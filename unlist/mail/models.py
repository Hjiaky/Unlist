# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""What discovery keeps (spec section 5): per Subject and Organization, never a mail body."""

from django.db import models
from django.utils import timezone

from unlist.mail import scanner
from unlist.organizations.models import Organization
from unlist.subjects.models import Mailbox, Subject


class Evidence(models.TextChoices):
    ORDER_MARKUP = scanner.ORDER_MARKUP, "Order or booking markup"
    TRANSACTION = scanner.TRANSACTION, "Order, receipt, invoice or shipping"
    ACCOUNT = scanner.ACCOUNT, "Account notice"
    BULK = scanner.BULK, "Newsletter or other bulk mail"
    NONE = scanner.NONE, "Unsorted"


class Discovery(models.Model):
    """One Organization that mailed one Subject, with the strongest evidence seen."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        PURSUED = "pursued", "Pursued"
        IGNORED = "ignored", "Ignored"

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="discoveries")
    # An Organization that drops off every list is deleted by the merge (unless a Case keeps
    # it); its discoveries go with it.
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="discoveries")
    first_seen = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    email_count = models.PositiveIntegerField(default=0)
    evidence = models.CharField(max_length=20, choices=Evidence.choices, default=Evidence.NONE)
    strongest_subject = models.CharField(max_length=scanner.SUBJECT_MAX, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "discoveries"
        constraints = [
            models.UniqueConstraint(fields=["subject", "organization"], name="discovery_unique_per_subject"),
        ]

    def __str__(self):
        return f"{self.organization} for {self.subject}"


class UnassignedSender(models.Model):
    """Mail from a shared (ambiguous) or unknown domain, waiting for the Operator to assign it.

    For a shared domain the display name is part of the key (one row per sender on the
    platform); for an unknown domain there is one row per domain and the display name is
    the latest one seen.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        IGNORED = "ignored", "Ignored"

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="unassigned_senders")
    domain = models.CharField(max_length=253)
    display_name = models.CharField(max_length=200, blank=True)
    ambiguous = models.BooleanField(default=False, help_text="A shared mail or platform domain.")
    email_count = models.PositiveIntegerField(default=0)
    first_seen = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    evidence = models.CharField(max_length=20, choices=Evidence.choices, default=Evidence.NONE)
    strongest_subject = models.CharField(max_length=scanner.SUBJECT_MAX, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="Assigned to."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["domain", "display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "domain", "display_name"], name="unassigned_sender_unique_per_subject"
            ),
        ]

    def __str__(self):
        return f"{self.display_name} <{self.domain}>" if self.display_name else self.domain


class ImportRun(models.Model):
    """One scan of an mbox upload (or, later, of an IMAP mailbox)."""

    class Source(models.TextChoices):
        MBOX = "mbox", "mbox upload"
        IMAP = "imap", "IMAP"

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="import_runs")
    mailbox = models.ForeignKey(Mailbox, null=True, blank=True, on_delete=models.SET_NULL, related_name="import_runs")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MBOX)
    filename = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    total = models.PositiveIntegerField(default=0)
    authenticated = models.PositiveIntegerField(default=0)
    personal_skipped = models.PositiveIntegerField(default=0)
    unauthenticated_skipped = models.PositiveIntegerField(default=0)
    spam_skipped = models.PositiveIntegerField(default=0, help_text="Spam and Trash in a Google Takeout export.")
    duplicates = models.PositiveIntegerField(default=0, help_text="Already counted by an earlier import.")
    errors = models.PositiveIntegerField(default=0)
    failure = models.TextField(blank=True, help_text="Why the run stopped, if it did not finish.")

    class Meta:
        ordering = ["-started_at", "-id"]

    def __str__(self):
        return f"Import for {self.subject} at {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def running(self):
        return self.finished_at is None and not self.failure


class SeenMessage(models.Model):
    """A digest of a counted message's Message-ID, so a later import does not count it twice."""

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="+")
    digest = models.CharField(max_length=32)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["subject", "digest"], name="seen_message_unique_per_subject")]


class MailboxConnection(models.Model):
    """An optional live connection to one of a Subject's mailboxes (spec sections 5 and 6).

    IMAP is read-only (``EXAMINE``, headers fetched with ``BODY.PEEK``); SMTP sends approved
    drafts from the Subject's own address. The app password is stored encrypted with
    ``unlist.crypto``; everything else stays readable. Deleting the connection (or the
    Mailbox) forgets the password.
    """

    class Security(models.TextChoices):
        SSL = "ssl", "SSL/TLS"
        STARTTLS = "starttls", "STARTTLS"

    mailbox = models.OneToOneField(Mailbox, on_delete=models.CASCADE, related_name="connection")
    imap_host = models.CharField(max_length=253)
    imap_port = models.PositiveIntegerField(default=993)
    smtp_host = models.CharField(max_length=253)
    smtp_port = models.PositiveIntegerField(default=465, help_text="465 (SSL/TLS) or 587 (STARTTLS).")
    smtp_security = models.CharField(max_length=10, choices=Security.choices, default=Security.SSL)
    username = models.CharField(max_length=320)
    password_encrypted = models.TextField(help_text="The app password, encrypted with the instance key.")
    scheduled_rescans = models.BooleanField(default=False, help_text="Re-scan on its own, at most every 6 hours.")
    folder = models.CharField(max_length=500, blank=True, help_text="The folder the UID state below belongs to.")
    uidvalidity = models.PositiveBigIntegerField(null=True, blank=True)
    last_uid = models.PositiveBigIntegerField(default=0, help_text="The highest UID scanned in that folder.")
    last_scan_at = models.DateTimeField(null=True, blank=True, help_text="When the last scan finished.")
    last_attempt_at = models.DateTimeField(null=True, blank=True, help_text="When a scan last started.")
    last_error = models.TextField(blank=True, help_text="The last problem with IMAP or SMTP, for the Operator.")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Live connection for {self.mailbox}"

    def set_password(self, password):
        from unlist import crypto

        self.password_encrypted = crypto.encrypt(password)

    def password(self):
        """The app password. Raises ``crypto.MissingKey`` or ``crypto.WrongKey``."""
        from unlist import crypto

        return crypto.decrypt(self.password_encrypted)

    def record_error(self, message):
        self.last_error = message[:2000]
        self.save(update_fields=["last_error"])
