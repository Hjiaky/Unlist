# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Replies: match incoming mail to a Case, suggest the outcome, let the Operator confirm (spec section 7).

The entry point other code calls for every message it has for a Subject::

    from unlist.cases.replies import ingest_message
    reply = ingest_message(subject, message, source="imap", raw=raw_bytes)   # Reply or None

``source`` is ``"imap"`` (the live mailbox), ``"mbox"`` (a mailbox import) or ``"upload"`` (an
``.eml`` the Operator uploaded on a Case page, which passes ``case=``). A batch of messages
can share one :class:`Matcher` (``matcher=``), or go through :func:`ingest_each`, which the mbox
import wraps around its message stream.

Matching, in order (first hit wins):

1. ``In-Reply-To`` / ``References`` (or, for a bounce, the returned message's ``Message-ID``)
   name a stored ``Draft.message_id``.
2. The subject line holds a Case reference code (``[Ref U-7KQ3]`` or the bare code), as a
   ticket system answering in a new thread keeps it.
3. The sender's registrable domain, authenticated (the discovery scanner's check), belongs to an
   Organization with exactly one open Case for this Subject that has sent something before
   the message's date. Bulk mail (newsletters) never matches this way.
4. Otherwise the reply goes to the unmatched queue, but only if it is plausibly related: it
   carries something that looks like a reference code, or comes (not as bulk mail, and after
   the first request was sent) from a domain of an Organization with a Case for this Subject.
   Anything else is not stored at all.

Mail from the Subject's own addresses (their sent requests, perhaps with an ID attached) and
Unlist's own sent drafts are never taken in. Messages are de-duplicated by Message-ID.

What happens next:

- A delivery status notification that reports a failure and matches a Case is recorded as a
  bounce right away (``auto_recorded``): the Case becomes undeliverable.
- An automatic reply (``Auto-Submitted: auto-replied``, ``X-Autoreply``, out-of-office subject
  lines in English or German) is attached to the Case as a note, with no state change.
- Everything else gets a suggested outcome and waits for the Operator (``to_confirm``).
  Suggesters registered in :data:`suggesters` are asked first (the optional LLM plugs in
  here); the keyword rules (English and German) are the fallback. Nothing changes on a
  guess: :func:`confirm` records the outcome the Operator chose, dated the day the reply came.

