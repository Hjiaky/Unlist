# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Mail import: scan messages and record which Organizations mailed a Subject (spec section 5).

- `scan_messages(subject, messages)` takes any iterable of `email.message.Message` (full
  messages from an mbox, or headers fetched over IMAP) and updates the Subject's
  Discoveries and UnassignedSenders. It is the entry point a live IMAP scan reuses.
- `import_mbox(subject, upload)` stores an uploaded `.mbox` file (Google Takeout included)
  in a temporary file inside the data directory, streams it through `scan_messages` and
  deletes it afterwards.

Mapping, per sender: a shared (ambiguous) domain becomes an UnassignedSender per display
name, unless the Operator assigned that sender before. Otherwise the domain maps through
the merged Organization Lists (`lookup.by_domain`, which tries parent domains). An unknown
domain with account evidence or better becomes a local stub; any other unknown domain
becomes an UnassignedSender. "Ignored" is kept across scans, and a message counted once
(by Message-ID) is not counted again by a later import.
"""

import datetime
import hashlib
import logging
import mailbox
import os
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path

from django.db import connections, transaction
from django.utils import timezone

from unlist import paths
from unlist.mail import psl, scanner
from unlist.mail.models import Discovery, ImportRun, SeenMessage, UnassignedSender
from unlist.organizations import lookup, services

log = logging.getLogger("unlist.mail")

# Scans of large uploads outlive a web request, so the upload view runs them in a thread.
RUN_IN_BACKGROUND = True
PROGRESS_EVERY = 500  # messages between progress saves
STALE_AFTER = datetime.timedelta(days=1)
COUNT_FIELDS = [
    "total",
    "authenticated",
    "personal_skipped",
    "unauthenticated_skipped",
    "spam_skipped",
    "duplicates",
    "errors",
]


def import_dir():
    """Where uploads wait to be scanned: inside the data directory, never the system temp directory."""
    return Path(paths.DATA_DIR) / "mail-import"


@dataclass
class Tally:
    """What a batch of messages says about one sender."""

    count: int = 0
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None
    evidence: str = scanner.NONE
    subject: str = ""
    subject_date: datetime.datetime | None = None
    display_name: str = ""
    display_date: datetime.datetime | None = None

    def _take_evidence(self, evidence, subject, date):
        rank, mine = scanner.evidence_rank(evidence), scanner.evidence_rank(self.evidence)
        later = date is not None and (self.subject_date is None or date > self.subject_date)
        if rank < mine or (rank == mine and (later or not self.subject)):
            self.evidence, self.subject, self.subject_date = evidence, subject, date

    def _take_dates(self, first, last):
        if first is not None and (self.first_seen is None or first < self.first_seen):
            self.first_seen = first
        if last is not None and (self.last_seen is None or last > self.last_seen):
            self.last_seen = last

    def add(self, result):
        self.count += 1
        self._take_dates(result.date, result.date)
        self._take_evidence(result.evidence, result.subject, result.date)
        if result.display_name and (
            not self.display_name or (result.date and (self.display_date is None or result.date > self.display_date))
        ):
            self.display_name, self.display_date = result.display_name, result.date

    def merge(self, other):
        self.count += other.count
        self._take_dates(other.first_seen, other.last_seen)
        self._take_evidence(other.evidence, other.subject, other.subject_date)
        if other.display_name and (
            not self.display_name
            or (other.display_date and (self.display_date is None or other.display_date > self.display_date))
        ):
            self.display_name, self.display_date = other.display_name, other.display_date

    def apply_to(self, row):
        """Add this tally to a Discovery or UnassignedSender (not saved)."""
        row.email_count += self.count
        if self.first_seen is not None and (row.first_seen is None or self.first_seen < row.first_seen):
            row.first_seen = self.first_seen
        if self.last_seen is not None and (row.last_seen is None or self.last_seen > row.last_seen):
            row.last_seen = self.last_seen
        rank, current = scanner.evidence_rank(self.evidence), scanner.evidence_rank(row.evidence)
        if rank < current or (rank == current and self.subject and not row.strongest_subject):
            row.evidence, row.strongest_subject = self.evidence, self.subject


def tally_of(row):
    """A Discovery's or UnassignedSender's totals as a Tally, to move them elsewhere."""
    return Tally(
        count=row.email_count,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
        evidence=row.evidence,
        subject=row.strongest_subject,
        subject_date=row.last_seen,
    )


def message_digest(result):
    """A short digest identifying a message across imports: its Message-ID, else sender, date and subject."""
    if result.message_id:
        key = "id:" + result.message_id.strip().strip("<>").lower()
    else:
        key = f"hdr:{result.sender_address}\n{result.date.isoformat() if result.date else ''}\n{result.subject}"
    return hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()[:32]


def add_to_discovery(subject, organization, tally):
    discovery, _ = Discovery.objects.get_or_create(subject=subject, organization=organization)
    tally.apply_to(discovery)
    discovery.save()
    return discovery


def scan_messages(subject, messages, *, run=None, mailbox=None, source=ImportRun.Source.MBOX):
    """Scan an iterable of messages for `subject` and record what they show. Returns the ImportRun.

    An item that is None (a message the caller could not read) is counted as an error. The
    run's counts are saved as the scan goes; the Discoveries are written at the end.
    """
    if run is None:
        run = ImportRun.objects.create(subject=subject, mailbox=mailbox, source=source)
    own_addresses = frozenset(email.lower() for email in subject.mailboxes.values_list("email", flat=True))
    seen = set(SeenMessage.objects.filter(subject=subject).values_list("digest", flat=True))
    new_digests = []
    tallies = {}  # (host, display name for a shared domain, else None) -> Tally
    shared = {}  # host -> is_ambiguous

    for message in messages:
        run.total += 1
        try:
            if message is None:
                raise ValueError("unreadable message")
            result = scanner.scan(message, own_addresses)
        except Exception:  # one broken message must not stop the import
            log.debug("Could not scan a message", exc_info=True)
            run.errors += 1
            continue
        if result.skip == scanner.SKIP_PERSONAL:
            run.personal_skipped += 1
        elif result.skip == scanner.SKIP_UNAUTHENTICATED:
            run.unauthenticated_skipped += 1
        elif result.skip == scanner.SKIP_SPAM:
            run.spam_skipped += 1
        elif result.skip is not None:
            run.errors += 1
        else:
            run.authenticated += 1
            digest = message_digest(result)
            if digest in seen:
                run.duplicates += 1
            else:
                seen.add(digest)
                new_digests.append(digest)
                host = result.sender_host
                if host not in shared:
                    shared[host] = lookup.is_ambiguous(host)
                key = (host, result.display_name if shared[host] else None)
                tallies.setdefault(key, Tally()).add(result)
        if run.total % PROGRESS_EVERY == 0:
            run.save(update_fields=COUNT_FIELDS)

    with transaction.atomic():
        _record(subject, tallies)
        SeenMessage.objects.bulk_create(
            [SeenMessage(subject=subject, digest=digest) for digest in new_digests],
            batch_size=1000,
            ignore_conflicts=True,
        )
        run.finished_at = timezone.now()
        run.save()
    return run


def _record(subject, tallies):
    found = {}  # Organization pk -> (Organization, Tally)
    unknown = {}  # registrable domain -> Tally
    on_shared = {}  # (registrable domain, display name) -> Tally

    def to_organization(organization, tally):
        found.setdefault(organization.pk, (organization, Tally()))[1].merge(tally)

    for (host, display_name), tally in tallies.items():
        domain = psl.registrable_domain(host) or host
        if display_name is not None:
            on_shared.setdefault((domain, display_name), Tally()).merge(tally)
            continue
        organization = lookup.by_domain(host)
        if organization is not None:
            to_organization(organization, tally)
        else:
            unknown.setdefault(domain, Tally()).merge(tally)

    for (domain, display_name), tally in on_shared.items():
        sender, _ = UnassignedSender.objects.get_or_create(
            subject=subject, domain=domain, display_name=display_name, defaults={"ambiguous": True}
        )
        if sender.status == UnassignedSender.Status.ASSIGNED and sender.organization is None:
            sender.status = UnassignedSender.Status.OPEN  # the Organization it was assigned to is gone
        tally.apply_to(sender)
        sender.save()
        if sender.status == UnassignedSender.Status.ASSIGNED:
            to_organization(sender.organization, tally)

    for domain, tally in unknown.items():
        sender = UnassignedSender.objects.filter(subject=subject, domain=domain, ambiguous=False).first()
        if sender is not None and sender.status == UnassignedSender.Status.ASSIGNED and sender.organization is None:
            sender.status = UnassignedSender.Status.OPEN  # the Organization it was assigned to is gone
        if sender is not None and sender.status == UnassignedSender.Status.IGNORED:
            tally.apply_to(sender)
            sender.save()
            continue
        if sender is not None and sender.status == UnassignedSender.Status.ASSIGNED and sender.organization:
            to_organization(sender.organization, tally)
            continue
        if tally.evidence in scanner.ACCOUNT_OR_BETTER:
            try:
                organization = services.create_stub(domain)
            except ValueError:
                log.info("No local stub for %s: domain in conflict", domain)
            else:
                if sender is not None:  # move what earlier imports recorded for it
                    tally.merge(tally_of(sender))
                    sender.status, sender.organization = UnassignedSender.Status.ASSIGNED, organization
                    sender.save()
                to_organization(organization, tally)
                continue
        if sender is None:
            sender = UnassignedSender(subject=subject, domain=domain, ambiguous=False)
        if tally.display_name:
            sender.display_name = tally.display_name[:200]
        tally.apply_to(sender)
        sender.save()

    for organization, tally in found.values():
        add_to_discovery(subject, organization, tally)


# mbox files -----------------------------------------------------------------------------


def _messages(box):
    """Each message of an mbox in file order, None for one that cannot be read. Streams the file."""
    for key in box.iterkeys():
        try:
            yield box.get_message(key)
        except Exception:  # counted as an error by scan_messages
            log.debug("Could not read message %s", key, exc_info=True)
            yield None


def store_upload(upload):
    """Put an uploaded file into a new temporary file in the data directory; return its path."""
    directory = import_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{secrets.token_hex(12)}.mbox"
    source = getattr(upload, "temporary_file_path", None)
    if source is not None:
        try:
            os.link(source(), target)  # already on disk in the data directory: no second copy
            return target
        except OSError:
            pass
    with open(target, "xb") as out:
        for chunk in upload.chunks():
            out.write(chunk)
    return target


def scan_mbox_file(run, path):
    """Scan the mbox at `path` into `run`, then delete the file, whatever happens."""
    try:
        from unlist.cases.replies import ingest_each  # takes in replies to Cases on the way; never raises (#49)

        box = mailbox.mbox(path, create=False)
        try:
            scan_messages(run.subject, ingest_each(run.subject, _messages(box)), run=run)
        finally:
            box.close()
    except Exception as error:
        log.exception("mbox import %s failed", run.pk)
        run.failure = f"The import stopped: {error.__class__.__name__}: {error}"[:2000]
        run.save()
    finally:
        Path(path).unlink(missing_ok=True)


def _scan_in_thread(run_pk, path):
    try:
        run = ImportRun.objects.select_related("subject").get(pk=run_pk)
        scan_mbox_file(run, path)
    finally:
        Path(path).unlink(missing_ok=True)
        connections.close_all()


def clean_up_stale(now=None):
    """Remove uploads and mark runs left behind by a restart in the middle of an import."""
    now = now or timezone.now()
    ImportRun.objects.filter(finished_at__isnull=True, failure="", started_at__lt=now - STALE_AFTER).update(
        failure="The import was interrupted (Unlist restarted). Import the file again."
    )
    directory = import_dir()
    if directory.is_dir():
        cutoff = now.timestamp() - STALE_AFTER.total_seconds()
        for path in directory.iterdir():
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass


def import_mbox(subject, upload, *, mailbox=None, background=None):
    """Import an uploaded mbox for `subject`. Returns the ImportRun, finished unless run in the background."""
    clean_up_stale()
    path = store_upload(upload)
    run = ImportRun.objects.create(
        subject=subject,
        mailbox=mailbox,
        source=ImportRun.Source.MBOX,
        filename=os.path.basename(getattr(upload, "name", "") or "")[:255],
    )
    if RUN_IN_BACKGROUND if background is None else background:
        threading.Thread(target=_scan_in_thread, args=(run.pk, path), name=f"mbox-import-{run.pk}", daemon=True).start()
    else:
        scan_mbox_file(run, path)
        run.refresh_from_db()
    return run
