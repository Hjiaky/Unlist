# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""A Case is one Subject at one Organization (spec section 4).

The rules live in ``lifecycle.py`` and the steps in ``services.py``; change a Case only through
the services, so that every change is checked and leaves a dated ``CaseEvent``.
"""

import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from unlist.cases import lifecycle
from unlist.cases.lifecycle import State

_RECHECK_OVERRIDE = re.compile(r"^(close|[1-9][0-9]{0,4})?$")


def validate_recheck_override(value):
    if not _RECHECK_OVERRIDE.fullmatch(value or ""):
        raise ValidationError('Enter a number of days, "close", or leave it empty for the default.')


class Case(models.Model):
    STATE_CHOICES = [(state.value, lifecycle.STATE_LABELS[state]) for state in State]
    REQUEST_CHOICES = [("access", "Access Request"), ("removal", "Removal Request")]

    subject = models.ForeignKey("subjects.Subject", on_delete=models.CASCADE, related_name="cases")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="cases")
    reference = models.CharField(max_length=12, unique=True, help_text="Short code in every subject line, e.g. U-7KQ3.")
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=State.FOUND)
    request = models.CharField(
        max_length=10, choices=REQUEST_CHOICES, blank=True, help_text="The request in flight, if any."
    )
    result = models.CharField(max_length=200, blank=True, help_text="The last outcome, in plain words.")
    direct_removal = models.BooleanField(
        default=False, help_text="Request removal directly instead of asking first (an Access Request)."
    )
    recheck_override = models.CharField(
        max_length=10,
        blank=True,
        validators=[validate_recheck_override],
        help_text='Days between re-checks, or "close" for none. Empty: the Organization\'s default.',
    )
    recheck_on = models.DateField(null=True, blank=True, help_text="When a resting Case is re-checked.")
    # Cached from the events by services.refresh_deadline, for querying; recomputed on every event.
    due_date = models.DateField(null=True, blank=True)
    overdue_from = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["subject", "organization"], name="one_case_per_subject_and_organization")
        ]

    def __str__(self):
        return f"{self.reference}: {self.subject} at {self.organization}"

    @property
    def state_label(self):
        return lifecycle.STATE_LABELS[State(self.state)]

    @property
    def state_text(self):
        return lifecycle.STATE_TEXT[State(self.state)]

    @property
    def next_actor(self):
        return lifecycle.NEXT_ACTOR[State(self.state)]

    @property
    def is_open(self):
        return self.state not in (State.RESTING, State.CLOSED)

    @property
    def pending_draft(self):
        return self.drafts.filter(status__in=Draft.PENDING).order_by("-id").first()


class CaseEvent(models.Model):
    class Kind(models.TextChoices):
        OPENED = "opened", "Case opened"
        DRAFTED = "drafted", "Draft prepared"
        APPROVED = "approved", "Draft approved"
        DISCARDED = "discarded", "Draft discarded"
        SENT = "sent", "Sent"
        NOTHING_HELD = "nothing_held", "Nothing held"
        LISTING_FOUND = "listing_found", "Listing found"
        REMOVED = "removed", "Removed"
        REFUSED = "refused", "Refused or partly done"
        ID_OR_DETAILS_ASKED = "id_or_details_asked", "ID or details asked"
        EXTENSION_ANNOUNCED = "extension_announced", "Extension announced"
        BOUNCE = "bounce", "Bounced"
        LISTING_KEPT = "listing_kept", "Listing kept"
        REFUSAL_ACCEPTED = "refusal_accepted", "Refusal accepted"
        OVERDUE = "overdue", "Overdue"
        COMPLAINT_DRAFTED = "complaint_drafted", "Complaint drafted"
        COMPLAINT_LODGED = "complaint_lodged", "Complaint lodged"
        STOPPED = "stopped", "Stopped"
        REOPENED = "reopened", "Reopened"
        RECHECK_DUE = "recheck_due", "Re-check due"
        NOTE = "note", "Note"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    occurred_on = models.DateField(help_text="The day it happened (for an answer: the day it arrived).")
    recorded_at = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict, blank=True)
    exception_text = models.TextField(blank=True, help_text="For a refusal: the exception the Organization cites.")
    suppression_confirmed = models.BooleanField(
        null=True, blank=True, help_text="For a removal: whether a Suppression Record was confirmed."
    )

    class Meta:
        ordering = ["occurred_on", "recorded_at", "id"]

    def __str__(self):
        return f"{self.occurred_on}: {self.get_kind_display()}"

    @property
    def text(self):
        return self.details.get("text", "")


class Draft(models.Model):
    """One email (or web-form text, or letter) prepared for a Case. Nothing leaves before approval."""

    class Status(models.TextChoices):
        AWAITING_APPROVAL = "awaiting_approval", "Awaiting approval"
        APPROVED = "approved", "Approved"
        HANDED_OVER = "handed_over", "Handed over"
        SENT = "sent", "Sent"
        DISCARDED = "discarded", "Discarded"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WEBFORM = "webform", "Web form"
        LETTER = "letter", "Letter"

    PENDING = (Status.AWAITING_APPROVAL, Status.APPROVED, Status.HANDED_OVER)
    KIND_CHOICES = [(kind.value, lifecycle.DRAFT_NAMES[kind]) for kind in lifecycle.DraftKind]

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="drafts")
    kind = models.CharField(max_length=30, choices=KIND_CHOICES, help_text="The mail template kind.")
    lang = models.CharField(max_length=10)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    recipient = models.TextField(help_text="Email address, web-form URL or postal address.")
    sender = models.CharField(max_length=254, help_text="The Subject's address the draft is sent from.")
    subject_line = models.CharField(max_length=500)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_APPROVAL)
    return_state = models.CharField(
        max_length=20, choices=Case.STATE_CHOICES, help_text="The Case's state before the draft, for discarding."
    )
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_on = models.DateField(null=True, blank=True)
    message_id = models.CharField(max_length=300, blank=True, help_text="Set on approval; used to match replies.")

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.case.reference}"

    @property
    def is_pending(self):
        return self.status in self.PENDING


class Attachment(models.Model):
    """A file kept as evidence: a reply's ``.eml``, a letter scan. Never an ID document (spec section 7)."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="attachments")
    event = models.ForeignKey(CaseEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments")
    original_name = models.CharField(max_length=255)
    stored_path = models.CharField(max_length=500, help_text="Relative to the data directory.")
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["uploaded_at", "id"]

    def __str__(self):
        return self.original_name
