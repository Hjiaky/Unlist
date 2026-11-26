# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Everything that changes a Case. Views, the scheduler and later tickets call these.

Each service checks the step against the rules (``lifecycle.py``), stores a dated ``CaseEvent``,
prepares any draft the step needs, and recomputes the Case's cached deadline. An illegal step
raises ``IllegalStep`` with the reason in plain words and changes nothing.

``on`` is the day the step happened (for an answer: the day it arrived). It defaults to today.

Nothing here sends anything by itself. A draft leaves only through ``approve`` (which may hand it
to a registered live sender, see ``sending.py``) and is marked sent only through ``mark_sent``,
which needs a draft that was approved and handed over.
"""

import logging
import secrets
from collections.abc import Callable
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from unlist.cases import deadlines, drafting, lifecycle, sending, templating
from unlist.cases.lifecycle import Action, DraftKind, Request, State
from unlist.cases.models import Case, CaseEvent, Draft
from unlist.subjects.consent import require_consent

log = logging.getLogger("unlist.cases")

REFERENCE_PREFIX = "U-"
# No 0/O, 1/I: the code is read and typed by people.
REFERENCE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

# Sends that start a deadline round: the requests, and a reconsider reply (which asks for an
# answer within one month).
ROUND_STARTS = (DraftKind.ACCESS_REQUEST, DraftKind.REMOVAL_REQUEST, DraftKind.RECONSIDER)

# Callables `case -> None`, run after a Case moves to "Complaint draft". The Complaints ticket
# registers the one that writes the Complaint; until then the state alone is recorded.
complaint_drafters: list[Callable[[Case], None]] = []


class CaseError(Exception):
    """A step that cannot be taken. The message is meant for the Operator."""


class IllegalStep(CaseError):
    """The rules do not allow this step in the Case's current state."""


class ContactNotConfirmed(CaseError):
    pass


class NoContact(CaseError):
    pass


class NoMailbox(CaseError):
    pass


class CaseExists(CaseError):
    def __init__(self, case):
        self.case = case
        super().__init__(
            f"{case.subject} already has a Case at {case.organization} ({case.reference}). Reopen it instead."
        )


# --- Reading a Case ----------------------------------------------------------------------


def _today(on: date | None) -> date:
    return on or timezone.localdate()


def _events(case) -> list[CaseEvent]:
    return list(case.events.order_by("occurred_on", "recorded_at", "id"))


def _sent_kind(event) -> str | None:
    return event.details.get("draft_kind") if event.kind == CaseEvent.Kind.SENT else None


def reminders_sent(case) -> int:
    """Reminders sent since the current request (an Access or Removal Request) was sent."""
    count = 0
    for event in _events(case):
        kind = _sent_kind(event)
        if kind in (DraftKind.ACCESS_REQUEST, DraftKind.REMOVAL_REQUEST):
            count = 0
        elif kind == DraftKind.REMINDER:
            count += 1
    return count


def _current_round(events: list[CaseEvent]) -> list[CaseEvent]:
    """The events from the latest send of a request (or reconsider reply) on; empty if none was sent."""
    start = None
    for index, event in enumerate(events):
        if _sent_kind(event) in ROUND_STARTS:
            start = index
    return [] if start is None else events[start:]


# Case events that pause the clock, and what the paused Case then waits for.
ASK_EVENTS = {
    CaseEvent.Kind.ID_OR_DETAILS_ASKED: lifecycle.ASKED_ID_OR_DETAILS,
    CaseEvent.Kind.CLARIFICATION_ASKED: lifecycle.ASKED_CLARIFICATION,
}


def demands(case) -> tuple[str | None, bool]:
    """(what the open question asks for, whether an ID pushback was sent) in the current round."""
    asked, pushed_back = None, False
    for event in _current_round(_events(case)):
        if event.kind in ASK_EVENTS:
            asked = ASK_EVENTS[event.kind]
        elif _sent_kind(event) in lifecycle.ANSWERS:
            asked = None
            pushed_back = pushed_back or _sent_kind(event) == DraftKind.ID_PUSHBACK
    return asked, pushed_back


