# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Optional live IMAP scans (spec section 5): read-only, headers only, incremental.

How a scan reads a mailbox:

- TLS always (``IMAP4_SSL`` with the default SSL context, so the certificate and host name are
  verified), then ``LOGIN`` with the app password.
- Folder rule: if the server's ``LIST`` marks a folder with the RFC 6154 special-use attribute
  ``\\All`` (Gmail's ``[Gmail]/All Mail``, whatever its localized name), only that folder is
  scanned: it "presents all messages in the user's message store", INBOX included, so scanning
  INBOX as well would fetch every inbox message twice. Without an ``\\All`` folder, INBOX is
  scanned. Gmail's All Mail leaves out Spam and Trash, which discovery skips anyway.
- The folder is opened with ``EXAMINE`` (read-only), never ``SELECT``. Headers are fetched with
  ``BODY.PEEK[HEADER.FIELDS (...)]``, which never sets ``\\Seen``.
- Incremental: the folder's ``UIDVALIDITY`` and the highest UID scanned are kept on the
  connection; the next scan fetches only higher UIDs. A changed ``UIDVALIDITY`` (or folder)
  means the UIDs no longer mean the same messages, so the folder is scanned again from the
  start; ``scan_messages`` does not count a message twice (it remembers Message-IDs).
- Replies: a message that looks like an answer to one of the Subject's Cases (it refers to a
  sent draft's Message-ID, names a Case reference, or comes from an Organization with an open
  Case, sent after that Case was opened) is fetched in full with ``BODY.PEEK[]`` and handed to
  ``unlist.cases.replies.ingest_message``. Mail from the Subject's own addresses never is.

