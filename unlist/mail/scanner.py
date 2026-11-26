# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The discovery scanner: what one message says about who mailed the Subject.

Pure functions, no database. `scan(message)` takes one `email.message.Message` (a full
message from an mbox, or just its headers, as an IMAP scan would fetch them) and returns a
`ScanResult` (spec section 5, docs/research/mailbox-discovery-signals.md):

- Identity: the registrable domain of `From:`, trusted only when the topmost
  `Authentication-Results` header (the one the receiving provider added) shows
  `dmarc=pass`, or `dkim=pass` for a domain with the same registrable domain as `From:`.
- Bulk: any `List-*` header, `Precedence: bulk|list|junk`, or `Auto-Submitted` other than `no`.
- Evidence, strongest first: schema.org order or booking markup in the HTML body,
  transaction keywords, account keywords, bulk, none.
- Skipped: no usable `From:`, Gmail Takeout's Spam and Trash, personal mail (no bulk
  markers and a personal-mailbox provider, or one of the Subject's own addresses), and
  unauthenticated mail.

The body is read only to look for markup, and only for mail that is not skipped. Nothing
from it is returned except the evidence kind.
"""

import datetime
import email.errors
import email.header
import email.utils
import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from unlist.mail import psl

DATA_DIR = Path(__file__).resolve().parent / "data"

# Evidence kinds, strongest first.
ORDER_MARKUP = "order_markup"
TRANSACTION = "transaction"
ACCOUNT = "account"
BULK = "bulk"
NONE = "none"
EVIDENCE_ORDER = (ORDER_MARKUP, TRANSACTION, ACCOUNT, BULK, NONE)
ACCOUNT_OR_BETTER = (ORDER_MARKUP, TRANSACTION, ACCOUNT)

# Why a message was skipped.
SKIP_NO_SENDER = "no_sender"
SKIP_SPAM = "spam"
SKIP_PERSONAL = "personal"
SKIP_UNAUTHENTICATED = "unauthenticated"

SUBJECT_MAX = 300
HTML_MAX = 2 * 1024 * 1024  # bytes of one HTML part searched for markup
PARTS_MAX = 50
SPAM_LABELS = {"spam", "trash", "junk"}
BULK_PRECEDENCE = {"bulk", "list", "junk"}
MARKUP_TYPE = re.compile(r"^(?:https?://schema\.org/)?(Order|Invoice|ParcelDelivery|\w*Reservation)$", re.IGNORECASE)
MICRODATA = re.compile(
    r"""itemtype\s*=\s*["']?\s*https?://schema\.org/(?:Order|Invoice|ParcelDelivery|\w*Reservation)\b""", re.IGNORECASE
)
JSON_LD = re.compile(
    r"""<script\b[^>]*\btype\s*=\s*["']?application/ld\+json["']?[^>]*>(.*?)</script\s*>""", re.IGNORECASE | re.DOTALL
)
JSON_LD_TYPE = re.compile(
    r""""@type"\s*:\s*\[?\s*"(?:https?://schema\.org/)?(?:Order|Invoice|ParcelDelivery|\w*Reservation)\"""",
    re.IGNORECASE,
)
# Methods an Authentication-Results header may report (RFC 8601 and the IANA registry).
AUTH_METHODS = {
    "arc",
    "auth",
    "bimi",
    "compauth",
    "dkim",
    "dkim-adsp",
    "dkim-atps",
    "dmarc",
    "dnswl",
    "domainkeys",
    "iprev",
    "rrvs",
    "sender-id",
    "smime",
    "spf",
    "vbr",
}


@dataclass(frozen=True)
class ScanResult:
    sender_address: str = ""  # the From: address, lowercased
    sender_host: str | None = None  # its domain, lowercase ASCII
    sender_domain: str | None = None  # the registrable domain of sender_host
    display_name: str = ""
    date: datetime.datetime | None = None  # timezone-aware
    message_id: str = ""
    subject: str = ""  # the subject line, only for messages that are not skipped
    authenticated: bool = False
    is_bulk: bool = False
    evidence: str = NONE
    skip: str | None = None

    @property
    def discoverable(self):
        return self.skip is None


def evidence_rank(kind):
    """0 for the strongest evidence kind, higher for weaker ones."""
    try:
        return EVIDENCE_ORDER.index(kind)
    except ValueError:
        return len(EVIDENCE_ORDER)


def stronger(a, b):
    """The stronger of two evidence kinds."""
    return a if evidence_rank(a) <= evidence_rank(b) else b


# Data files -----------------------------------------------------------------------------


