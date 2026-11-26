# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""What the household's pages show: the sidebar counts, "Needs you", and the board columns (#53).

Read-only: nothing here changes a Case. Changes go through ``unlist.cases.services``.

"Needs you" counts what waits for the Operator (spec section 13): drafts awaiting approval,
replies to confirm (also those Unlist could not match to a Case), and Cases that are overdue or
whose request bounced (decided by agent: a bounce needs the Operator just as much as an overdue
answer).
"""

from collections import Counter
from dataclasses import dataclass, field

from django.db.models import Count

from unlist.cases import sending
from unlist.cases.lifecycle import State
from unlist.cases.models import Case, Draft, Reply
from unlist.subjects.models import Mailbox, Subject

ATTENTION_STATES = (State.OVERDUE, State.UNDELIVERABLE)
YOU_STATES = (State.AWAITING_APPROVAL, *ATTENTION_STATES)
SUBJECT_STATES = (State.HANDED_OVER, State.PAUSED, State.LISTING_FOUND, State.REFUSED, State.COMPLAINT_DRAFT)
WAITING_STATES = (State.WAITING, State.COMPLAINT_LODGED)
DONE_STATES = (State.RESTING, State.CLOSED)

# Board columns, in order: (key, heading, what it means).
COLUMNS = [
    ("found", "Found", "Found in the mail. Pick what to pursue."),
    ("you", "Needs you", "Approve, confirm, remind."),
    ("subject", "With the Subject", "To send by hand, or to decide."),
    ("waiting", "Waiting", "On the Organization."),
    ("resting", "Resting", "Until the re-check."),
    ("closed", "Closed", ""),
]
BOARD_LIMIT = 30  # cards per column; the rest are one link away

VIEW_COOKIE = "unlist_view"
VIEWS = ("table", "board")


# --- Sidebar -------------------------------------------------------------------------------


@dataclass
class SidebarSubject:
    pk: int
    name: str
    needs_you: int


@dataclass
class Sidebar:
    subjects: list[SidebarSubject] = field(default_factory=list)
    needs_you: int = 0


def needs_you_counts() -> Counter:
    """Subject id -> what waits for the Operator. Four small aggregate queries."""
    counts = Counter()
    drafts = Draft.objects.filter(status=Draft.Status.AWAITING_APPROVAL).values("case__subject_id")
    for row in drafts.annotate(n=Count("id")):
        counts[row["case__subject_id"]] += row["n"]
    for row in Reply.objects.filter(status=Reply.Status.TO_CONFIRM).values("subject_id").annotate(n=Count("id")):
        counts[row["subject_id"]] += row["n"]
    for row in Case.objects.filter(state__in=ATTENTION_STATES).values("subject_id").annotate(n=Count("id")):
        counts[row["subject_id"]] += row["n"]
    return counts


def sidebar() -> Sidebar:
    counts = needs_you_counts()
    subjects = [SidebarSubject(pk, name, counts[pk]) for pk, name in Subject.objects.values_list("pk", "name")]
    return Sidebar(subjects=subjects, needs_you=sum(subject.needs_you for subject in subjects))


# --- Drafts: who receives them and how they leave --------------------------------------------


def delivery(draft) -> dict:
    """How an approved draft leaves: Unlist sends it, or the Subject sends it (and where to)."""
    subject = draft.case.subject.name
    hand = {"mode": "hand", "label": "Handed over"}
    if sending.will_send(draft):
        return {"mode": "send", "label": "Unlist sends it", "text": f"from {draft.sender}"}
    if draft.channel == Draft.Channel.WEBFORM:
        return {**hand, "text": f"{subject} submits it at the web form"}
    if draft.channel == Draft.Channel.LETTER:
        return {**hand, "text": f"{subject} posts it as a letter"}
    return {**hand, "text": f"{subject} sends it from {draft.sender} with their own mail app"}


def drafts_awaiting(subject=None):
    drafts = Draft.objects.filter(status=Draft.Status.AWAITING_APPROVAL).select_related(
        "case", "case__subject", "case__organization"
    )
    if subject is not None:
        drafts = drafts.filter(case__subject=subject)
    return [{"draft": draft, **delivery(draft)} for draft in drafts.order_by("case__subject__name", "created_at", "id")]


# --- Needs you -----------------------------------------------------------------------------


def needs_you(subject=None) -> dict:
    """Everything that waits for the Operator, household-wide or for one Subject."""
    from unlist.mail.models import Discovery, ImportRun
    from unlist.organizations.models import PendingContactChange

    replies = Reply.objects.filter(status=Reply.Status.TO_CONFIRM).select_related(
        "subject", "case", "case__organization"
    )
    attention = Case.objects.filter(state__in=ATTENTION_STATES).select_related("subject", "organization")
    subjects = Subject.objects.all()
    if subject is not None:
        replies = replies.filter(subject=subject)
        attention = attention.filter(subject=subject)
        subjects = subjects.filter(pk=subject.pk)

    finds = []
    for one in subjects:
        run = ImportRun.objects.filter(subject=one, finished_at__isnull=False, failure="").first()
        if run is None:
            continue
        with_case = Case.objects.filter(subject=one).values("organization_id")
        new = (
            Discovery.objects.filter(subject=one, status=Discovery.Status.NEW).exclude(organization_id__in=with_case)
        ).count()
        if new:
            finds.append({"subject": one, "run": run, "new": new})

    return {
        "drafts": drafts_awaiting(subject),
        "replies": [reply for reply in replies if reply.case_id],
        "unmatched": [reply for reply in replies if not reply.case_id],
        "attention": list(attention.order_by("overdue_from", "id")),
        "contact_changes": list(PendingContactChange.objects.select_related("organization")),
        "finds": finds,
    }


def first_run() -> dict | None:
    """The guided first steps, while any of them is missing; None once the household is set up."""
    from unlist.mail.models import ImportRun, MailboxConnection

    subject = Subject.objects.order_by("created_at", "id").first()
    consent = subject is not None and subject.has_active_consent()
    mail = subject is not None and (
        ImportRun.objects.filter(subject=subject).exists()
        or MailboxConnection.objects.filter(mailbox__subject=subject).exists()
    )
    if subject and consent and mail:
        return None
    return {"subject": subject, "has_subject": subject is not None, "consent": consent, "mail": mail}


# --- The board -----------------------------------------------------------------------------


def column_for(case, reply_case_ids) -> str:
    state = State(case.state)
    if case.pk in reply_case_ids or state in YOU_STATES:
        return "you"
    if state == State.FOUND:
        return "found"
    if state in SUBJECT_STATES:
        return "subject"
    if state in WAITING_STATES:
        return "waiting"
    return state.value  # resting, closed


def reply_case_ids(subject=None) -> set[int]:
    replies = Reply.objects.filter(status=Reply.Status.TO_CONFIRM, case__isnull=False)
    if subject is not None:
        replies = replies.filter(subject=subject)
    return set(replies.values_list("case_id", flat=True))


def next_date(case):
    """(label, date) of a Case's next date: the answer's deadline, or the re-check."""
    if case.state == State.RESTING and case.recheck_on:
        return "re-check", case.recheck_on
    if case.state == State.OVERDUE and case.overdue_from:
        return "overdue since", case.overdue_from
    if case.due_date:
        return "due", case.due_date
    return "", None


def case_rows(cases, replies_for, draft_items=()) -> list[dict]:
    """One row per Case for the table and the board, with its draft awaiting approval, if any."""
    awaiting = {item["draft"].case_id: item for item in draft_items}
    rows = []
    for case in cases:
        label, on = next_date(case)
        rows.append(
            {
                "case": case,
                "column": column_for(case, replies_for),
                "reply_waiting": case.pk in replies_for,
                "date_label": label,
                "date": on,
                "awaiting": awaiting.get(case.pk),
            }
        )
    return rows


def board(rows, found=(), *, found_total=0, found_url="", more_urls=None) -> list[dict]:
    """The six columns. ``found`` are new Discoveries, shown in "Found" next to Cases in that state."""
    more_urls = more_urls or {}
    columns = []
    for key, heading, text in COLUMNS:
        items = [row for row in rows if row["column"] == key]
        total = len(items) + (found_total if key == "found" else 0)
        column = {"key": key, "heading": heading, "text": text, "total": total, "rows": items[:BOARD_LIMIT]}
        if key == "found":
            column["found"] = list(found)[: max(BOARD_LIMIT - len(column["rows"]), 0)]
            shown = len(column["rows"]) + len(column["found"])
            column["more_url"] = found_url if total > shown else ""
        else:
            column["more_url"] = more_urls.get(key, "") if len(items) > BOARD_LIMIT else ""
        column["more"] = total - len(column["rows"]) - len(column.get("found", []))
        columns.append(column)
    return columns


def new_discoveries(subject=None):
    """Discoveries not pursued, not ignored and without a Case: the board's "Found" cards."""
    from unlist.mail import scanner
    from unlist.mail.models import Discovery

    discoveries = Discovery.objects.filter(status=Discovery.Status.NEW).select_related("subject", "organization")
    if subject is not None:
        discoveries = discoveries.filter(subject=subject)
    with_case = set(Case.objects.values_list("subject_id", "organization_id"))
    rank = {kind: index for index, kind in enumerate(scanner.EVIDENCE_ORDER)}
    found = [d for d in discoveries if (d.subject_id, d.organization_id) not in with_case]
    found.sort(key=lambda d: (rank.get(d.evidence, len(rank)), d.organization.name.lower()))
    return found


