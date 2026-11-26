# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from datetime import date

from unlist.cases import services
from unlist.organizations.models import Organization
from unlist.subjects.consent import record_consent
from unlist.subjects.models import Mailbox, Subject

# A Monday in the past: mark_sent refuses dates in the future.
DAY0 = date(2025, 3, 3)


def make_subject(name="Alex Example", email="alex@example.org", mode=Mailbox.Mode.IMPORT, consent=True):
    subject = Subject.objects.create(name=name, country="DE")
    Mailbox.objects.create(subject=subject, email=email, mode=mode)
    if consent:
        record_consent(subject, "subject")
    return subject


def make_organization(slug="acme", name="ACME Ltd", *, broker=False, email="privacy@acme.example", **fields):
    fields.setdefault("relevant_countries", ["de"])
    fields.setdefault("quality", "verified")
    return Organization.objects.create(slug=slug, name=name, broker=broker, email=email, **fields)


def send(case, on):
    """Approve the pending draft and mark it sent on the same day (import-only mode)."""
    draft = case.pending_draft
    services.approve(draft, on=on)
    services.mark_sent(draft, on=on)
    case.refresh_from_db()
    return draft