@cache
def personal_mail_providers():
    with open(DATA_DIR / "personal-mail-domains.json", encoding="utf-8") as handle:
        data = json.load(handle)
    return frozenset(data["domains"]), frozenset(data["names"])


def is_personal_domain(domain):
    """True for a personal-mailbox provider such as gmail.com or hotmail.co.uk."""
    registrable = psl.registrable_domain(domain or "")
    if not registrable:
        return False
    domains, names = personal_mail_providers()
    return registrable in domains or registrable.split(".", 1)[0] in names


@cache
def keyword_rules():
    """{kind: (subject regex or None, sender prefixes)} for the transaction and account kinds."""
    with open(DATA_DIR / "evidence-keywords.json", encoding="utf-8") as handle:
        data = json.load(handle)
    rules = {}
    for kind in (TRANSACTION, ACCOUNT):
        phrases = sorted({p.lower() for p in data[kind]["subject"]}, key=len, reverse=True)
        pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(p) for p in phrases) + ")") if phrases else None
        rules[kind] = (pattern, tuple(p.lower() for p in data[kind]["sender"]))
    return rules


# Headers --------------------------------------------------------------------------------


def _header_text(value):
    """A header value as text, with RFC 2047 encoded words decoded and whitespace collapsed."""
    if value is None:
        return ""
    try:
        text = str(email.header.make_header(email.header.decode_header(str(value))))
    except (UnicodeError, LookupError, ValueError, email.errors.HeaderParseError):
        text = str(value)
    return " ".join(text.split())


def _sender(message):
    """(display name, address) of the first From: address."""
    values = [str(v) for v in message.get_all("From", [])]
    if not values:
        return "", ""
    try:
        addresses = email.utils.getaddresses(values)
    except (TypeError, ValueError):
        return "", ""
    for name, address in addresses:
        if "@" in address:
            return _header_text(name), address.strip().lower()
    return "", ""


def _date(message):
    value = message.get("Date")
    if not value:
        return None
    try:
        date = email.utils.parsedate_to_datetime(str(value))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if date is None:
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.UTC)
    return date


def is_bulk(message):
    """Any List-* header, Precedence: bulk|list|junk, or Auto-Submitted other than "no"."""
    if any(name.lower().startswith("list-") for name in message.keys()):
        return True
    precedence = str(message.get("Precedence", "")).strip().lower()
    if precedence in BULK_PRECEDENCE:
        return True
    auto = message.get("Auto-Submitted")
    if auto is not None:
        keyword = str(auto).split(";", 1)[0].strip().lower()
        if keyword and keyword != "no":
            return True
    return False


def _is_spam(message):
    labels = message.get("X-Gmail-Labels")
    if not labels:
        return False
    return any(label.strip().lower() in SPAM_LABELS for label in _header_text(labels).split(","))


# Authentication-Results (RFC 8601) --------------------------------------------------------


def _strip_comments(value):
    """Remove (nested) parenthesised comments outside quoted strings."""
    out, depth, quoted, escaped = [], 0, False, False
    for char in value:
        if escaped:
            if depth == 0:
                out.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
            if depth == 0:
                out.append(char)
        elif quoted:
            out.append(char)
            if char == '"':
                quoted = False
        elif char == '"' and depth == 0:
            quoted = True
            out.append(char)
        elif char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        elif depth == 0:
            out.append(char)
    return "".join(out)


def parse_authentication_results(value):
    """(authserv-id or "", [(method, result, {property: value})]) from one header value.

    Tolerant: comments are dropped, spaces around "=" are allowed, the authserv-id may be
    missing (as in some Microsoft headers), and results are recognised by their method
    name even where a ";" between them is missing.
    """
    text = re.sub(r"\s*=\s*", "=", _strip_comments(" ".join(str(value).split())))
    segments = [segment.strip() for segment in text.split(";")]
    authserv_id = ""
    if segments and segments[0]:
        first = segments[0].split()
        if first and "=" not in first[0]:
            authserv_id = first[0].lower()
            segments[0] = " ".join(first[1:])
    results = []
    for segment in segments:
        for token in segment.split():
            key, sep, val = token.partition("=")
            if not sep:
                continue
            key, val = key.lower(), val.strip('"')
            method = key.split("/", 1)[0]
            if "." not in key and method in AUTH_METHODS:
                results.append((method, val.lower(), {}))
            elif results:
                results[-1][2][key] = val
    return authserv_id, results


def _domain_of(value):
    value = (value or "").strip().strip("<>")
    if "@" in value:
        value = value.rsplit("@", 1)[1]
    return psl.registrable_domain(value)