def recheck_intervals(case) -> tuple[int | None, int | None]:
    organization = case.organization
    return lifecycle.recheck_intervals(organization.broker, organization.recheck_default, case.recheck_override or None)


def case_state(case) -> lifecycle.CaseState:
    """The Case as the rules see it."""
    pending = case.pending_draft
    after_nothing, after_removed = recheck_intervals(case)
    asked, pushed_back = demands(case)
    return lifecycle.CaseState(
        state=State(case.state),
        request=Request(case.request) if case.request else None,
        draft=DraftKind(pending.kind) if pending else None,
        draft_back=State(pending.return_state) if pending else None,
        reminders=reminders_sent(case),
        broker=case.organization.broker,
        direct_removal=case.direct_removal,
        recheck_after_nothing=after_nothing,
        recheck_after_removed=after_removed,
        result=case.result,
        asked=asked,
        pushed_back=pushed_back,
    )


CASE_ACTIONS = (
    Action.PREPARE_REQUEST,
    Action.REQUEST_REMOVAL,
    Action.KEEP_LISTING,
    Action.SEND_DETAILS,
    Action.PUSH_BACK,
    Action.SEND_ID,
    Action.FIX_CONTACT,
    Action.SEND_REMINDER,
    Action.DRAFT_COMPLAINT,
    Action.COMPLAINT_LODGED,
    Action.ACCEPT_REFUSAL,
    Action.ASK_RECONSIDER,
    Action.REOPEN,
    Action.STOP,
)


def available_actions(case) -> list[Action]:
    """The Case-level steps (buttons) legal right now."""
    return lifecycle.allowed(case_state(case), CASE_ACTIONS)


def available_outcomes(case) -> list[Action]:
    """The answers from the Organization that can be recorded right now."""
    return lifecycle.allowed(case_state(case), lifecycle.OUTCOMES)


def _deadline_input(case):
    """(request kind, deadline events) of the current round, or None when no clock runs.

    A round starts with the latest send of a request (or reconsider reply). A bounce after it
    means the Organization never received it, so the clock never started.
    """
    current = _current_round(_events(case))
    if not current:
        return None
    if any(event.kind == CaseEvent.Kind.BOUNCE for event in current[1:]):
        return None
    first_kind = DraftKind(_sent_kind(current[0]))
    kind = lifecycle.DRAFT_REQUEST.get(first_kind, Request.REMOVAL)
    result = [deadlines.Event(deadlines.EventKind.SENT, current[0].occurred_on)]
    open_ask = None  # the deadline engine's kind of the question an answer replies to
    for event in current[1:]:
        sent_kind = _sent_kind(event)
        if sent_kind == DraftKind.REMINDER:
            result.append(deadlines.Event(deadlines.EventKind.REMINDER_SENT, event.occurred_on))
        elif sent_kind in lifecycle.ANSWERS:
            answer = (
                deadlines.EventKind.CLARIFICATION_ANSWERED
                if open_ask is deadlines.EventKind.CLARIFICATION_ASKED
                else deadlines.EventKind.ID_OR_DETAILS_ANSWERED
            )
            result.append(deadlines.Event(answer, event.occurred_on))
            open_ask = None
        elif event.kind == CaseEvent.Kind.ID_OR_DETAILS_ASKED:
            open_ask = deadlines.EventKind.ID_OR_DETAILS_ASKED
            result.append(deadlines.Event(open_ask, event.occurred_on))
        elif event.kind == CaseEvent.Kind.CLARIFICATION_ASKED:
            open_ask = deadlines.EventKind.CLARIFICATION_ASKED
            result.append(deadlines.Event(open_ask, event.occurred_on))
        elif event.kind == CaseEvent.Kind.EXTENSION_ANNOUNCED:
            result.append(
                deadlines.Event(
                    deadlines.EventKind.EXTENSION_ANNOUNCED,
                    event.occurred_on,
                    with_reasons=bool(event.details.get("with_reasons")),
                )
            )
    return kind, result


def case_deadline(case) -> deadlines.Deadline | None:
    """The deadline of the Case's current request, worked out from its events; None if nothing was sent."""
    found = _deadline_input(case)
    if found is None:
        return None
    kind, events = found
    organization = case.organization
    return deadlines.compute_deadline(
        drafting.jurisdiction_for(organization), drafting.country_for(organization), events, kind=kind
    )