Decided by agent (ticket #49):

- Matching by sender domain and the unmatched queue only consider mail dated on or after the
  day the Case's first request was sent, so importing years of a shop's order mail does not
  flood the queue.
- A dismissed reply keeps only its headers (to stay de-duplicated); its text and files are
  deleted, so dismissed mail is not kept.
- ``Auto-Submitted: auto-generated`` alone is not an automatic reply: ticket systems send real
  answers with it.
- A delivery report whose only action is ``delayed`` (or ``delivered``, ``relayed``,
  ``expanded``) is treated as an automatic reply, not a bounce.
"""

import email
import email.policy
import email.utils
import hashlib
import logging
import mimetypes
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from email.parser import HeaderParser
from html.parser import HTMLParser

from django.db import IntegrityError, transaction
from django.db.models import Min
from django.utils import timezone

from unlist.cases import services, storage
from unlist.cases.lifecycle import OUTCOMES, Action
from unlist.cases.models import Attachment, Case, CaseEvent, Draft, Reply
from unlist.mail import scanner
from unlist.organizations import domains as organization_domains
from unlist.organizations import lookup

log = logging.getLogger("unlist.cases")

SOURCES = ("imap", "mbox", "upload")
BODY_MAX = 200_000  # characters of text kept per reply
RULES_TEXT_MAX = 20_000  # characters the keyword rules read
PARTS_MAX = 50
ATTACH_ONLY = "attach_only"  # confirm without recording an outcome

# Reference codes: "U-" and four or more characters of services.REFERENCE_ALPHABET.
_CODE = r"U-[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{4,8}"
REFERENCE_RE = re.compile(rf"(?<![A-Za-z0-9]){_CODE}(?![A-Za-z0-9])", re.IGNORECASE)
_MESSAGE_ID_RE = re.compile(r"<([^<>\s]+)>")
_SYSTEM_SENDERS = ("mailer-daemon", "postmaster", "mail-daemon", "mailerdaemon")
_DSN_FAILED = "failed"
_OUT_OF_OFFICE = re.compile(
    r"out of (the )?office|automatic reply|auto[- ]?reply|autoreply|auto[- ]?response|away from (the )?office|"
    r"on (vacation|holiday|leave)|abwesenheit|abwesend|automatische antwort|nicht im büro|urlaub",
    re.IGNORECASE,
)


# --- Suggestions ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Suggestion:
    """A guess at a reply's outcome. Shown to the Operator, never applied on its own.

    ``outcome`` is one of ``lifecycle.OUTCOMES`` (as a string); ``source`` is ``"rules"`` or
    ``"llm"``; ``note`` says why, in a few words.
    """

    outcome: str
    source: str
    note: str = ""
    exception: str = ""
    suppression_confirmed: bool | None = None
    with_reasons: bool | None = None


# Callables ``(reply) -> Suggestion | None``, asked in order before the keyword rules. The
# optional LLM registers one; a suggester that fails is skipped.
suggesters: list[Callable[[Reply], Suggestion | None]] = []


def _rx(*patterns: str) -> list[re.Pattern]:
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


RULES: list[tuple[str, list[re.Pattern]]] = [
    (
        "refused",
        _rx(
            r"\b(unable|not able|cannot|can ?not|can't|won't|will not)( to)? (fully )?(delete|erase|remove|comply|"
            r"fulfil|fulfill)",
            r"\b(must|need to|required to|obliged to|obligated to|have to) (retain|keep|store)\b",
            r"\bretention (period|obligation|requirement|dut)",
            r"\b(refuse|decline|reject)(d|s)?\b.{0,40}\brequest",
            r"\bart(icle|\.)? ?17 ?\(3\)",
            r"\bmanifestly unfounded\b",
            r"\bart(icle|\.)? ?12 ?\(5\)",
            r"(können|könnten|dürfen)\b.{0,60}\bnicht\b.{0,30}(löschen|entfernen|nachkommen)",
            r"nicht gelöscht werden",
            r"aufbewahrungs(pflicht|frist)",
            r"(aufbewahren|speichern) müssen|müssen\b.{0,40}\b(aufbewahren|speichern)",
            r"\blehnen\b.{0,60}\bab\b",
            r"art\.? ?17 abs\.? ?3",
            r"offenkundig unbegründet",
        ),
    ),
    (
        "extension_announced",
        _rx(
            r"\bextend(ed|ing)? (the )?(deadline|period|time|response time)",
            r"\bextension\b",
            r"\b(two|2) (further|additional|more) months\b",
            r"\bneed (more|additional|further) time\b",
            r"fristverlängerung",
            r"(frist|bearbeitungszeit|bearbeitungsfrist)\b.{0,40}verlänger",
            r"verlänger\w*\b.{0,40}\b(frist|monate)",
            r"(zwei|2) (weitere|zusätzliche) monate",
        ),
    ),
    (
        "id_or_details_asked",
        _rx(
            r"\bverify (your )?identity\b",
            r"\bidentity (document|card|verification|check)",
            r"\b(copy|scan|photo|picture) of (your |a |an )?(valid )?(id|passport|identity|driving licen[cs]e|"
            r"driver'?s licen[cs]e)",
            r"\bpassport\b",
            r"\bproof of (identity|address)\b",
            r"\bconfirm (your )?identity\b",
            r"\bphoto id\b",
            r"\b(verify|verification of) (you|your)\b",
            r"\bunable to (identify|locate|find) (you|your account|your data)",
            r"\b(provide|send|tell)( us)?( with)? (your )?.{0,30}(customer number|account number|date of birth|"
            r"order number|postal address)",
            r"ausweis",
            r"reisepass",
            r"identität\w*\b.{0,40}\b(bestätigen|nachweisen|prüfen|verifizieren)",
            r"identitätsnachweis|identitätsprüfung",
            r"(kundennummer|geburtsdatum|anschrift|bestellnummer)\b.{0,60}\b(mitteilen|nennen|angeben|zusenden|"
            r"übermitteln)",
            r"nicht (eindeutig )?(zuordnen|identifizieren)",
        ),
    ),
    (
        "removed",
        _rx(
            r"\b(have|has|had|been|was|were) (now |successfully |permanently |fully )*(deleted|erased|removed)\b",
            r"\b(deleted|erased|removed) (all )?(of )?(your|the) (personal )?(data|information|account|details|"
            r"records?)\b",
            r"\bdeletion (is |has been )?(complete|completed|confirmed|carried out)",
            r"\b(wurden|wurde|ist|sind|haben)\b.{0,60}\bgelöscht\b",
            r"löschung\b.{0,40}\b(durchgeführt|abgeschlossen|bestätigt|erfolgt)",
        ),
    ),
    (
        "nothing_held",
        _rx(
            r"\b(no|not any) (personal )?(data|information|records?)\b.{0,60}\b(about|on|for|relating to|regarding|"
            r"concerning)\b (you|your)",
            r"\b(do|does|did) not (hold|have|store|process|keep) any\b",
            r"\bcould not find any\b",
            r"\bno (matching |such )?(account|record|data)s? (was |were )?found\b",
            r"\bwe (hold|have|store|process) no (personal )?(data|information)",
            r"keine (personenbezogenen )?daten",
            r"keine (daten|informationen|einträge|datensätze)\b.{0,40}\b(gespeichert|vorhanden|gefunden)",
            r"\b(kein|keinen) (kundenkonto|konto|eintrag|datensatz)",
        ),
    ),
    (
        "listing_found",
        _rx(
            r"\b(copy|overview|summary|export) of (your|the) (personal )?(data|information)",
            r"\b(attached|enclosed|attachment)\b.{0,60}\b(data|information)\b",
            r"\bthe following (personal )?(data|information)\b",
            r"\byour (personal )?data\b",
            r"\bauskunft",
            r"(kopie|übersicht|auszug|export) (ihrer|der) (personenbezogenen )?daten",
            r"(anbei|anhang|beigefügt)\b.{0,60}\bdaten",
            r"folgende (daten|informationen)",
        ),
    ),
]
SUPPRESSION_RE = re.compile(
    r"suppression|sperrliste|sperrvermerk|werbesperre|robinson|do[- ]not[- ](contact|mail|call|email)|"
    r"block ?list|blacklist",
    re.IGNORECASE,
)
REASONS_RE = re.compile(
    r"\bbecause\b|\bdue to\b|\bowing to\b|\bcomplex|\bnumber of requests\b|\bvolume of\b|\baufgrund\b|\bwegen\b|"
    r"komplexität|vielzahl|umfang",
    re.IGNORECASE,
)
_EXCEPTION_HINTS = re.compile(
    r"\bart(icle|\.)?\s*\d|§|legal obligation|legal requirement|retain|retention|aufbewahr|gesetzlich|\btax|steuer|"
    r"handelsrecht|\bhgb\b|\bao\b|accounting|buchhaltung|fraud|betrug|legal claims|rechtsansprüch|"
    r"freedom of expression|meinungsfreiheit|public interest|öffentlichen interesse|manifestly|offenkundig",
    re.IGNORECASE,
)
_ACKNOWLEDGEMENT = re.compile(
    r"(we have|we've) received your (request|email|message)|thank you for (your|contacting)|"
    r"(wir haben|haben wir) ihre (anfrage|e-mail|nachricht)\b.{0,20}erhalten|vielen dank für ihre (anfrage|nachricht)",
    re.IGNORECASE,
)
# Words that contain "ID" without asking for an identity document.
_NOT_AN_ID = re.compile(
    r"\b(ticket|request|case|customer|reference|order|user|account|message|transaction|vorgangs|kunden)[- ]?id\b",
    re.IGNORECASE,
)
_BARE_ID = re.compile(r"\bID\b")
_QUOTE_START = re.compile(
    r"^(-{2,}\s*(original message|ursprüngliche nachricht|forwarded message|weitergeleitete nachricht)|"
    r"on .{0,200}wrote:|am .{0,200}schrieb.{0,100}:)\s*$",
    re.IGNORECASE,
)


def strip_quoted(text: str) -> str:
    """The new part of a reply: without ``>`` lines and without the quoted original below it."""
    kept = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if _QUOTE_START.match(stripped):
            break
        if stripped.startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept)


def _sentences(text: str) -> list[str]:
    return [" ".join(part.split()) for part in re.split(r"(?<=[.!?])\s+|\n\s*\n", text) if part.strip()]


def cited_exception(text: str, max_length: int = 300) -> str:
    """The sentence of a refusal that names the exception or legal duty, as best the rules can tell."""
    sentences = _sentences(text)
    for sentence in sentences:
        if _EXCEPTION_HINTS.search(sentence):
            return sentence[:max_length]
    patterns = dict(RULES)["refused"]
    for sentence in sentences:
        if any(pattern.search(sentence) for pattern in patterns):
            return sentence[:max_length]
    return ""


def rules_suggestion(subject_line: str, body: str, *, has_files: bool = False) -> Suggestion | None:
    """The keyword rules (English and German). Pure: no database."""
    text = f"{subject_line or ''}\n{strip_quoted(body or '')}"[:RULES_TEXT_MAX]
    rules = RULES
    if SUPPRESSION_RE.search(text) and any(pattern.search(text) for pattern in dict(RULES)["removed"]):
        # Keeping an address on a suppression list after removal is what a Removal Request asks a
        # Broker for, not a refusal.
        rules = [rule for rule in RULES if rule[0] != "refused"]
    for outcome, patterns in rules:
        match = next((found for pattern in patterns if (found := pattern.search(text))), None)
        if match is None and outcome == "id_or_details_asked":
            match = _BARE_ID.search(_NOT_AN_ID.sub(" ", text))  # "ID" in capitals, not "Ticket ID"
        if match is None:
            continue
        if outcome == "listing_found" and _ACKNOWLEDGEMENT.search(text) and not has_files:
            return None  # "we received your request" is not an answer yet
        note = f'Keyword rule: "{" ".join(match.group(0).split())[:60]}"'
        if outcome == "refused":
            return Suggestion(outcome, "rules", note, exception=cited_exception(text))
        if outcome == "removed":
            return Suggestion(outcome, "rules", note, suppression_confirmed=bool(SUPPRESSION_RE.search(text)))
        if outcome == "extension_announced":
            return Suggestion(outcome, "rules", note, with_reasons=bool(REASONS_RE.search(text)))
        return Suggestion(outcome, "rules", note)
    if has_files:
        return Suggestion("listing_found", "rules", "Files are attached")
    return None


def suggest(reply: Reply) -> Suggestion | None:
    """Ask the registered suggesters in order, then the keyword rules."""
    for suggester in list(suggesters):
        try:
            found = suggester(reply)
        except Exception:  # an optional suggester must never stop a reply from being taken in
            log.warning("Suggester %r failed", suggester, exc_info=True)
            continue
        if found is not None and found.outcome in {action.value for action in OUTCOMES}:
            return found
    has_files = reply.pk is not None and reply.attachments.exclude(pk=reply.raw_attachment_id).exists()
    return rules_suggestion(reply.subject_line, reply.body, has_files=has_files)


def _apply_suggestion(reply: Reply, found: Suggestion | None) -> None:
    if found is None:
        return
    reply.suggested_outcome = found.outcome
    reply.suggestion_source = found.source if found.source in Reply.SuggestionSource.values else "llm"
    reply.suggestion_note = (found.note or "")[:500]
    reply.suggested_exception = found.exception or ""
    reply.suggested_suppression = found.suppression_confirmed
    reply.suggested_with_reasons = found.with_reasons


# --- Reading a message ---------------------------------------------------------------------


class _HTMLText(HTMLParser):
    BLOCK = frozenset("p div br li tr table ul ol h1 h2 h3 h4 h5 h6 section article header footer pre hr dd dt".split())
    SKIP = frozenset({"script", "style", "head", "title"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.quote = 0

    def _newline(self):
        self.parts.append("\n> " if self.quote else "\n")

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "blockquote":
            self.quote += 1
            self._newline()
        elif tag in self.BLOCK:
            self._newline()
            if tag == "li":
                self.parts.append("- ")

    def handle_startendtag(self, tag, attrs):
        if tag in self.BLOCK:
            self._newline()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "blockquote":
            self.quote = max(0, self.quote - 1)
            self._newline()
        elif tag in self.BLOCK:
            self._newline()

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data.replace("\n", "\n> ") if self.quote else data)


def html_to_text(html: str) -> str:
    """Readable text from HTML with the standard library only: blocks become lines, quotes get ``>``."""
    parser = _HTMLText()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:  # malformed HTML: keep what was read
        log.debug("HTML parse problem", exc_info=True)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    text = "\n".join(line for line in lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _decode(part) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        return ""
    if not isinstance(payload, bytes):
        return payload if isinstance(payload, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _is_attachment(part) -> bool:
    return part.get_content_disposition() == "attachment"


def _children(part) -> list:
    payload = part.get_payload()
    return [sub for sub in payload if hasattr(sub, "get_content_type")] if isinstance(payload, list) else []


def body_text(message) -> str:
    """The first plain-text part, else the first HTML part as text. Attached messages are not read."""
    found: dict[str, str] = {}
    count = 0

    def visit(part):
        nonlocal count
        count += 1
        if count > PARTS_MAX:
            return
        if part.is_multipart():
            for sub in _children(part):
                if sub.get_content_maintype() != "message":
                    visit(sub)
            return
        if _is_attachment(part):
            return
        content_type = part.get_content_type()
        if content_type == "text/plain" and "plain" not in found:
            found["plain"] = _decode(part)
        elif content_type == "text/html" and "html" not in found:
            found["html"] = _decode(part)

    visit(message)
    if found.get("plain", "").strip():
        text = found["plain"]
    else:
        text = html_to_text(found.get("html", ""))
    return text.replace("\r\n", "\n").strip()[:BODY_MAX]


@dataclass(frozen=True)
class FilePart:
    name: str
    content_type: str
    data: bytes


def file_parts(message) -> list[FilePart]:
    """The files a reply carries: attachments, and attached messages as ``.eml``. Inline images are skipped."""
    found: list[FilePart] = []
    count = 0

    def visit(part):
        nonlocal count
        count += 1
        if count > PARTS_MAX or len(found) >= PARTS_MAX:
            return
        content_type = part.get_content_type()
        filename = scanner._header_text(part.get_filename()) if part.get_filename() else ""
        if part.get_content_maintype() == "message":
            if _is_attachment(part) or filename:
                children = _children(part)
                data = _message_bytes(children[0]) if children else b""
                found.append(FilePart(filename or f"attached-message-{len(found) + 1}.eml", "message/rfc822", data))
            return
        if part.is_multipart():
            for sub in _children(part):
                visit(sub)
            return
        inline_image = part.get_content_maintype() == "image" and part.get("Content-ID") and not _is_attachment(part)
        if inline_image or not (_is_attachment(part) or (filename and not content_type.startswith("text/"))):
            return
        try:
            data = part.get_payload(decode=True) or b""
        except Exception:
            data = b""
        if len(data) > storage.MAX_UPLOAD_BYTES:
            return
        extension = mimetypes.guess_extension(content_type) or ".bin"
        found.append(FilePart(filename or f"attachment-{len(found) + 1}{extension}", content_type, data))

    visit(message)
    return found


def _message_bytes(message) -> bytes:
    try:
        return message.as_bytes()
    except Exception:
        try:
            return message.as_string().encode("utf-8", errors="replace")
        except Exception:
            return b""


def normalise_message_id(value: str) -> str:
    return (value or "").strip().strip("<>").strip().lower()


def message_ids(value) -> list[str]:
    """The Message-IDs in an ``In-Reply-To`` or ``References`` value, normalised."""
    text = scanner._header_text(value)
    found = _MESSAGE_ID_RE.findall(text) or text.split()
    return [normalise_message_id(item) for item in found if "@" in item]


def reference_codes(text: str) -> list[str]:
    """Things that look like Case reference codes, upper-cased, in order."""
    return [code.upper() for code in REFERENCE_RE.findall(text or "")]


@dataclass
class DeliveryReport:
    failed: bool
    original_ids: list[str] = field(default_factory=list)
    original_subjects: list[str] = field(default_factory=list)


def delivery_report(message, sender_address: str) -> DeliveryReport | None:
    """What a delivery status notification says, or None if the message is not one."""
    is_report = (
        message.get_content_type() == "multipart/report"
        and str(message.get_param("report-type", "") or "").lower() == "delivery-status"
    )
    actions: list[str] = []
    has_status = False
    ids: list[str] = []
    subjects: list[str] = []
    for count, part in enumerate(message.walk()):
        if count > PARTS_MAX:
            break
        content_type = part.get_content_type()
        if content_type == "message/delivery-status":
            has_status = True
            payload = part.get_payload()
            blocks = payload if isinstance(payload, list) else []
            for block in blocks:
                if hasattr(block, "get") and block.get("Action"):
                    actions.append(str(block.get("Action")).strip().lower())
            if not blocks and isinstance(payload, str):
                actions += [m.lower() for m in re.findall(r"^Action:\s*(\w+)", payload, re.MULTILINE | re.I)]
        elif content_type in ("message/rfc822", "message/rfc822-headers", "text/rfc822-headers"):
            children = _children(part)
            if children:
                original = children[0]
            else:
                original = HeaderParser().parsestr(_decode(part))
            if original.get("Message-ID"):
                ids.append(normalise_message_id(scanner._header_text(original.get("Message-ID"))))
            if original.get("Subject"):
                subjects.append(scanner._header_text(original.get("Subject")))
    local = sender_address.split("@", 1)[0].lower()
    if not is_report and not (local in _SYSTEM_SENDERS and has_status):
        return None
    failed = not actions or any(action.startswith(_DSN_FAILED) for action in actions)
    return DeliveryReport(failed=failed, original_ids=ids, original_subjects=subjects)


def is_auto_reply(message, subject_line: str) -> bool:
    auto = str(message.get("Auto-Submitted", "")).split(";", 1)[0].strip().lower()
    if auto == "auto-replied":
        return True
    if message.get("X-Autoreply") is not None or message.get("X-Autorespond") is not None:
        return True
    if str(message.get("Precedence", "")).strip().lower() == "auto_reply":
        return True
    return bool(_OUT_OF_OFFICE.search(subject_line or ""))


@dataclass
class Parsed:
    """The headers of one message, as matching needs them."""

    from_address: str
    from_name: str
    sender_domain: str | None
    authenticated: bool
    bulk: bool
    date: datetime | None
    message_id: str
    subject_line: str
    thread_ids: list[str]
    report: DeliveryReport | None
    auto_reply: bool

    @property
    def received_on(self) -> date:
        today = timezone.localdate()
        return min(timezone.localdate(self.date), today) if self.date else today

    @property
    def codes(self) -> list[str]:
        texts = [self.subject_line, *(self.report.original_subjects if self.report else [])]
        return [code for text in texts for code in reference_codes(text)]

    @property
    def dedup_key(self) -> str:
        if self.message_id:
            key = "id:" + normalise_message_id(self.message_id)
        else:
            when = self.date.isoformat() if self.date else ""
            key = f"hdr:{self.from_address}\n{when}\n{self.subject_line}"
        return hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()[:32]


def parse(message) -> Parsed:
    from_name, address = scanner._sender(message)
    host = address.rsplit("@", 1)[1] if "@" in address else ""
    domain = organization_domains.registrable_domain(host) if host else None
    subject_line = scanner._header_text(message.get("Subject"))[:500]
    references = " ".join(str(value) for value in message.get_all("References", []))
    thread_ids = message_ids(message.get("In-Reply-To")) + message_ids(references)
    report = delivery_report(message, address)
    return Parsed(
        from_address=address,
        from_name=from_name[:200],
        sender_domain=domain,
        authenticated=bool(domain) and scanner.is_authenticated(message, domain),
        bulk=scanner.is_bulk(message),
        date=scanner._date(message),
        message_id=scanner._header_text(message.get("Message-ID")).strip()[:500],
        subject_line=subject_line,
        thread_ids=thread_ids,
        report=report,
        auto_reply=report is None and is_auto_reply(message, subject_line),
    )


# --- Matching ------------------------------------------------------------------------------


def _organization_domains(organization) -> set[str]:
    """The registrable domains an Organization mails from, as far as Unlist knows them."""
    values = [*(organization.domains or []), organization.email or "", organization.web or ""]
    values += [claim.domain for claim in organization.domain_claims.all()]
    found = set()
    for value in values:
        domain = organization_domains.registrable_domain(value) if value else None
        if domain and not lookup.is_ambiguous(domain) and not scanner.is_personal_domain(domain):
            found.add(domain)
    return found


class Matcher:
    """What matching needs to know about one Subject's Cases. Build once per batch of messages."""

    def __init__(self, subject):
        self.subject = subject
        cases = list(subject.cases.select_related("organization").prefetch_related("organization__domain_claims"))
        self.cases: dict[int, Case] = {case.pk: case for case in cases}
        self.own_addresses = frozenset(address.lower() for address in subject.mailboxes.values_list("email", flat=True))
        drafts = Draft.objects.filter(case__subject=subject).exclude(message_id="")
        self.drafts = {
            normalise_message_id(mid): case_id for case_id, mid in drafts.values_list("case_id", "message_id")
        }
        self.references = {case.reference.upper(): case.pk for case in cases}
        first_sent = (
            CaseEvent.objects.filter(case__subject=subject, kind=CaseEvent.Kind.SENT)
            .values("case")
            .annotate(first=Min("occurred_on"))
            .values_list("case", "first")
        )
        self.first_sent: dict[int, date] = dict(first_sent)
        self.domains: dict[str, set[int]] = defaultdict(set)
        for case in cases:
            for domain in _organization_domains(case.organization):
                self.domains[domain].add(case.pk)

    def _sent_before(self, case_id: int, parsed: Parsed) -> bool:
        first = self.first_sent.get(case_id)
        return first is not None and parsed.received_on >= first

    def match(self, parsed: Parsed) -> tuple[Case, str] | None:
        ids = parsed.thread_ids + (parsed.report.original_ids if parsed.report else [])
        for message_id in ids:
            if message_id in self.drafts:
                return self.cases[self.drafts[message_id]], Reply.MatchedBy.IN_REPLY_TO
        for code in parsed.codes:
            if code in self.references:
                return self.cases[self.references[code]], Reply.MatchedBy.REFERENCE
        if parsed.authenticated and not parsed.bulk and parsed.report is None and parsed.sender_domain:
            open_cases = [pk for pk in self.domains.get(parsed.sender_domain, ()) if self.cases[pk].is_open]
            if len(open_cases) == 1 and self._sent_before(open_cases[0], parsed):
                return self.cases[open_cases[0]], Reply.MatchedBy.SENDER_DOMAIN
        return None

    def plausible(self, parsed: Parsed) -> bool:
        """Worth the unmatched queue: looks like it carries a reference, or comes from a Case's Organization."""
        if parsed.codes:
            return True
        if parsed.bulk or parsed.report is not None or not parsed.sender_domain:
            return False
        return any(self._sent_before(pk, parsed) for pk in self.domains.get(parsed.sender_domain, ()))

    def is_own(self, parsed: Parsed) -> bool:
        """Sent by the Subject (their own address) or one of Unlist's own drafts."""
        return parsed.from_address in self.own_addresses or (
            bool(parsed.message_id) and normalise_message_id(parsed.message_id) in self.drafts
        )


# --- Taking a message in -------------------------------------------------------------------


@dataclass(frozen=True)
class Ingested:
    """What :func:`ingest` did: the stored Reply, or None and why (``own``, ``unrelated``, ``duplicate``...)."""

    reply: Reply | None
    reason: str = ""


def _store_case_files(reply: Reply, raw: bytes, message, written: list[str]) -> None:
    """The ``.eml`` and the files of a reply that has a Case, as Attachments of that Case."""
    case = reply.case
    eml = storage.store_attachment(
        case, f"{case.reference}-reply-{reply.pk}.eml", raw, content_type="message/rfc822", reply=reply
    )
    written.append(eml.stored_path)
    reply.raw_attachment = eml
    if reply.kind == Reply.Kind.BOUNCE:
        return  # the returned message is in the .eml; it is Unlist's own request
    for part in file_parts(message):
        attachment = storage.store_attachment(case, part.name, part.data, content_type=part.content_type, reply=reply)
        written.append(attachment.stored_path)


def _link_attachments(reply: Reply, event: CaseEvent) -> None:
    reply.attachments.update(event=event)
    if reply.raw_attachment is not None:
        reply.raw_attachment.event = event


def _decide(reply: Reply) -> None:
    """What happens to a reply once it has a Case (or right away, for the unmatched queue)."""
    case = reply.case
    if case is None:
        if reply.kind == Reply.Kind.REPLY:
            _apply_suggestion(reply, suggest(reply))
        elif reply.kind == Reply.Kind.BOUNCE:
            _apply_suggestion(reply, Suggestion("bounce", "rules", "Delivery status notification"))
        return
    if reply.kind == Reply.Kind.BOUNCE:
        try:
            event = services.record_outcome(case, Action.BOUNCE, on=reply.received_on, reply=reply.pk)
        except services.CaseError as error:
            note = f"Delivery status notification; not recorded automatically: {error}"
            _apply_suggestion(reply, Suggestion("bounce", "rules", note))
            return
        _finish(reply, event, Reply.Status.AUTO_RECORDED)
    elif reply.kind == Reply.Kind.AUTO_REPLY:
        event = services.add_note(
            case,
            f"Automatic reply from {reply.from_address or 'the Organization'} ({reply.subject_line}). Nothing changes.",
            on=reply.received_on,
            details={"reply": reply.pk},
        )
        _finish(reply, event, Reply.Status.AUTO_RECORDED)
    else:
        _apply_suggestion(reply, suggest(reply))


def _finish(reply: Reply, event: CaseEvent, status: str) -> None:
    _link_attachments(reply, event)
    reply.event, reply.status, reply.decided_at = event, status, timezone.now()


def _cleanup(written: list[str]) -> None:
    for path in written:
        storage.delete_file(path)


def ingest(subject, message, *, source: str, raw: bytes | None = None, case=None, matcher=None) -> Ingested:
    """Take in one message for ``subject`` if it belongs to (or plausibly relates to) one of its Cases.

    ``case`` (an upload from a Case page) skips matching: the Operator chose. ``matcher`` lets a
    batch share one :class:`Matcher`. Raises ``ValueError`` for an unknown ``source``.
    """
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}")
    if message is None:
        return Ingested(None, "unreadable")
    if case is not None and case.subject_id != subject.pk:
        raise ValueError("The Case belongs to another Subject.")
    matcher = matcher or Matcher(subject)
    parsed = parse(message)
    if matcher.is_own(parsed):
        return Ingested(None, "own")
    if case is not None:
        matched_by = Reply.MatchedBy.OPERATOR
    else:
        found = matcher.match(parsed)
        if found is None and not matcher.plausible(parsed):
            return Ingested(None, "unrelated")
        case, matched_by = found if found else (None, "")
    key = parsed.dedup_key
    if Reply.objects.filter(subject=subject, dedup_key=key).exists():
        return Ingested(None, "duplicate")
    raw = raw if raw is not None else _message_bytes(message)
    if parsed.report is not None and parsed.report.failed:
        kind = Reply.Kind.BOUNCE
    elif parsed.report is not None or parsed.auto_reply:
        kind = Reply.Kind.AUTO_REPLY
    else:
        kind = Reply.Kind.REPLY
    written: list[str] = []
    try:
        with transaction.atomic():
            reply = Reply.objects.create(
                subject=subject,
                case=case,
                kind=kind,
                source=source,
                message_id=parsed.message_id,
                dedup_key=key,
                from_address=parsed.from_address[:320],
                from_name=parsed.from_name,
                sender_domain=parsed.sender_domain or "",
                authenticated=parsed.authenticated,
                received_at=parsed.date or timezone.now(),
                subject_line=parsed.subject_line,
                body=body_text(message),
                matched_by=matched_by,
            )
            if case is not None:
                _store_case_files(reply, raw, message, written)
            else:
                reply.raw_path, reply.raw_sha256 = storage.store_unmatched(subject.pk, f"reply-{reply.pk}.eml", raw)
                written.append(reply.raw_path)
            _decide(reply)
            reply.save()
    except IntegrityError:
        _cleanup(written)
        if Reply.objects.filter(subject=subject, dedup_key=key).exists():
            return Ingested(None, "duplicate")  # taken in at the same moment by another process
        raise
    except Exception:
        _cleanup(written)
        raise
    return Ingested(reply, "matched" if case is not None else "unmatched")