def is_authenticated(message, sender_domain):
    """True if the topmost Authentication-Results shows DMARC pass, or a DKIM pass aligned with `sender_domain`."""
    if not sender_domain:
        return False
    headers = message.get_all("Authentication-Results") or []
    if not headers:
        return False
    _, results = parse_authentication_results(headers[0])
    for method, result, properties in results:
        if result != "pass":
            continue
        if method == "dmarc":
            header_from = properties.get("header.from")
            if not header_from or _domain_of(header_from) == sender_domain:
                return True
        elif method == "dkim":
            signer = properties.get("header.d") or properties.get("header.i")
            if signer and _domain_of(signer) == sender_domain:
                return True
    return False


# Evidence -------------------------------------------------------------------------------


def _html_parts(message):
    """The text/html parts of a message, not descending into attached messages."""
    found = []

    def visit(part):
        if len(found) >= PARTS_MAX:
            return
        if part.is_multipart():
            for sub in part.get_payload() or []:
                if hasattr(sub, "get_content_maintype") and sub.get_content_maintype() != "message":
                    visit(sub)
        elif part.get_content_type() == "text/html":
            found.append(part)

    visit(message)
    return found


def _has_type(node, depth=0):
    if depth > 20:
        return False
    if isinstance(node, list):
        return any(_has_type(item, depth + 1) for item in node)
    if isinstance(node, dict):
        types = node.get("@type")
        for kind in types if isinstance(types, list) else [types]:
            if isinstance(kind, str) and MARKUP_TYPE.match(kind.strip()):
                return True
        return any(_has_type(value, depth + 1) for value in node.values() if isinstance(value, (dict, list)))
    return False


def html_has_order_markup(html):
    """True if HTML carries schema.org Order, Invoice, ParcelDelivery or *Reservation (JSON-LD or Microdata)."""
    if MICRODATA.search(html):
        return True
    for block in JSON_LD.findall(html):
        try:
            if _has_type(json.loads(block.strip())):
                return True
        except ValueError:
            if JSON_LD_TYPE.search(block):
                return True
    return False


def has_order_markup(message):
    for part in _html_parts(message):
        try:
            payload = part.get_payload(decode=True)
        except (ValueError, TypeError, AssertionError):
            continue
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            html = payload[:HTML_MAX].decode(charset, errors="replace")
        except LookupError:
            html = payload[:HTML_MAX].decode("utf-8", errors="replace")
        if html_has_order_markup(html):
            return True
    return False


def _local_words(address):
    local = address.rsplit("@", 1)[0]
    return [word for word in re.split(r"[^a-z0-9äöüß]+", local.lower()) if word]


def keyword_evidence(subject, sender_address):
    """TRANSACTION, ACCOUNT or None from the subject line and the From: local part."""
    subject = subject.lower()
    words = _local_words(sender_address)
    for kind, (pattern, prefixes) in keyword_rules().items():
        if pattern is not None and pattern.search(subject):
            return kind
        if any(word.startswith(prefix) for word in words for prefix in prefixes):
            return kind
    return None


# The scan -------------------------------------------------------------------------------


def scan(message, own_addresses=()):
    """Scan one message. `own_addresses` are the Subject's own addresses (lowercase); mail from them is personal."""
    display_name, address = _sender(message)
    host = psl.normalize_host(address.rsplit("@", 1)[1]) if address else None
    domain = psl.registrable_domain(host) if host else None
    date = _date(message)
    message_id = _header_text(message.get("Message-ID")).strip()
    base = {
        "sender_address": address,
        "sender_host": host,
        "sender_domain": domain,
        "display_name": display_name[:200],
        "date": date,
        "message_id": message_id[:500],
    }
    if not domain:
        return ScanResult(**base, skip=SKIP_NO_SENDER)
    if _is_spam(message):
        return ScanResult(**base, skip=SKIP_SPAM)
    bulk = is_bulk(message)
    if address in own_addresses or (not bulk and is_personal_domain(domain)):
        return ScanResult(**base, is_bulk=bulk, skip=SKIP_PERSONAL)
    if not is_authenticated(message, domain):
        return ScanResult(**base, is_bulk=bulk, skip=SKIP_UNAUTHENTICATED)
    subject = _header_text(message.get("Subject"))[:SUBJECT_MAX]
    if has_order_markup(message):
        evidence = ORDER_MARKUP
    else:
        evidence = keyword_evidence(subject, address) or (BULK if bulk else NONE)
    return ScanResult(**base, subject=subject, authenticated=True, is_bulk=bulk, evidence=evidence)