def effective_overdue_from(deadline: deadlines.Deadline | None) -> date | None:
    """When the Case counts as overdue: after a reminder, its 14 days plus grace; else the legal one plus grace."""
    if deadline is None or deadline.paused:
        return None
    if deadline.reminder_due_date:
        return deadline.reminder_due_date + timedelta(days=deadlines.GRACE_DAYS)
    return deadline.overdue_from


def refresh_deadline(case) -> deadlines.Deadline | None:
    """Recompute the cached ``due_date`` and ``overdue_from`` from the events."""
    deadline = case_deadline(case)
    if deadline is not None and case.state in lifecycle.CLOCK_STATES:
        case.due_date, case.overdue_from = deadline.due_date, effective_overdue_from(deadline)
    else:
        case.due_date = case.overdue_from = None
    case.save(update_fields=["due_date", "overdue_from", "updated_at"])
    return deadline


# --- Drafting ----------------------------------------------------------------------------


def new_reference() -> str:
    """A short unique code such as ``U-7KQ3``; longer if the short ones run out."""
    for attempt in range(40):
        length = 4 + attempt // 10
        code = REFERENCE_PREFIX + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(length))
        if not Case.objects.filter(reference=code).exists():
            return code
    raise CaseError("Could not find a free reference code.")


def _sender(subject) -> str:
    mailbox = subject.mailboxes.order_by("id").first()
    if mailbox is None:
        raise NoMailbox(f"{subject} has no email address yet. Add one before anything is drafted.")
    return mailbox.email


def _check_contact(organization) -> tuple[str, str]:
    if not organization.contact_confirmed:
        raise ContactNotConfirmed(
            f"The contact of {organization} has not been confirmed. Confirm it on the Organization's page (add it "
            "as a local override) before the first request."
        )
    channel, recipient = drafting.choose_channel(organization)
    if not recipient:
        raise NoContact(f"Unlist knows no email address, web form or postal address for {organization}. Add one first.")
    return channel, recipient


def _round_start_draft(case) -> tuple[Draft | None, CaseEvent | None]:
    start = None
    for event in _events(case):
        if _sent_kind(event) in ROUND_STARTS:
            start = event
    if start is None:
        return None, None
    return case.drafts.filter(pk=start.details.get("draft")).first(), start


def _context(case, kind: DraftKind, lang: str, jurisdiction: str, sender: str, extra: dict) -> dict:
    subject, organization = case.subject, case.organization
    context = {
        "jurisdiction": jurisdiction,
        "reference": case.reference,
        "subject_name": subject.name,
        "subject_email": sender,
        "organization_name": organization.name,
        "is_broker": organization.broker,
    }
    if kind in (DraftKind.ACCESS_REQUEST, DraftKind.REMOVAL_REQUEST):
        context["identifying_details"] = drafting.identifying_lines(organization, list(subject.details.all()), lang)
    if kind is DraftKind.REMOVAL_REQUEST:
        context["erasure_grounds"] = list(extra.get("erasure_grounds") or drafting.DEFAULT_ERASURE_GROUNDS)
        if extra.get("objection_grounds"):
            context["objection_grounds"] = extra["objection_grounds"]
    if kind is DraftKind.REMINDER:
        original, sent_event = _round_start_draft(case)
        deadline = case_deadline(case)
        original_kind = original.kind if original else DraftKind.ACCESS_REQUEST
        if original_kind not in templating.ORIGINAL_KINDS:
            original_kind = DraftKind.REMOVAL_REQUEST
        context.update(
            original_kind=str(original_kind),
            original_date=drafting.format_date(sent_event.occurred_on if sent_event else None, lang),
            deadline_date=drafting.format_date(deadline.due_date if deadline else None, lang),
            original_body=original.body if original else "",
        )
    if kind is DraftKind.RECONSIDER:
        refusal = case.events.filter(kind=CaseEvent.Kind.REFUSED).order_by("-occurred_on", "-id").first()
        if refusal:
            context.update(
                refusal_date=drafting.format_date(refusal.occurred_on, lang), cited_exception=refusal.exception_text
            )
    if kind is DraftKind.DETAILS_REPLY:
        details = extra.get("details") or drafting.identifying_lines(organization, list(subject.details.all()), lang)
        if details:
            context["details"] = list(details)
    if kind is DraftKind.ID_PUSHBACK and extra.get("offered_details"):
        context["offered_details"] = list(extra["offered_details"])
    return context


