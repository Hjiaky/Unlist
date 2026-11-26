# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Re-checks (spec section 8, ticket #51): a resting Case asks again with a fresh Access Request.

- ``prepare_due_rechecks`` (a scheduler job) drafts the fresh Access Request of every resting
  Case whose ``recheck_on`` has come. The draft waits for approval; nothing is sent.
- The intervals are ``lifecycle.recheck_intervals`` (Brokers 90 days after "removed" or "nothing
  held"; others 365 days after "removed" and none after "nothing held"; overridable per
  Organization or Case). ``reschedule`` moves the date of a resting Case when its override changes.
- Never earlier than the interval (``services.prepare_recheck`` refuses), unless the Operator asks
  with a reason (``early_recheck``). An incomplete answer is not a re-check: it is recorded as
  "refused or partly done" and followed up from there (a reconsider reply or a Complaint).
- ``early_recheck_suggestion``: mail from the Organization newer than its "nothing held" or
  "removed" answer suggests an early re-check. It only suggests; the Operator decides.
- ``returned_listing``: a Listing found at a Broker that had confirmed a Suppression Record. The
  lifecycle then also offers a Complaint draft.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from unlist.cases.drafting import format_date
from unlist.cases.lifecycle import State
from unlist.cases.models import CaseEvent
from unlist.core.scheduler import job

log = logging.getLogger("unlist.cases")

# The answers that put a Case to rest, and the interval each one uses.
RESTING_KINDS = (CaseEvent.Kind.NOTHING_HELD, CaseEvent.Kind.REMOVED, CaseEvent.Kind.REFUSAL_ACCEPTED)
NO_RECHECK = 'no re-check: the re-check setting is "close"'

_SAID = {
    CaseEvent.Kind.NOTHING_HELD: "it holds nothing",
    CaseEvent.Kind.REMOVED: "it removed the Subject's data",
    CaseEvent.Kind.REFUSAL_ACCEPTED: "it removed part of the Subject's data",
}


@dataclass(frozen=True)
class Suggestion:
    last_seen: date
    answered_on: date
    text: str


def _today(on):
    return on or timezone.localdate()


def resting_event(case) -> CaseEvent | None:
    """The answer that put a resting Case to rest; None if the Case is not resting."""
    if case.state != State.RESTING:
        return None
    for event in case.events.order_by("-occurred_on", "-recorded_at", "-id"):
        if event.kind in RESTING_KINDS and event.details.get("state") == State.RESTING:
            return event
    return None


def interval_for(case, event) -> int | None:
    """Days from the resting event to the re-check, by the Case's current intervals; None closes."""
    from unlist.cases import services

    after_nothing, after_removed = services.recheck_intervals(case)
    return after_nothing if event.kind == CaseEvent.Kind.NOTHING_HELD else after_removed


def reschedule(case, *, on: date | None = None) -> date | None:
    """Work out a resting Case's ``recheck_on`` again from the day it came to rest.

    Called when the Case's re-check override changes. With no re-check left (``"close"``, or no
    interval after "nothing held"), the Case closes. Returns the new date, or None.
    """
    from unlist.cases import services

    event = resting_event(case)
    if event is None:
        return None
    days = interval_for(case, event)
    if days is None:
        services.stop(case, on=on, reason=NO_RECHECK)
        return None
    new = event.occurred_on + timedelta(days=days)
    if new != case.recheck_on:
        old = case.recheck_on
        case.recheck_on = new
        case.save(update_fields=["recheck_on", "updated_at"])
        before = f" from {format_date(old, 'en')}" if old else ""
        services._record(
            case,
            CaseEvent.Kind.NOTE,
            _today(on),
            f"Re-check setting changed: the re-check moves{before} to {format_date(new, 'en')}.",
            details={"recheck_on": new.isoformat()},
        )
    return new


def early_recheck(case, reason: str, *, on: date | None = None):
    """The Operator asks for a re-check before its date, with a reason. Returns the draft."""
    from unlist.cases import services

    reason = " ".join((reason or "").split())
    if not reason:
        raise services.CaseError("Say why the re-check should come early.")
    return services.prepare_recheck(case, on=on, reason=reason)


def early_recheck_suggestion(case, *, today: date | None = None) -> Suggestion | None:
    """Mail from the Organization newer than the answer that put the Case to rest, if any."""
    from unlist.mail.models import Discovery

    event = resting_event(case)
    if event is None or (case.recheck_on and case.recheck_on <= _today(today)):
        return None
    discovery = Discovery.objects.filter(subject_id=case.subject_id, organization_id=case.organization_id).first()
    if discovery is None or discovery.last_seen is None:
        return None
    seen = timezone.localdate(discovery.last_seen)
    if seen <= event.occurred_on:
        return None
    text = f"New mail from this Organization since it said {_SAID[event.kind]}. Re-check early?"
    return Suggestion(last_seen=seen, answered_on=event.occurred_on, text=text)


def returned_listing(case) -> CaseEvent | None:
    """For a Listing found after a confirmed Suppression Record: that confirmation; else None."""
    if case.state != State.LISTING_FOUND:
        return None
    return case.events.filter(suppression_confirmed=True).order_by("-occurred_on", "-id").first()


@job
def prepare_due_rechecks(now):
    """Draft the fresh Access Request of every resting Case whose re-check date has come.

    The drafts wait for the Operator's approval; nothing is sent. Cases of a Subject without
    active consent are skipped (their Cases are stopped on withdrawal anyway).
    """
    from unlist.cases import services
    from unlist.cases.models import Case

    today = timezone.localdate(now) if timezone.is_aware(now) else now.date()
    prepared = failed = 0
    cases = Case.objects.filter(state=State.RESTING, recheck_on__lte=today).select_related("subject", "organization")
    for case in cases:
        if not case.subject.has_active_consent():
            continue
        try:
            with transaction.atomic():
                services.prepare_recheck(case, on=today)
            prepared += 1
        except Exception:  # one Case must not stop the others; the Operator sees it still resting
            failed += 1
            log.exception("Could not prepare the re-check of Case %s", case.reference)
    if not prepared and not failed:
        return None
    summary = f"{prepared} re-check(s) prepared for approval."
    return summary + (f" {failed} could not be prepared (see the log)." if failed else "")