Nothing here runs unless the Operator pressed "Scan now" or switched scheduled re-scans on.
"""

import datetime
import email
import email.policy
import imaplib
import logging
import re
import ssl
import threading

from django.db import connections
from django.utils import timezone

from unlist import crypto
from unlist.mail import psl, scanner
from unlist.mail.importer import scan_messages
from unlist.mail.models import ImportRun

log = logging.getLogger("unlist.mail")

TIMEOUT = 60  # seconds per network operation
BATCH = 500  # headers per UID FETCH
FULL_BATCH = 20  # full messages per UID FETCH
RUN_IN_BACKGROUND = True  # "Scan now" runs in a thread; tests switch it off
REPLY_SLACK = datetime.timedelta(days=1)  # clock skew allowed before a Case was opened

HEADER_FIELDS = (
    "From Sender Reply-To Date Subject Message-ID In-Reply-To References List-Id List-Unsubscribe "
    "List-Unsubscribe-Post Precedence Auto-Submitted Authentication-Results Content-Type X-Gmail-Labels"
)
HEADER_FETCH = f"(BODY.PEEK[HEADER.FIELDS ({HEADER_FIELDS})])"
FULL_FETCH = "(BODY.PEEK[])"

AUTH_FAILED = (
    "The provider refused the user name and app password. Check that IMAP is turned on for the "
    "account and that you entered an app password (created in the account's security settings), "
    "not the normal account password. If the provider does not offer app passwords, disconnect "
    "and use file import instead: export the mailbox as an .mbox file and upload it. Outlook.com "
    "and Microsoft 365 generally require OAuth for IMAP, which Unlist does not use, so import "
    "their mail from a file."
)

_LIST_LINE = re.compile(rb'^\((?P<flags>[^)]*)\)\s+(?P<delimiter>"(?:[^"\\]|\\.)*"|NIL)\s*(?P<name>.*)$', re.I)
_LITERAL = re.compile(rb"\{\d+\}$")
_UID = re.compile(rb"\bUID (\d+)", re.I)
_MESSAGE_ID = re.compile(r"<[^<>\s]+>")
_REFERENCE = re.compile(r"\bU-[0-9A-Z]{4,}\b")


class ConnectionProblem(Exception):
    """A problem with the mailbox connection, as one plain sentence for the Operator."""


class AuthenticationFailed(ConnectionProblem):
    pass


def network_problem(error, what, host, port):
    """A plain sentence for a network, TLS or protocol error."""
    if isinstance(error, ssl.SSLCertVerificationError):
        return (
            f"The {what} server {host}:{port} sent a certificate that could not be verified "
            f"({error.verify_message or error}). Check the host name."
        )
    if isinstance(error, ssl.SSLError):
        return f"TLS with the {what} server {host}:{port} failed: {error}. Check the port and security setting."
    if isinstance(error, TimeoutError):
        return f"The {what} server {host}:{port} did not answer in time."
    if isinstance(error, OSError):
        return f"Could not reach the {what} server {host}:{port}: {error.strerror or error}."
    return f"The {what} server {host}:{port} refused a command: {error}."


def stored_password(connection):
    try:
        return connection.password()
    except (crypto.MissingKey, crypto.WrongKey) as error:
        raise ConnectionProblem(f"The stored app password cannot be read ({error}) Enter it again.") from error


# Connecting -----------------------------------------------------------------------------


def open_imap(connection, password=None):
    """Connect over TLS and log in. Returns the client. Raises ConnectionProblem."""
    host, port = connection.imap_host, connection.imap_port
    password = stored_password(connection) if password is None else password
    try:
        client = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=TIMEOUT)
    except (OSError, imaplib.IMAP4.error) as error:
        raise ConnectionProblem(network_problem(error, "IMAP", host, port)) from error
    try:
        client.login(connection.username, password)
    except UnicodeEncodeError as error:
        logout(client)
        raise ConnectionProblem("IMAP allows only ASCII characters in the user name and password here.") from error
    except imaplib.IMAP4.abort as error:
        logout(client)
        raise ConnectionProblem(network_problem(error, "IMAP", host, port)) from error
    except imaplib.IMAP4.error as error:
        logout(client)
        raise AuthenticationFailed(AUTH_FAILED) from error
    except OSError as error:
        logout(client)
        raise ConnectionProblem(network_problem(error, "IMAP", host, port)) from error
    return client


def logout(client):
    try:
        client.logout()
    except Exception:  # the connection may already be gone
        log.debug("IMAP logout failed", exc_info=True)


def test_login(connection, password=None):
    """Log in and out again, nothing else. Raises ConnectionProblem."""
    logout(open_imap(connection, password))


# Folders and fetching -------------------------------------------------------------------


def quote(name):
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote(raw):
    raw = raw.strip()
    if raw.startswith(b'"') and raw.endswith(b'"') and len(raw) >= 2:
        raw = re.sub(rb"\\(.)", rb"\1", raw[1:-1])
    return raw.decode("ascii", errors="replace")  # modified UTF-7 is ASCII


def all_mail_folder(client):
    """The name of the folder LIST marks ``\\All`` (RFC 6154), or None."""
    try:
        typ, data = client.list()
    except imaplib.IMAP4.error:
        return None
    if typ != "OK":
        return None
    for item in data or []:
        literal = None
        if isinstance(item, tuple):  # the name came as a literal
            item, literal = item[0], item[1]
        if not isinstance(item, bytes):
            continue
        match = _LIST_LINE.match(item.strip())
        if not match:
            continue
        flags = match["flags"].lower().split()
        if b"\\all" in flags and b"\\noselect" not in flags:
            if literal is not None and _LITERAL.search(match["name"]):
                return literal.decode("ascii", errors="replace")
            return _unquote(match["name"])
    return None


def choose_folder(client):
    return all_mail_folder(client) or "INBOX"


def examine(client, folder):
    """Open the folder read-only. Returns (message count, UIDVALIDITY or None)."""
    typ, data = client.select(quote(folder), readonly=True)  # imaplib sends EXAMINE for readonly
    if typ != "OK":
        detail = (data[0] if data and data[0] else b"").decode("utf-8", errors="replace")
        raise ConnectionProblem(f"The IMAP server would not open {folder} read-only: {detail}")
    try:
        exists = int(data[0])
    except (TypeError, ValueError, IndexError):
        exists = 0
    _, values = client.response("UIDVALIDITY")
    try:
        uidvalidity = int(values[0])
    except (TypeError, ValueError, IndexError):
        uidvalidity = None
    return exists, uidvalidity


def uids_after(client, last_uid):
    """UIDs above ``last_uid``, ascending. (``n:*`` also matches the highest UID when it is below n.)"""
    typ, data = client.uid("SEARCH", f"UID {last_uid + 1}:*")
    if typ != "OK":
        raise ConnectionProblem("The IMAP server refused to list new messages.")
    found = set()
    for item in data or []:
        if isinstance(item, bytes):
            found.update(int(token) for token in item.split() if token.isdigit())
    return sorted(uid for uid in found if uid > last_uid)


def parse_fetch(data):
    """(uid, bytes) for each message literal in a UID FETCH response."""
    pending = None
    for item in data or []:
        if isinstance(item, tuple) and len(item) >= 2:
            match = _UID.search(item[0])
            if match:
                yield int(match[1]), item[1]
                pending = None
            else:
                pending = item[1]  # the UID may follow the literal
        elif isinstance(item, bytes) and pending is not None:
            match = _UID.search(item)
            if match:
                yield int(match[1]), pending
            pending = None


def sequence_set(uids):
    """A compact IMAP sequence set for ascending UIDs: ``[1, 2, 3, 7]`` becomes ``1:3,7``."""
    parts = []
    start = previous = None
    for uid in uids:
        if previous is not None and uid == previous + 1:
            previous = uid
            continue
        if start is not None:
            parts.append(str(start) if start == previous else f"{start}:{previous}")
        start = previous = uid
    if start is not None:
        parts.append(str(start) if start == previous else f"{start}:{previous}")
    return ",".join(parts)


def fetch(client, uids, items, *, batch=None):
    """Yield (uid, bytes) for ``uids`` (ascending), fetched in batches with ``items``."""
    batch = batch or BATCH
    for start in range(0, len(uids), batch):
        chunk = uids[start : start + batch]
        wanted = set(chunk)
        typ, data = client.uid("FETCH", sequence_set(chunk), items)
        if typ != "OK":
            raise ConnectionProblem("The IMAP server refused to send messages.")
        for uid, raw in parse_fetch(data):
            if uid in wanted:
                yield uid, raw


# Replies --------------------------------------------------------------------------------


def reply_ingester():
    """``unlist.cases.replies.ingest_message``, or None while that module does not exist."""
    try:
        from unlist.cases.replies import ingest_message
    except ImportError:
        return None
    return ingest_message


def _normal_id(value):
    return value.strip().strip("<>").strip().lower()


class ReplyCandidates:
    """Decides from headers alone whether a message may answer one of the Subject's Cases."""

    def __init__(self, subject, own_addresses):
        from unlist.cases.lifecycle import State
        from unlist.cases.models import Case, Draft

        self.own_addresses = own_addresses
        self.message_ids = {
            _normal_id(value)
            for value in Draft.objects.filter(case__subject=subject)
            .exclude(message_id="")
            .values_list("message_id", flat=True)
        }
        cases = Case.objects.filter(subject=subject)
        self.references = {reference.upper() for reference in cases.values_list("reference", flat=True)}
        self.domains = {}  # registrable domain -> when the earliest open Case there was opened
        for case in cases.exclude(state=State.CLOSED).select_related("organization"):
            organization = case.organization
            hosts = list(organization.domains or [])
            if "@" in (organization.email or ""):
                hosts.append(organization.email.rpartition("@")[2])
            for host in hosts:
                domain = psl.registrable_domain(host)
                if domain and (domain not in self.domains or case.created_at < self.domains[domain]):
                    self.domains[domain] = case.created_at

    def __bool__(self):
        return bool(self.message_ids or self.references or self.domains)

    def match(self, message):
        _, address = scanner._sender(message)
        if not address or address in self.own_addresses:
            return False
        threads = " ".join(scanner._header_text(message.get(name)) for name in ("In-Reply-To", "References"))
        if any(_normal_id(value) in self.message_ids for value in _MESSAGE_ID.findall(threads)):
            return True
        subject = scanner._header_text(message.get("Subject")).upper()
        if any(reference in self.references for reference in _REFERENCE.findall(subject)):
            return True
        opened = self.domains.get(psl.registrable_domain(address.rpartition("@")[2]))
        date = scanner._date(message)
        return opened is not None and date is not None and date >= opened - REPLY_SLACK