def _create_draft(case, kind: DraftKind, return_state: State, extra: dict | None = None) -> Draft:
    require_consent(case.subject)
    sender = _sender(case.subject)
    channel, recipient = _check_contact(case.organization)
    jurisdiction = drafting.jurisdiction_for(case.organization)
    lang = templating.template_language(kind, drafting.request_language(case.organization), jurisdiction)
    subject_line, body = templating.render(kind, lang, _context(case, kind, lang, jurisdiction, sender, extra or {}))
    return Draft.objects.create(
        case=case,
        kind=kind,
        lang=lang,
        channel=channel,
        recipient=recipient,
        sender=sender,
        subject_line=subject_line,
        body=body,
        return_state=return_state,
    )


# --- The step machinery ------------------------------------------------------------------


def _record(case, kind, on, text="", *, details=None, exception_text="", suppression_confirmed=None) -> CaseEvent:
    return CaseEvent.objects.create(
        case=case,
        kind=kind,
        occurred_on=on,
        details={"text": text, "state": case.state, **(details or {})},
        exception_text=exception_text or "",
        suppression_confirmed=suppression_confirmed,
    )


def _step(
    case,
    action: Action,
    on: date,
    *,
    event_kind,
    details=None,
    exception_text="",
    suppression_confirmed=None,
    draft_extra=None,
    **transition_args,
):
    """Check and apply one step. Returns (transition, event, new draft or None)."""
    before = case_state(case)
    if action is Action.REMOVED:
        transition_args["suppression_confirmed"] = bool(suppression_confirmed)
    result = lifecycle.transition(before, action, **transition_args)
    if not result.ok:
        raise IllegalStep(result.error)
    if result.discarded_draft:
        case.drafts.filter(status__in=Draft.PENDING).update(status=Draft.Status.DISCARDED)
    after = result.case
    case.state = after.state
    case.request = after.request or ""
    case.result = after.result
    if result.recheck_in_days is not None:
        case.recheck_on = on + timedelta(days=result.recheck_in_days)
    elif after.state is not State.RESTING:
        case.recheck_on = None
    case.save()
    draft = None
    if result.new_draft:
        draft = _create_draft(case, result.new_draft, before.state, draft_extra)
        details = {**(details or {}), "draft": draft.pk, "draft_kind": str(draft.kind)}
    event = _record(
        case,
        event_kind,
        on,
        result.text,
        details=details,
        exception_text=exception_text,
        suppression_confirmed=suppression_confirmed,
    )
    refresh_deadline(case)
    return result, event, draft


def _draft_step(case, action, on, event_kind=CaseEvent.Kind.DRAFTED, **extra) -> Draft:
    with transaction.atomic():
        require_consent(case.subject)
        _result, _event, draft = _step(case, action, _today(on), event_kind=event_kind, draft_extra=extra)
        return draft


def _sent_details(draft) -> dict:
    details = {
        "draft": draft.pk,
        "draft_kind": str(draft.kind),
        "channel": draft.channel,
        "recipient": draft.recipient,
        "message_id": draft.message_id,
    }
    if draft.kind in lifecycle.DRAFT_REQUEST:
        details["request"] = str(lifecycle.DRAFT_REQUEST[DraftKind(draft.kind)])
    return details


def _approved_on(draft) -> date:
    """The day the draft was approved, as recorded on the Case (the ``on`` given to ``approve``)."""
    for event in reversed(_events(draft.case)):
        if event.kind == CaseEvent.Kind.APPROVED and event.details.get("draft") == draft.pk:
            return event.occurred_on
    return timezone.localdate(draft.approved_at)


def _check_pending(draft):
    pending = draft.case.pending_draft
    if pending is None or pending.pk != draft.pk:
        raise IllegalStep("This draft is no longer the Case's pending draft.")