def ingest_message(
    subject, message: email.message.Message, *, source: str, raw: bytes | None = None, case=None, matcher=None
) -> Reply | None:
    """Take in one message for ``subject``; the stored Reply, or None if it was not taken in.

    None means: from the Subject's own address, one of Unlist's own drafts, unrelated to any of
    the Subject's Cases, or already taken in (same Message-ID). See :func:`ingest` for why.
    """
    return ingest(subject, message, source=source, raw=raw, case=case, matcher=matcher).reply


def ingest_each(subject, messages: Iterable, *, source: str = "mbox") -> Iterator:
    """Pass ``messages`` through unchanged, taking in each one that is a reply on the way.

    For the mbox import: a message that cannot be taken in is logged and skipped; it never
    stops the stream (discovery goes on). ``None`` items are passed through untouched.
    """
    matcher = None
    for message in messages:
        if message is not None:
            try:
                matcher = matcher or Matcher(subject)
                ingest(subject, message, source=source, matcher=matcher)
            except Exception:
                log.warning("Could not take in a reply during the import", exc_info=True)
        yield message


def parse_bytes(data: bytes):
    """An uploaded ``.eml`` as a message (the same tolerant policy as the mbox import)."""
    return email.message_from_bytes(data, policy=email.policy.compat32)


