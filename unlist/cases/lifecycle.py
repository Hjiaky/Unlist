# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The Case state machine: which step may follow which, and why not.

A port of the pure ``UnlistCase`` module in ``docs/prototypes/request-lifecycle.html`` (spec
section 4, decisions on https://github.com/Hjiaky/Unlist/issues/4). Pure: no Django, no dates.

    result = transition(case_state, Action.APPROVE, sent=False)
    if result.error: ...            # plain words, the state is unchanged
    else: result.case               # the new CaseState

Dates and deadlines live elsewhere: the deadline engine (``deadlines.py``) works out when an
answer is due, and the services (``services.py``) turn "the deadline has passed" into
``Action.MARK_OVERDUE`` and "the re-check date has come" into ``Action.RECHECK_DUE``. The
result tells the caller what to do outside the state: which draft to prepare
(``new_draft``), which draft went out (``delivered``), which pending draft to drop
(``discarded_draft``) and after how many days to re-check (``recheck_in_days``).

Rules kept from the prototype
-----------------------------
- Ask, then delete: a Case starts with an Access Request; a Removal Request follows only once a
  Listing is known, unless the Case was set to "request removal directly".
- Every email is a draft that waits for approval. Approving either sends it (a live sender took
  it) or hands it over to the Subject, who marks it sent; only then does the clock start.
- Gentle first: overdue leads to a reminder, and only after a reminder to a Complaint draft. A
  refusal may go straight to a Complaint draft.
- Late answers still move a Case on, also after a Complaint draft or a lodged Complaint.
- A bounce means the clock never started; the contact is fixed and the request prepared again.
- After a Listing is found the Subject removes or keeps; after a refusal the Subject accepts,
  asks to reconsider, or drafts a Complaint.
- After "nothing held", Brokers rest until a re-check and others close; after "removed" every
  Organization rests. Both are overridable per Organization or per Case (``recheck_intervals``).

Changes to the prototype (decided by agent, ticket #47)
-------------------------------------------------------
- An answer from the Organization is also taken while a follow-up draft (a reminder, details
  reply, ID pushback or reconsider reply) waits for approval or for the Subject to send it.
  The pending draft is then discarded. Without this, a reminder prepared by the scheduler
  would block a late answer.
- "Nothing held" also answers a Removal Request (a Case that asked for removal directly, or an
  Organization that deleted the data before it answered).
- Asking to reconsider is only offered after a refused Removal Request: the reconsider text is
  about erasure. A refused Access Request is accepted or taken to a Complaint.

Changes for re-checks (decided by agent, ticket #51)
----------------------------------------------------
- A returned Listing: when a re-check finds a Listing at a Broker that had confirmed a
  Suppression Record (``suppression_record``), the Subject may go straight to a Complaint draft
  besides removing or keeping (spec section 8).

Changes for Complaints (decided by agent, ticket #52)
-----------------------------------------------------
- Persistent ID demands (spec section 9): a Complaint may be drafted while the Case is paused if
  the Subject already pushed back on an ID demand in the current request (``pushbacks``) and the
  Organization asked again. Gentle first: the pushback comes before the Complaint.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

BROKER_RECHECK_DAYS = 90
OTHER_RECHECK_DAYS = 365
CLOSE = "close"


class State(StrEnum):
    FOUND = "found"
    AWAITING_APPROVAL = "awaiting_approval"
    HANDED_OVER = "handed_over"
    WAITING = "waiting"
    PAUSED = "paused"
    OVERDUE = "overdue"
    UNDELIVERABLE = "undeliverable"
    LISTING_FOUND = "listing_found"
    REFUSED = "refused"
    COMPLAINT_DRAFT = "complaint_draft"
    COMPLAINT_LODGED = "complaint_lodged"
    RESTING = "resting"
    CLOSED = "closed"


STATE_LABELS = {
    State.FOUND: "Found",
    State.AWAITING_APPROVAL: "Draft awaiting approval",
    State.HANDED_OVER: "Handed over",
    State.WAITING: "Waiting",
    State.PAUSED: "Paused",
    State.OVERDUE: "Overdue",
    State.UNDELIVERABLE: "Undeliverable",
    State.LISTING_FOUND: "Listing found",
    State.REFUSED: "Refused or partly done",
    State.COMPLAINT_DRAFT: "Complaint draft",
    State.COMPLAINT_LODGED: "Complaint lodged",
    State.RESTING: "Resting",
    State.CLOSED: "Closed",
}

STATE_TEXT = {
    State.FOUND: "Found. Nothing sent yet.",
    State.AWAITING_APPROVAL: "A draft is ready and waits for approval.",
    State.HANDED_OVER: "Approved and handed over. Waiting for the Subject to send it and mark it sent.",
    State.WAITING: "Sent. Waiting for the Organization's answer.",
    State.PAUSED: "The Organization asked for ID or more details. The clock is paused.",
    State.OVERDUE: "No answer by the deadline.",
    State.UNDELIVERABLE: "The email bounced. The contact needs fixing.",
    State.LISTING_FOUND: "A Listing was found. The Subject decides: remove or keep.",
    State.REFUSED: "The Organization refused, or did only part. The Subject decides what next.",
    State.COMPLAINT_DRAFT: "A Complaint draft is ready. The Subject lodges it themselves.",
    State.COMPLAINT_LODGED: "A Complaint was lodged with the Supervisory Authority.",
    State.RESTING: "Done for now. Resting until the re-check.",
    State.CLOSED: "Closed.",
}

NEXT_ACTOR = {
    State.FOUND: "Operator (prepare the request, or stop)",
    State.AWAITING_APPROVAL: "Operator (approve or discard)",
    State.HANDED_OVER: "Subject (send it, then mark it sent)",
    State.WAITING: "The Organization",
    State.PAUSED: "Subject (answer, or push back)",
    State.OVERDUE: "Operator (a reminder first, then a Complaint draft)",
    State.UNDELIVERABLE: "Operator (fix the contact)",
    State.LISTING_FOUND: "Subject (remove or keep)",
    State.REFUSED: "Subject (accept, ask to reconsider, or draft a Complaint)",
    State.COMPLAINT_DRAFT: "Subject (lodge the Complaint)",
    State.COMPLAINT_LODGED: "The Supervisory Authority, outside Unlist",
    State.RESTING: "Nobody, until the re-check date",
    State.CLOSED: "Nobody (it can be reopened)",
}


class Request(StrEnum):
    ACCESS = "access"
    REMOVAL = "removal"


class DraftKind(StrEnum):
    """What a draft is. The values are the mail template kinds (``templating.KINDS``)."""

    ACCESS_REQUEST = "access_request"
    REMOVAL_REQUEST = "removal_request"
    REMINDER = "reminder"
    DETAILS_REPLY = "details_reply"
    ID_PUSHBACK = "id_pushback"
    RECONSIDER = "reconsider"


REQUEST_DRAFT = {Request.ACCESS: DraftKind.ACCESS_REQUEST, Request.REMOVAL: DraftKind.REMOVAL_REQUEST}
DRAFT_REQUEST = {kind: request for request, kind in REQUEST_DRAFT.items()}

DRAFT_NAMES = {
    DraftKind.ACCESS_REQUEST: "Access Request",
    DraftKind.REMOVAL_REQUEST: "Removal Request",
    DraftKind.REMINDER: "Reminder",
    DraftKind.DETAILS_REPLY: "Reply with the details asked for",
    DraftKind.ID_PUSHBACK: "Reply pushing back on the ID demand",
    DraftKind.RECONSIDER: "Reply asking the Organization to reconsider",
}


class Action(StrEnum):
    PREPARE_REQUEST = "prepare_request"
    REQUEST_REMOVAL = "request_removal"
    KEEP_LISTING = "keep_listing"
    APPROVE = "approve"
    MARK_SENT = "mark_sent"
    DISCARD = "discard"
    # The Organization answers
    NOTHING_HELD = "nothing_held"
    LISTING_FOUND = "listing_found"
    REMOVED = "removed"
    REFUSED = "refused"
    ID_OR_DETAILS_ASKED = "id_or_details_asked"
    EXTENSION_ANNOUNCED = "extension_announced"
    BOUNCE = "bounce"
    # Follow-ups
    SEND_DETAILS = "send_details"
    PUSH_BACK = "push_back"
    FIX_CONTACT = "fix_contact"
    MARK_OVERDUE = "mark_overdue"
    SEND_REMINDER = "send_reminder"
    DRAFT_COMPLAINT = "draft_complaint"
    COMPLAINT_LODGED = "complaint_lodged"
    ACCEPT_REFUSAL = "accept_refusal"
    ASK_RECONSIDER = "ask_reconsider"
    STOP = "stop"
    REOPEN = "reopen"
    RECHECK_DUE = "recheck_due"


OUTCOMES = (
    Action.NOTHING_HELD,
    Action.LISTING_FOUND,
    Action.REMOVED,
    Action.REFUSED,
    Action.ID_OR_DETAILS_ASKED,
    Action.EXTENSION_ANNOUNCED,
    Action.BOUNCE,
)

OUTCOME_LABELS = {
    Action.NOTHING_HELD: '"We hold nothing"',
    Action.LISTING_FOUND: "Sent the data it holds (a Listing exists)",
    Action.REMOVED: "Confirmed removal",
    Action.REFUSED: "Refused, or did only part",
    Action.ID_OR_DETAILS_ASKED: "Asked for ID or more details",
    Action.EXTENSION_ANNOUNCED: "Announced an extension",
    Action.BOUNCE: "The email bounced",
}

ACTION_LABELS = {
    Action.PREPARE_REQUEST: "Prepare the request",
    Action.REQUEST_REMOVAL: "Ask for removal",
    Action.KEEP_LISTING: "Keep the Listing",
    Action.SEND_DETAILS: "Send the details asked for",
    Action.PUSH_BACK: "Push back on the ID demand",
    Action.FIX_CONTACT: "Contact fixed: prepare the request again",
    Action.SEND_REMINDER: "Prepare a reminder",
    Action.DRAFT_COMPLAINT: "Draft a Complaint",
    Action.COMPLAINT_LODGED: "Mark the Complaint as lodged",
    Action.ACCEPT_REFUSAL: "Accept the refusal",
    Action.ASK_RECONSIDER: "Ask the Organization to reconsider",
    Action.STOP: "Stop pursuing this Organization",
    Action.REOPEN: "Reopen the Case",
}

# States in which an answer from the Organization is still expected or still welcome.
LATE_OK = (State.WAITING, State.PAUSED, State.OVERDUE, State.COMPLAINT_DRAFT, State.COMPLAINT_LODGED)
FOLLOW_UPS = (DraftKind.REMINDER, DraftKind.DETAILS_REPLY, DraftKind.ID_PUSHBACK, DraftKind.RECONSIDER)
# States where the Organization's clock matters.
CLOCK_STATES = (State.WAITING, State.PAUSED, State.OVERDUE)


@dataclass(frozen=True)
class CaseState:
    """Everything the rules look at. ``draft`` and ``draft_back`` describe the pending draft, if any."""

    state: State = State.FOUND
    request: Request | None = None
    draft: DraftKind | None = None
    draft_back: State | None = None
    reminders: int = 0
    broker: bool = False
    direct_removal: bool = False
    recheck_after_nothing: int | None = None
    """Days until the re-check after "nothing held"; ``None`` closes the Case instead."""
    recheck_after_removed: int | None = BROKER_RECHECK_DAYS
    """Days until the re-check after "removed" or an accepted partial removal; ``None`` closes."""
    result: str = ""
    pushbacks: int = 0
    """ID pushbacks sent since the current request was sent."""
    suppression_record: bool = False
    """A Suppression Record was confirmed earlier in this Case, so a Listing found now has returned."""


@dataclass(frozen=True)
class Transition:
    case: CaseState
    error: str | None = None
    messages: tuple[str, ...] = ()
    new_draft: DraftKind | None = None
    delivered: DraftKind | None = None
    discarded_draft: DraftKind | None = None
    recheck_in_days: int | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def text(self) -> str:
        return " ".join(self.messages)


def recheck_intervals(
    broker: bool, organization_default: int | None = None, case_override: int | str | None = None
) -> tuple[int | None, int | None]:
    """Days until the re-check after (nothing held, removed); ``None`` means close instead.

    Spec section 8: Brokers 90 days after either; others 365 days after "removed" and none after
    "nothing held". The Organization's re-check default replaces both; a Case override (days, or
    ``"close"`` for never) beats it.
    """
    if case_override == CLOSE:
        return None, None
    if case_override not in (None, ""):
        days = int(case_override)
        return days, days
    if organization_default:
        return organization_default, organization_default
    if broker:
        return BROKER_RECHECK_DAYS, BROKER_RECHECK_DAYS
    return None, OTHER_RECHECK_DAYS


def initial(
    *, broker: bool = False, direct_removal: bool = False, organization_default=None, case_override=None
) -> CaseState:
    nothing, removed = recheck_intervals(broker, organization_default, case_override)
    return CaseState(
        broker=broker,
        direct_removal=direct_removal,
        recheck_after_nothing=nothing,
        recheck_after_removed=removed,
    )


def _plural_days(days: int) -> str:
    return "1 day" if days == 1 else f"{days} days"


def transition(
    s: CaseState, action: Action | str, *, sent: bool = False, suppression_confirmed: bool = False, reason: str = ""
) -> Transition:
    """Apply ``action`` to ``s``. On an illegal action, ``error`` says why and ``case`` is ``s``.

    ``sent`` (for APPROVE): a live sender sent the draft, so it does not need handing over.
    ``suppression_confirmed`` (for REMOVED): the Broker confirmed a Suppression Record.
    ``reason`` (for STOP): why the Case was stopped, kept as its result.
    """
    try:
        action = Action(action)
    except ValueError:
        return Transition(s, error="Unknown action.")

    changes: dict = {}
    messages: list[str] = []
    effects: dict = {}

    def say(text):
        messages.append(text)

    def ok():
        return Transition(replace(s, **changes), None, tuple(messages), **effects)

    def no(why):
        return Transition(s, error=why)

    def make_draft(kind: DraftKind):
        changes.update(state=State.AWAITING_APPROVAL, draft=kind, draft_back=s.state)
        effects["new_draft"] = kind

    def rest(result, days):
        changes.update(result=result, request=None, draft=None, draft_back=None)
        if days is None:
            changes["state"] = State.CLOSED
            say("Case closed. No re-check is planned.")
        else:
            changes["state"] = State.RESTING
            effects["recheck_in_days"] = days
            say(f"Done for now. Re-check in {_plural_days(days)}.")

    def close(result):
        changes.update(state=State.CLOSED, result=result, request=None, draft=None, draft_back=None)

    def deliver(kind: DraftKind):
        effects["delivered"] = kind
        changes.update(draft=None, draft_back=None, state=State.WAITING)
        if kind in DRAFT_REQUEST:
            changes.update(request=DRAFT_REQUEST[kind], reminders=0, result="")
        elif kind is DraftKind.REMINDER:
            changes["reminders"] = s.reminders + 1
        elif kind in (DraftKind.DETAILS_REPLY, DraftKind.ID_PUSHBACK):
            say("The clock runs again.")
        say(f"{DRAFT_NAMES[kind]} sent from the Subject's own address.")

    # The state an answer from the Organization is judged against: while a follow-up draft is
    # pending, the state it was prepared in.
    effective = s.state
    pending_follow_up = (
        s.state in (State.AWAITING_APPROVAL, State.HANDED_OVER) and s.draft in FOLLOW_UPS and s.draft_back in LATE_OK
    )
    if action in OUTCOMES and pending_follow_up:
        effective = s.draft_back

    def drop_pending_follow_up():
        if pending_follow_up:
            effects["discarded_draft"] = s.draft
            changes.update(draft=None, draft_back=None)
            say(f"The pending draft ({DRAFT_NAMES[s.draft]}) was discarded because the Organization answered.")

    not_open = "The Organization has not been asked anything that is still open."

    match action:
        case Action.PREPARE_REQUEST:
            if s.state is not State.FOUND:
                return no("A request is only prepared for a Case where nothing is in flight.")
            kind = DraftKind.REMOVAL_REQUEST if s.direct_removal else DraftKind.ACCESS_REQUEST
            make_draft(kind)
            if s.direct_removal:
                say("Unlist prepared a Removal Request directly, as chosen for this Case. It waits for approval.")
            else:
                say("Unlist prepared an Access Request. It waits for approval.")

        case Action.REQUEST_REMOVAL:
            if s.state is not State.LISTING_FOUND:
                return no(
                    "Ask, then delete: a Removal Request is only sent after an Access Request showed that a "
                    "Listing exists."
                )
            make_draft(DraftKind.REMOVAL_REQUEST)
            if s.broker:
                say(
                    "The Subject chose removal. Unlist prepared a Removal Request that also asks the Broker to keep "
                    "a minimal Suppression Record, so the Subject is not listed again."
                )
            else:
                say("The Subject chose removal. Unlist prepared a Removal Request.")

        case Action.KEEP_LISTING:
            if s.state is not State.LISTING_FOUND:
                return no("There is no Listing to decide about right now.")
            close("Kept by choice (the Subject still wants this Organization to hold the data)")
            say("The Subject chose to keep the Listing. Case closed, no re-check.")

        case Action.APPROVE:
            if s.state is not State.AWAITING_APPROVAL:
                return no("Nothing is waiting for approval.")
            if sent:
                say("Approved. Unlist sent it.")
                deliver(s.draft)
            else:
                changes["state"] = State.HANDED_OVER
                say("Approved. Unlist handed the email to the Subject to send from their own mail app.")

        case Action.MARK_SENT:
            if s.state is not State.HANDED_OVER:
                return no("No email is waiting to be sent by hand.")
            say("The Subject sent it and marked it as sent.")
            deliver(s.draft)

        case Action.DISCARD:
            if s.state not in (State.AWAITING_APPROVAL, State.HANDED_OVER):
                return no("There is no draft to discard.")
            say(f"Draft discarded ({DRAFT_NAMES[s.draft]}).")
            effects["discarded_draft"] = s.draft
            changes.update(state=s.draft_back, draft=None, draft_back=None)

        case Action.NOTHING_HELD:
            if effective not in LATE_OK:
                return no(not_open)
            drop_pending_follow_up()
            say("The Organization answered: it holds nothing about the Subject.")
            rest("Nothing held", s.recheck_after_nothing)

        case Action.LISTING_FOUND:
            if effective not in LATE_OK:
                return no(not_open)
            if s.request is not Request.ACCESS:
                return no("A copy of the data answers an Access Request, and none is open.")
            drop_pending_follow_up()
            changes["state"] = State.LISTING_FOUND
            say("The Organization sent the data it holds. A Listing exists. The Subject decides what to do.")

        case Action.REMOVED:
            if effective not in LATE_OK:
                return no(not_open)
            if s.request is not Request.REMOVAL:
                return no("A removal confirmation answers a Removal Request, and none is open.")
            drop_pending_follow_up()
            if s.broker and suppression_confirmed:
                say(
                    "The Broker confirmed the removal and that it keeps a minimal Suppression Record, so it will "
                    "not list the Subject again."
                )
                rest("Removed, Suppression Record confirmed", s.recheck_after_removed)
            elif s.broker:
                say(
                    "The Broker confirmed the removal but said nothing about a Suppression Record. It may list the "
                    "Subject again; the re-check will show it."
                )
                rest("Removed, no Suppression Record confirmed", s.recheck_after_removed)
            else:
                say("The Organization confirmed the removal.")
                rest("Removed", s.recheck_after_removed)

        case Action.REFUSED:
            if effective not in LATE_OK:
                return no(not_open)
            drop_pending_follow_up()
            changes["state"] = State.REFUSED
            say("The Organization refused, or did only part, and named a reason. Unlist records the exception cited.")

        case Action.ID_OR_DETAILS_ASKED:
            if effective is not State.WAITING:
                return no("The Organization can only ask for ID or details while a request is open and the clock runs.")
            drop_pending_follow_up()
            changes["state"] = State.PAUSED
            say("The Organization asked for ID or more details. The clock is paused until the Subject answers.")

        case Action.EXTENSION_ANNOUNCED:
            if effective is not State.WAITING:
                return no("An extension notice only matters while a request is open.")
            drop_pending_follow_up()
            changes["state"] = State.WAITING
            say("The Organization announced an extension. Whether it counts is worked out in the deadline.")

        case Action.BOUNCE:
            if effective is not State.WAITING:
                return no("Only a sent email can bounce.")
            drop_pending_follow_up()
            changes["state"] = State.UNDELIVERABLE
            say("The email bounced. The clock never started: the Organization did not receive it.")

        case Action.SEND_DETAILS:
            if s.state is not State.PAUSED:
                return no("The Organization has not asked for anything.")
            make_draft(DraftKind.DETAILS_REPLY)
            say("Unlist prepared a reply with the details asked for.")

        case Action.PUSH_BACK:
            if s.state is not State.PAUSED:
                return no("There is no ID demand to push back on.")
            make_draft(DraftKind.ID_PUSHBACK)
            say("Unlist prepared a reply saying the ID demand goes too far.")

        case Action.FIX_CONTACT:
            if s.state is not State.UNDELIVERABLE:
                return no("No email has bounced.")
            kind = REQUEST_DRAFT[s.request]
            make_draft(kind)
            say(f"Contact corrected. Unlist prepared the {DRAFT_NAMES[kind]} again.")

        case Action.MARK_OVERDUE:
            if s.state is not State.WAITING:
                return no("Only a Case waiting for an answer can become overdue.")
            changes["state"] = State.OVERDUE
            say("No answer by the deadline plus grace. The Case is overdue.")

        case Action.SEND_REMINDER:
            if s.state is not State.OVERDUE:
                return no("A reminder is only for an Organization that has missed its deadline.")
            make_draft(DraftKind.REMINDER)
            say("Unlist prepared a polite reminder. It waits for approval.")

        case Action.DRAFT_COMPLAINT:
            if s.state is State.REFUSED:
                say("Unlist drafts a Complaint about the refusal. The Subject lodges it; Unlist does not.")
            elif s.state is State.OVERDUE:
                if s.reminders < 1:
                    return no("Gentle first: send a reminder before drafting a Complaint.")
                say("Unlist drafts a Complaint about the missed deadline. The Subject lodges it; Unlist does not.")
            elif s.state is State.PAUSED:
                if s.pushbacks < 1:
                    return no("Gentle first: push back on the ID demand before drafting a Complaint.")
                say(
                    "The Organization repeats its ID demand after the Subject pushed back. Unlist drafts a Complaint "
                    "about it. The Subject lodges it; Unlist does not."
                )
            elif s.state is State.LISTING_FOUND and s.suppression_record:
                say(
                    "The Broker lists the Subject again although it confirmed a Suppression Record. Unlist drafts a "
                    "Complaint about it. The Subject lodges it; Unlist does not."
                )
            else:
                return no(
                    "A Complaint is only drafted after a missed deadline plus a reminder, after a refusal, after an "
                    "ID demand repeated despite a pushback, or when a Broker lists the Subject again despite a "
                    "Suppression Record."
                )
            changes["state"] = State.COMPLAINT_DRAFT

        case Action.COMPLAINT_LODGED:
            if s.state is not State.COMPLAINT_DRAFT:
                return no("There is no Complaint draft.")
            changes["state"] = State.COMPLAINT_LODGED
            say("The Subject lodged the Complaint and marked it as lodged.")

        case Action.ACCEPT_REFUSAL:
            if s.state is not State.REFUSED:
                return no("There is no refusal to accept.")
            if s.request is Request.REMOVAL:
                say("The Subject accepted the outcome.")
                rest("Partly removed or refused (accepted)", s.recheck_after_removed)
            else:
                close("Access refused (accepted)")
                say("The Subject accepted the refusal. Case closed.")

        case Action.ASK_RECONSIDER:
            if s.state is not State.REFUSED:
                return no("There is no refusal to answer.")
            if s.request is not Request.REMOVAL:
                return no(
                    "Asking to reconsider is for a refused Removal Request. A refused Access Request can be accepted "
                    "or taken to a Complaint."
                )
            make_draft(DraftKind.RECONSIDER)
            say("Unlist prepared a reply asking the Organization to reconsider.")

        case Action.STOP:
            if s.state is State.CLOSED:
                return no("The Case is already closed.")
            if s.draft:
                effects["discarded_draft"] = s.draft
            close(reason or "Stopped by choice")
            say(f"The Operator stopped pursuing this Organization ({reason or 'by choice'}).")

        case Action.REOPEN:
            if s.state is not State.CLOSED:
                return no("Only a closed Case can be reopened.")
            changes.update(state=State.FOUND, result="", request=None)
            say("Case reopened. Nothing in flight.")

        case Action.RECHECK_DUE:
            if s.state is not State.RESTING:
                return no("Only a resting Case has a re-check.")
            make_draft(DraftKind.ACCESS_REQUEST)
            say("Re-check due. Unlist prepared a fresh Access Request. It waits for approval like any other email.")

    return ok()


def can(s: CaseState, action: Action | str) -> bool:
    return transition(s, action).ok


def allowed(s: CaseState, actions=tuple(Action)) -> list[Action]:
    """The actions from ``actions`` that are legal in ``s``, in the given order."""
    return [action for action in actions if can(s, action)]