# --- Public services ---------------------------------------------------------------------


def open_case(subject, organization, *, direct_removal: bool = False, on: date | None = None) -> Case:
    """Open a Case for a Subject at an Organization and draft its first request.

    The first draft is an Access Request (ask, then delete), or a Removal Request when
    ``direct_removal``. Raises ``ConsentRequired`` without active consent, ``ContactNotConfirmed``
    for a scraped record or stub whose contact the Operator has not confirmed, ``NoContact``,
    ``NoMailbox``, or ``CaseExists``.
    """
    on = _today(on)
    require_consent(subject)
    existing = Case.objects.filter(subject=subject, organization=organization).first()
    if existing:
        raise CaseExists(existing)
    _check_contact(organization)
    _sender(subject)
    with transaction.atomic():
        case = Case.objects.create(
            subject=subject, organization=organization, reference=new_reference(), direct_removal=direct_removal
        )
        how = "removal directly" if direct_removal else "an Access Request first"
        _record(case, CaseEvent.Kind.OPENED, on, f"Case opened for {subject} at {organization}, asking {how}.")
        prepare_request(case, on=on)
    return case


def prepare_request(case, *, on: date | None = None) -> Draft:
    """Draft the Case's request (Access, or Removal for direct removal) when nothing is in flight."""
    return _draft_step(case, Action.PREPARE_REQUEST, on)


def approve(draft, *, on: date | None = None) -> Draft:
    """Approve a draft. A registered live sender may send it; otherwise it is handed over to the Subject."""
    on = _today(on)
    case = draft.case
    with transaction.atomic():
        require_consent(case.subject)
        if draft.status != Draft.Status.AWAITING_APPROVAL:
            raise IllegalStep("Only a draft awaiting approval can be approved.")
        _check_pending(draft)
        state = case_state(case)
        if not lifecycle.can(state, Action.APPROVE):
            raise IllegalStep(lifecycle.transition(state, Action.APPROVE).error)
        draft.status = Draft.Status.APPROVED
        draft.approved_at = timezone.now()
        if draft.channel == Draft.Channel.EMAIL:
            draft.message_id = sending.new_message_id(draft.sender)
        draft.save()
        sent = sending.try_live_send(draft)
        if sent:
            _record(case, CaseEvent.Kind.APPROVED, on, "Approved by the Operator.", details={"draft": draft.pk})
            _step(case, Action.APPROVE, on, event_kind=CaseEvent.Kind.SENT, details=_sent_details(draft), sent=True)
            draft.status, draft.sent_on = Draft.Status.SENT, on
            draft.save()
        else:
            draft.status = Draft.Status.HANDED_OVER
            draft.save()
            _step(case, Action.APPROVE, on, event_kind=CaseEvent.Kind.APPROVED, details={"draft": draft.pk})
    return draft


def discard(draft, *, on: date | None = None) -> Draft:
    """Drop a pending draft; the Case goes back to where it was before the draft."""
    with transaction.atomic():
        if not draft.is_pending:
            raise IllegalStep("This draft is not pending.")
        _check_pending(draft)
        _step(draft.case, Action.DISCARD, _today(on), event_kind=CaseEvent.Kind.DISCARDED, details={"draft": draft.pk})
    draft.refresh_from_db()
    return draft


def mark_sent(draft, *, on: date | None = None) -> Draft:
    """The Subject sent a handed-over draft on ``on``: record it and start (or move) the clock."""
    on = _today(on)
    with transaction.atomic():
        if draft.status != Draft.Status.HANDED_OVER or draft.approved_at is None:
            raise IllegalStep("Only a draft that was approved and handed over can be marked sent.")
        _check_pending(draft)
        if on > timezone.localdate():
            raise CaseError("The send date cannot be in the future.")
        if on < _approved_on(draft):
            raise CaseError("The send date cannot be before the day the draft was approved.")
        draft.status, draft.sent_on = Draft.Status.SENT, on
        _step(draft.case, Action.MARK_SENT, on, event_kind=CaseEvent.Kind.SENT, details=_sent_details(draft))
        draft.save()
        if draft.kind == DraftKind.ID_COPY_REPLY:
            _record(
                draft.case,
                CaseEvent.Kind.ID_SENT,
                on,
                f"ID sent on {deadlines.format_date(on)}. The Subject attached it from their own device; Unlist "
                "keeps no copy.",
                details={"draft": draft.pk},
            )
    return draft