def ingest_replies(client, subject, uids, ingest):
    """Fetch candidate replies in full and hand them over. Returns (errors, first UID not done or None)."""
    errors = 0
    done = set()
    try:
        for uid, raw in fetch(client, uids, FULL_FETCH, batch=FULL_BATCH):
            done.add(uid)
            try:
                message = email.message_from_bytes(raw, policy=email.policy.default)
                ingest(subject, message, source="imap", raw=raw)
            except Exception:  # one reply the Cases app cannot read must not stop the scan
                log.exception("Could not ingest a reply over IMAP (UID %s)", uid)
                errors += 1
    except (OSError, imaplib.IMAP4.error, ConnectionProblem):
        log.warning("The IMAP connection failed while fetching replies", exc_info=True)
        missing = [uid for uid in uids if uid not in done]
        return errors, (missing[0] if missing else None)
    return errors, None


# Scanning -------------------------------------------------------------------------------


def _scan(client, connection, run):
    mailbox = connection.mailbox
    subject = mailbox.subject
    folder = choose_folder(client)
    exists, uidvalidity = examine(client, folder)
    last_uid = connection.last_uid
    if folder != connection.folder or uidvalidity is None or uidvalidity != connection.uidvalidity:
        last_uid = 0  # first scan, another folder, or the UIDs were renumbered: start again
    uids = uids_after(client, last_uid) if exists else []
    run.filename = folder[:255]

    ingest = reply_ingester()
    own = frozenset(email_address.lower() for email_address in subject.mailboxes.values_list("email", flat=True))
    candidates = ReplyCandidates(subject, own) if ingest is not None else None
    if candidates is not None and not candidates:
        candidates = None
    to_ingest = []

    def messages():
        for uid, raw in fetch(client, uids, HEADER_FETCH):
            message = email.message_from_bytes(raw)
            if candidates is not None and candidates.match(message):
                to_ingest.append(uid)
            yield message

    scan_messages(subject, messages(), run=run, mailbox=mailbox, source=ImportRun.Source.IMAP)

    highest = max(uids, default=last_uid)
    reply_errors, stopped_at = ingest_replies(client, subject, to_ingest, ingest) if to_ingest else (0, None)
    if stopped_at is not None:
        highest = stopped_at - 1  # fetch the rest again next time; discovery does not count twice

    connection.folder = folder
    connection.uidvalidity = uidvalidity
    connection.last_uid = highest
    connection.save(update_fields=["folder", "uidvalidity", "last_uid"])
    run.errors += reply_errors
    run.save(update_fields=["errors", "filename"])
    if stopped_at is not None:
        raise ConnectionProblem("The connection failed while fetching replies; the next scan continues from there.")
    return len(to_ingest)