# --- Table / Board choice --------------------------------------------------------------------


def chosen_view(request) -> tuple[str, bool]:
    """("table" or "board", whether to remember it). ``?view=`` wins; else the browser's last choice."""
    asked = request.GET.get("view")
    if asked in VIEWS:
        return asked, True
    remembered = request.COOKIES.get(VIEW_COOKIE)
    return (remembered if remembered in VIEWS else "table"), False


def remember_view(response, view: str):
    """Remember the choice in this browser for a year. Not a setting: nothing is stored on the instance."""
    response.set_cookie(VIEW_COOKIE, view, max_age=365 * 24 * 3600, samesite="Lax", httponly=True)
    return response


# --- A Subject's mail ----------------------------------------------------------------------


def mail_status(subject) -> dict:
    """The Subject's mail mode, last scan or import, and the button that fits."""
    from unlist.mail.models import ImportRun, MailboxConnection

    live = (
        MailboxConnection.objects.filter(mailbox__subject=subject, mailbox__mode=Mailbox.Mode.LIVE)
        .select_related("mailbox")
        .first()
    )
    run = ImportRun.objects.filter(subject=subject).first()
    last = None
    if run is not None:
        last = run.finished_at or run.started_at
    if live and live.last_scan_at and (last is None or live.last_scan_at > last):
        last = live.last_scan_at
    return {
        "mode": "live" if live else "import",
        "mode_label": "Live connection" if live else "Import only",
        "live": live,
        "run": run,
        "last": last,
        "imported": run is not None,
    }