def record_outcome(case, outcome: Action | str, *, on: date | None = None, **details) -> CaseEvent:
    """Record an answer from the Organization (or a bounce).

    ``outcome`` is one of ``lifecycle.OUTCOMES``: ``nothing_held``, ``listing_found``, ``removed``
    (``suppression_confirmed=bool``), ``refused`` (``exception="..."``: the exception it cites),
    ``id_or_details_asked``, ``clarification_asked`` (which data an Access Request is about),
    ``extension_announced`` (``with_reasons=bool``) or ``bounce``. Other keyword arguments (JSON
    values, such as ``note`` or ``reply``) are stored in the event's details.
    """
    try:
        action = Action(outcome)
    except ValueError:
        action = None
    if action not in lifecycle.OUTCOMES:
        raise CaseError(f"Unknown outcome {outcome!r}.")
    on = _today(on)
    exception = ""
    suppression = None
    if action is Action.REMOVED:
        suppression = bool(details.pop("suppression_confirmed", False))
    if action is Action.REFUSED:
        exception = (details.pop("exception", "") or details.pop("exception_text", "") or "").strip()
    if action is Action.EXTENSION_ANNOUNCED:
        details["with_reasons"] = bool(details.get("with_reasons", False))
    with transaction.atomic():
        _result, event, _draft = _step(
            case,
            action,
            on,
            event_kind=action.value,
            details=details,
            exception_text=exception,
            suppression_confirmed=suppression,
        )
        if action is Action.EXTENSION_ANNOUNCED:
            deadline = case_deadline(case)
            decision = deadline.extensions[-1] if deadline and deadline.extensions else None
            if decision is not None:
                if decision.accepted:
                    event.details["extension"] = "accepted"
                    due = deadlines.format_date(deadline.due_date)
                    event.details["text"] += f" It counts: the deadline is now {due}."
                else:
                    event.details["extension"] = f"ignored: {decision.ignored_reason}"
                    event.details["text"] += " It does not count, so the deadline stays as it was."
                event.save(update_fields=["details"])
    return event


def keep_listing(case, *, on: date | None = None) -> CaseEvent:
    """The Subject keeps the Listing (still a customer): close, no re-check."""
    with transaction.atomic():
        return _step(case, Action.KEEP_LISTING, _today(on), event_kind=CaseEvent.Kind.LISTING_KEPT)[1]


def request_removal(case, *, on: date | None = None, erasure_grounds=None, objection_grounds="") -> Draft:
    """After a Listing was found: draft a Removal Request (asking a Broker for a Suppression Record)."""
    return _draft_step(
        case, Action.REQUEST_REMOVAL, on, erasure_grounds=erasure_grounds, objection_grounds=objection_grounds
    )


def accept_refusal(case, *, on: date | None = None) -> CaseEvent:
    """Accept a refusal: a refused Removal Request rests until the re-check, a refused Access Request closes."""
    with transaction.atomic():
        return _step(case, Action.ACCEPT_REFUSAL, _today(on), event_kind=CaseEvent.Kind.REFUSAL_ACCEPTED)[1]


def ask_reconsider(case, *, on: date | None = None) -> Draft:
    """After a refused Removal Request: draft a reply asking the Organization to reconsider."""
    return _draft_step(case, Action.ASK_RECONSIDER, on)


def send_reminder(case, *, on: date | None = None) -> Draft:
    """For an overdue Case: draft a polite reminder (gentle first)."""
    return _draft_step(case, Action.SEND_REMINDER, on)


def send_details(case, details: list[str] | None = None, *, on: date | None = None) -> Draft:
    """For a paused Case: draft a reply with the details asked for (default: those the Organization's quirks name)."""
    return _draft_step(case, Action.SEND_DETAILS, on, details=details)