def scan_connection(connection, *, run=None, now=None):
    """Scan a live mailbox once. Returns the ImportRun; on failure its ``failure`` says why.

    The problem is also kept on the connection (``last_error``) for the Operator.
    """
    mailbox = connection.mailbox
    connection.last_attempt_at = now or timezone.now()
    connection.save(update_fields=["last_attempt_at"])
    if run is None:
        run = ImportRun.objects.create(subject=mailbox.subject, mailbox=mailbox, source=ImportRun.Source.IMAP)
    host, port = connection.imap_host, connection.imap_port
    try:
        client = open_imap(connection)
        try:
            _scan(client, connection, run)
        finally:
            logout(client)
    except ConnectionProblem as error:
        problem = str(error)
    except (OSError, imaplib.IMAP4.error) as error:
        problem = network_problem(error, "IMAP", host, port)
    except Exception as error:
        log.exception("IMAP scan of %s failed", mailbox)
        problem = f"The scan stopped: {error.__class__.__name__}: {error}"
    else:
        connection.last_scan_at = timezone.now()
        connection.last_error = ""
        connection.save(update_fields=["last_scan_at", "last_error"])
        return run
    run.failure = problem[:2000]
    run.save(update_fields=["failure"])
    connection.record_error(problem)
    return run


def is_running(connection):
    """Whether a scan of this mailbox has started and not finished (stale runs are cleaned up elsewhere)."""
    return ImportRun.objects.filter(
        mailbox=connection.mailbox, source=ImportRun.Source.IMAP, finished_at__isnull=True, failure=""
    ).exists()


def _scan_in_thread(connection_pk, run_pk):
    from unlist.mail.models import MailboxConnection

    try:
        connection = MailboxConnection.objects.select_related("mailbox__subject").get(pk=connection_pk)
        scan_connection(connection, run=ImportRun.objects.get(pk=run_pk))
    except Exception:
        log.exception("IMAP scan thread failed")
    finally:
        connections.close_all()


def start_scan(connection, *, background=None):
    """Start a scan the Operator asked for. Returns the ImportRun (finished unless run in the background)."""
    from unlist.mail.importer import clean_up_stale

    clean_up_stale()
    mailbox = connection.mailbox
    run = ImportRun.objects.create(subject=mailbox.subject, mailbox=mailbox, source=ImportRun.Source.IMAP)
    if RUN_IN_BACKGROUND if background is None else background:
        threading.Thread(
            target=_scan_in_thread, args=(connection.pk, run.pk), name=f"imap-scan-{run.pk}", daemon=True
        ).start()
        return run
    scan_connection(connection, run=run)
    run.refresh_from_db()
    return run
