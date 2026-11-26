# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Scheduler jobs of the Cases app. They prepare work; they never send anything."""

import logging

from django.utils import timezone

from unlist.core.scheduler import job

log = logging.getLogger("unlist.cases")


@job
def mark_overdue_cases(now):
    """Mark waiting Cases overdue once their deadline plus grace has passed, and suggest a reminder.

    A reminder is suggested (a draft awaiting approval) only for the first missed deadline of a
    request; after a reminder, the next step is the Operator's (a Complaint draft).
    """
    from unlist.cases import services
    from unlist.cases.lifecycle import State
    from unlist.cases.models import Case

    today = timezone.localdate(now) if timezone.is_aware(now) else now.date()
    marked = suggested = 0
    for case in Case.objects.filter(state=State.WAITING, overdue_from__lte=today).select_related(
        "subject", "organization"
    ):
        if not services.mark_overdue_if_due(case, today=today):
            continue
        marked += 1
        if services.reminders_sent(case) == 0 and case.subject.has_active_consent():
            try:
                services.send_reminder(case, on=today)
                suggested += 1
            except Exception:  # one Case must not stop the others; the Operator can still prepare it
                log.exception("Could not prepare a reminder for Case %s", case.reference)
    if not marked:
        return None
    return f"{marked} Case(s) overdue, {suggested} reminder(s) prepared for approval."