def push_back(case, *, on: date | None = None, offered_details: list[str] | None = None) -> Draft:
    """For a paused Case with an ID demand: draft the pushback."""
    return _draft_step(case, Action.PUSH_BACK, on, offered_details=offered_details)


def send_id(case, *, on: date | None = None) -> Draft:
    """The Subject decided to send ID: draft the reply saying it is attached.

    The draft is always handed over (``sending.hands_over``): the Subject attaches the document
    from their own device when sending. Marking it sent records "ID sent on <date>"; Unlist
    never receives or stores the document.
    """
    return _draft_step(case, Action.SEND_ID, on)


def details_language(case) -> str:
    """The language a details reply for this Case is written in."""
    jurisdiction = drafting.jurisdiction_for(case.organization)
    return templating.template_language(
        DraftKind.DETAILS_REPLY, drafting.request_language(case.organization), jurisdiction
    )


def detail_line(detail, lang: str) -> str:
    """One IdentifyingDetail as a line of a details reply, such as ``Customer number: 12345``."""
    labels = drafting.DETAIL_LABELS.get(detail.kind)
    label = labels.get(lang, labels[drafting.FALLBACK_LANGUAGE]) if labels else detail.get_kind_display()
    return f"{label}: {detail.value}"


def suggested_details(case) -> list:
    """The Subject's IdentifyingDetails the Organization is known to ask for (pre-selected in the picker)."""
    details = list(case.subject.details.all())
    lang = details_language(case)
    wanted = set(drafting.identifying_lines(case.organization, details, lang))
    return [detail for detail in details if detail_line(detail, lang) in wanted]


def send_chosen_details(case, chosen, *, on: date | None = None) -> Draft:
    """Draft a details reply with exactly the chosen IdentifyingDetails of the Case's Subject."""
    chosen = list(chosen)
    if not chosen:
        raise CaseError("Choose at least one detail to send.")
    if any(detail.subject_id != case.subject_id for detail in chosen):
        raise CaseError("Only the Subject's own details can be sent.")
    lang = details_language(case)
    return send_details(case, [detail_line(detail, lang) for detail in chosen], on=on)


PORTAL_STATES = (State.WAITING, State.PAUSED, State.OVERDUE)


def hand_over_to_portal(case, url: str, *, on: date | None = None) -> CaseEvent:
    """The Organization insists on its own portal or web form: hand that step to the Subject.

    Records the portal link on the Case. Nothing else changes: the Subject uses the portal, and
    the Organization's answer is recorded as usual.
    """
    url = (url or "").strip()
    if not url:
        raise CaseError("Enter the link to the Organization's portal or web form.")
    if case.state not in PORTAL_STATES:
        raise IllegalStep("A portal demand only matters while a request is open.")
    return _record(
        case,
        CaseEvent.Kind.PORTAL_HANDED_OVER,
        _today(on),
        f"The Organization insists on its own portal or web form. Handed over to the Subject to use it: {url}",
        details={"url": url},
    )


def authority_letter(case, operator_name: str, *, on: date | None = None) -> CaseEvent:
    """Write a dated letter of authority for this Case's Organization only, and record it.

    A fresh letter each time: never reused for another Organization or a later date. The text is
    kept in the event so it can be printed again for this Case.
    """
    operator_name = " ".join((operator_name or "").split())
    if not operator_name:
        raise CaseError("Enter the Operator's name for the letter.")
    on = _today(on)
    require_consent(case.subject)
    organization, subject = case.organization, case.subject
    jurisdiction = drafting.jurisdiction_for(organization)
    lang = templating.template_language("authority_letter", drafting.request_language(organization), jurisdiction)
    context = {
        "jurisdiction": jurisdiction,
        "reference": case.reference,
        "subject_name": subject.name,
        "subject_email": _sender(subject),
        "organization_name": organization.name,
        "operator_name": operator_name,
        "letter_date": drafting.format_date(on, lang),
    }
    if subject.is_child and subject.parental_responsibility:
        context["parent_name"] = subject.parental_responsibility
    subject_line, body = templating.render("authority_letter", lang, context)
    return _record(
        case,
        CaseEvent.Kind.AUTHORITY_LETTER,
        on,
        f"Letter of authority for {organization} written, dated {drafting.format_date(on, 'en')}.",
        details={
            "organization": organization.slug,
            "operator_name": operator_name,
            "lang": lang,
            "subject_line": subject_line,
            "letter": body,
        },
    )


