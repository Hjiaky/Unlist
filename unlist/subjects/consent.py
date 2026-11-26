# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Consent rules. Other apps call `require_consent` before drafting anything for a Subject."""

from django.utils import timezone

CONSENT_SCOPE_VERSION = "1"
CONSENT_SCOPE = (
    "Import the Subject's mail; send Access Requests and Removal Requests from the Subject's address "
    "(each approved by the Operator first); read and store the replies; draft Complaints."
)

# Callables `f(subject, consent)` run after consent is withdrawn. Later apps (cases) register here to stop open Cases.
on_withdrawn = []


class ConsentRequired(Exception):
    """Raised when something is drafted for a Subject who has no active consent."""

    def __init__(self, subject):
        self.subject = subject
        super().__init__(f"{subject.name} has no active consent; nothing may be drafted until it is recorded.")


def require_consent(subject):
    """Raise `ConsentRequired` unless the Subject has active consent."""
    if not subject.has_active_consent():
        raise ConsentRequired(subject)


def record_consent(subject, given_by, now=None):
    """Record that the Subject (or a parent) agreed to the current scope. Returns the active Consent."""
    from unlist.subjects.models import Consent

    active = subject.consents.filter(withdrawn_at__isnull=True).first()
    if active:
        return active
    return Consent.objects.create(
        subject=subject,
        given_by=given_by,
        given_at=now or timezone.now(),
        scope=f"v{CONSENT_SCOPE_VERSION}: {CONSENT_SCOPE}",
    )


def withdraw_consent(subject, now=None):
    """Withdraw all active consent, then run the `on_withdrawn` hooks. Returns the withdrawn Consents."""
    now = now or timezone.now()
    withdrawn = list(subject.consents.filter(withdrawn_at__isnull=True))
    for consent in withdrawn:
        consent.withdrawn_at = now
        consent.save(update_fields=["withdrawn_at"])
    for consent in withdrawn:
        for hook in list(on_withdrawn):
            hook(subject, consent)
    return withdrawn