# --- The Operator decides ------------------------------------------------------------------


def confirm(reply: Reply, outcome: str, *, on: date | None = None, **details) -> CaseEvent:
    """Record the outcome the Operator chose for a reply, dated the day it came (or ``on``).

    ``outcome`` is one of ``lifecycle.OUTCOMES``, or ``"attach_only"`` to keep the reply on the
    Case without recording an outcome. ``details`` go to ``services.record_outcome``.
    """
    if reply.case_id is None:
        raise services.CaseError("Assign the reply to a Case first.")
    if reply.status != Reply.Status.TO_CONFIRM:
        raise services.CaseError("This reply was already dealt with.")
    on = on or reply.received_on
    with transaction.atomic():
        if outcome == ATTACH_ONLY:
            event = services.add_note(
                reply.case,
                f"Reply from {reply.from_address or 'the Organization'} attached ({reply.subject_line}).",
                on=on,
                details={"reply": reply.pk},
            )
        else:
            event = services.record_outcome(reply.case, outcome, on=on, reply=reply.pk, **details)
        _finish(reply, event, Reply.Status.CONFIRMED)
        reply.save()
    return event


def assign(reply: Reply, case: Case) -> Reply:
    """Put an unmatched reply on one of its Subject's Cases; it then gets the usual treatment."""
    if case.subject_id != reply.subject_id:
        raise services.CaseError("A reply can only go to a Case of the same Subject.")
    if not reply.is_unmatched:
        raise services.CaseError("Only a reply in the unmatched queue can be assigned.")
    raw = storage.read_file(reply.raw_path) if reply.raw_path else b""
    message = parse_bytes(raw)
    written: list[str] = []
    old_path = reply.raw_path
    try:
        with transaction.atomic():
            reply.case, reply.matched_by = case, Reply.MatchedBy.OPERATOR
            reply.suggested_outcome = reply.suggestion_source = reply.suggestion_note = ""
            reply.suggested_exception = ""
            reply.suggested_suppression = reply.suggested_with_reasons = None
            reply.raw_path = reply.raw_sha256 = ""
            reply.save()
            _store_case_files(reply, raw, message, written)
            _decide(reply)
            reply.save()
    except Exception:
        _cleanup(written)
        raise
    storage.delete_file(old_path)
    return reply


def dismiss(reply: Reply) -> Reply:
    """Drop a reply: its text and files are deleted; the headers stay so it is not taken in again."""
    if reply.status != Reply.Status.TO_CONFIRM:
        raise services.CaseError("This reply was already dealt with.")
    with transaction.atomic():
        attachments = list(reply.attachments.all())
        reply.raw_attachment = None
        storage.delete_file(reply.raw_path)
        reply.raw_path = reply.raw_sha256 = ""
        reply.body = ""
        reply.status, reply.decided_at = Reply.Status.DISMISSED, timezone.now()
        reply.save()
        for attachment in attachments:
            storage.delete_attachment(attachment)
    return reply


def reply_attachments(reply: Reply) -> list[Attachment]:
    """The files that came with a reply, without its ``.eml``."""
    return [attachment for attachment in reply.attachments.all() if attachment.pk != reply.raw_attachment_id]