def fix_contact(case, *, on: date | None = None) -> Draft:
    """After a bounce, once the Organization's contact is corrected: draft the request again."""
    return _draft_step(case, Action.FIX_CONTACT, on)


def prepare_recheck(case, *, on: date | None = None) -> Draft:
    """For a resting Case: draft the fresh Access Request of a re-check (the re-check ticket schedules it)."""
    return _draft_step(case, Action.RECHECK_DUE, on, event_kind=CaseEvent.Kind.RECHECK_DUE)


def draft_complaint(case, *, on: date | None = None) -> CaseEvent:
    """Move to "Complaint draft": after overdue plus a reminder, or after a refusal.

    Placeholder: the Complaints ticket writes the Complaint itself through ``complaint_drafters``.
    """
    with transaction.atomic():
        require_consent(case.subject)
        event = _step(case, Action.DRAFT_COMPLAINT, _today(on), event_kind=CaseEvent.Kind.COMPLAINT_DRAFTED)[1]
        for drafter in list(complaint_drafters):
            drafter(case)
    return event


def complaint_lodged(case, *, on: date | None = None) -> CaseEvent:
    with transaction.atomic():
        return _step(case, Action.COMPLAINT_LODGED, _today(on), event_kind=CaseEvent.Kind.COMPLAINT_LODGED)[1]


def stop(case, *, on: date | None = None, reason: str = "") -> CaseEvent:
    """Close the Case and discard any pending draft."""
    with transaction.atomic():
        return _step(
            case, Action.STOP, _today(on), event_kind=CaseEvent.Kind.STOPPED, details={"reason": reason}, reason=reason
        )[1]


def reopen(case, *, on: date | None = None) -> CaseEvent:
    """Reopen a closed Case. Nothing is in flight until a request is prepared."""
    with transaction.atomic():
        return _step(case, Action.REOPEN, _today(on), event_kind=CaseEvent.Kind.REOPENED)[1]


def mark_overdue_if_due(case, *, today: date | None = None) -> bool:
    """Mark a waiting Case overdue once ``overdue_from`` has come. True if it was marked."""
    today = _today(today)
    with transaction.atomic():
        refresh_deadline(case)
        if case.state != State.WAITING or case.overdue_from is None or today < case.overdue_from:
            return False
        _step(case, Action.MARK_OVERDUE, case.overdue_from, event_kind=CaseEvent.Kind.OVERDUE)
    return True


def set_recheck_override(case, value: str) -> Case:
    """Days between re-checks for this Case, ``"close"``, or empty for the Organization's default.

    Applies to the next outcome; a date already set for a resting Case stays.
    """
    from unlist.cases.models import validate_recheck_override

    value = (value or "").strip().lower()
    validate_recheck_override(value)
    case.recheck_override = value
    case.save(update_fields=["recheck_override", "updated_at"])
    return case


def add_note(case, text: str, *, on: date | None = None, details: dict | None = None) -> CaseEvent:
    """Record a dated note on the Case. Changes nothing else (no state, no clock)."""
    return _record(case, CaseEvent.Kind.NOTE, _today(on), text, details=details)


def edit_draft(draft, *, subject_line: str, body: str, on: date | None = None) -> Draft:
    """Change the text of a draft awaiting approval. The reference code must stay in the subject line."""
    subject_line = " ".join((subject_line or "").split())
    if draft.status != Draft.Status.AWAITING_APPROVAL:
        raise IllegalStep("Only a draft awaiting approval can be changed.")
    if draft.case.reference not in subject_line:
        raise CaseError(
            f"Keep the reference code {draft.case.reference} in the subject line, so replies can be matched."
        )
    draft.subject_line = subject_line
    draft.body = (body or "").replace("\r\n", "\n")
    draft.save(update_fields=["subject_line", "body"])
    _record(draft.case, CaseEvent.Kind.NOTE, _today(on), "The Operator edited the draft.", details={"draft": draft.pk})
    return draft
