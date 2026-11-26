# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Every figure on the statistics page, and every query behind it (spec section 11).

Definitions, per Subject and Organization (one Organization is counted once per Subject):

- **Holding data**: a Listing was found at the Organization and has not been removed since (a
  Case where the Organization sent the data it holds, and the Subject has not had it removed);
  or, with no Listing known, a Discovery with account evidence or better that was not ignored,
  unless a Case closed as "nothing held" or "removed".
- **Removed**: the Organization confirmed a removal, and it has not been found listing again.

A Case's standing is worked out from its events, in order (``case_standing``). Nothing here
scores, ranks or compares Subjects; the figures only count.
"""

import statistics
from collections import Counter
from dataclasses import dataclass, field

from unlist.cases import deadlines, drafting, lifecycle, services
from unlist.cases.lifecycle import State
from unlist.cases.models import Case, CaseEvent
from unlist.mail import scanner
from unlist.mail.models import Discovery, Evidence
from unlist.subjects.models import Subject

# Outcomes of a Case, in the order the page shows them.
REMOVED = "removed"
NOTHING_HELD = "nothing_held"
REFUSED = "refused"
KEPT = "kept"
OUTCOME_LABELS = {
    REMOVED: "Removed",
    NOTHING_HELD: "Nothing held",
    REFUSED: "Refused or partly done",
    KEPT: "Kept by choice",
}

# What an Organization's first answer to a request can be (not a bounce, not an extension).
ANSWER_KINDS = (
    CaseEvent.Kind.NOTHING_HELD,
    CaseEvent.Kind.LISTING_FOUND,
    CaseEvent.Kind.REMOVED,
    CaseEvent.Kind.REFUSED,
    CaseEvent.Kind.ID_OR_DETAILS_ASKED,
)

STATE_ORDER = [state.value for state in State]
EVIDENCE_ORDER = list(scanner.EVIDENCE_ORDER)
EVIDENCE_LABELS = {kind.value: kind.label for kind in Evidence}


@dataclass(frozen=True)
class Standing:
    """Where a Case stands, as its events tell it."""

    outcome: str | None = None  # REMOVED, NOTHING_HELD, REFUSED, KEPT, or None while undecided
    listing_known: bool = False
    suppression_confirmed: bool = False


def case_standing(events) -> Standing:
    """Replay a Case's events (in order) into its standing."""
    outcome, listing, confirmed = None, False, False
    for event in events:
        kind = event.kind
        if kind == CaseEvent.Kind.LISTING_FOUND:
            outcome, listing, confirmed = None, True, False
        elif kind == CaseEvent.Kind.REMOVED:
            outcome, listing, confirmed = REMOVED, False, bool(event.suppression_confirmed)
        elif kind == CaseEvent.Kind.NOTHING_HELD:
            outcome, listing, confirmed = NOTHING_HELD, False, False
        elif kind == CaseEvent.Kind.REFUSED:
            outcome = REFUSED
        elif kind == CaseEvent.Kind.LISTING_KEPT:
            outcome = KEPT
        elif kind == CaseEvent.Kind.REOPENED and outcome in (KEPT, REFUSED):
            outcome = None  # the question is open again
    return Standing(outcome, listing, confirmed)


@dataclass
class Figures:
    """The figures of one Subject, or of the household (the sum of its Subjects)."""

    evidence: Counter = field(default_factory=Counter)  # Discovery evidence kind -> Organizations
    discoveries: int = 0
    brokers: int = 0  # Discoveries that are Brokers
    cases_by_state: Counter = field(default_factory=Counter)
    outcomes: Counter = field(default_factory=Counter)
    removed_confirmed: int = 0  # of the removed, with a confirmed Suppression Record
    holding: int = 0
    removed: int = 0

    @property
    def cases(self) -> int:
        return sum(self.cases_by_state.values())

    def counts(self) -> dict:
        """The figures as JSON, for ``MonthlySnapshot.counts``."""
        return {
            "evidence": dict(self.evidence),
            "discoveries": self.discoveries,
            "brokers": self.brokers,
            "cases": dict(self.cases_by_state),
            "outcomes": dict(self.outcomes),
            "removed_confirmed": self.removed_confirmed,
        }


def combine(parts) -> Figures:
    """The household: the sum of the Subjects' figures."""
    total = Figures()
    for part in parts:
        total.evidence.update(part.evidence)
        total.discoveries += part.discoveries
        total.brokers += part.brokers
        total.cases_by_state.update(part.cases_by_state)
        total.outcomes.update(part.outcomes)
        total.removed_confirmed += part.removed_confirmed
        total.holding += part.holding
        total.removed += part.removed
    return total


def compute_all() -> dict[int, Figures]:
    """Figures for every Subject, by Subject id (a Subject with nothing yet has empty figures)."""
    result = {subject_id: Figures() for subject_id in Subject.objects.values_list("pk", flat=True)}
    discoveries = {}
    for discovery in Discovery.objects.select_related("organization"):
        found = result.get(discovery.subject_id)
        if found is None:
            continue
        discoveries[(discovery.subject_id, discovery.organization_id)] = discovery
        found.evidence[discovery.evidence] += 1
        found.discoveries += 1
        found.brokers += bool(discovery.organization.broker)

    standings = {}
    for case in Case.objects.prefetch_related("events"):
        found = result.get(case.subject_id)
        if found is None:
            continue
        found.cases_by_state[case.state] += 1
        standing = case_standing(case.events.all())
        standings[(case.subject_id, case.organization_id)] = standing
        if standing.outcome:
            found.outcomes[standing.outcome] += 1
            if standing.outcome == REMOVED and standing.suppression_confirmed:
                found.removed_confirmed += 1

    for key in standings.keys() | discoveries.keys():
        found = result[key[0]]
        standing = standings.get(key, Standing())
        discovery = discoveries.get(key)
        if standing.outcome == REMOVED:
            found.removed += 1
        elif standing.listing_known:
            found.holding += 1
        elif (
            standing.outcome != NOTHING_HELD
            and discovery is not None
            and discovery.status != Discovery.Status.IGNORED
            and discovery.evidence in scanner.ACCOUNT_OR_BETTER
        ):
            found.holding += 1
    return result


def compute(subject_id: int | None = None) -> Figures:
    """Figures for one Subject, or for the household when ``subject_id`` is None."""
    per_subject = compute_all()
    if subject_id is None:
        return combine(per_subject.values())
    return per_subject.get(subject_id, Figures())


# --- Per Organization (this instance only) -------------------------------------------------


@dataclass(frozen=True)
class Round:
    """One request round: when it was sent, and when and how fast the Organization first answered."""

    days_to_answer: int | None
    on_time: bool | None  # None until answered


def _round_deadline_events(round_events):
    """The deadline events of a round up to its first answer: the send and any extension.

    A reminder does not move the deadline here: an answer that needed a reminder came late.
    """
    result = []
    for index, event in enumerate(round_events):
        if index == 0:
            result.append(deadlines.Event(deadlines.EventKind.SENT, event.occurred_on))
        elif event.kind == CaseEvent.Kind.EXTENSION_ANNOUNCED:
            result.append(
                deadlines.Event(
                    deadlines.EventKind.EXTENSION_ANNOUNCED,
                    event.occurred_on,
                    with_reasons=bool(event.details.get("with_reasons")),
                )
            )
    return result


def _rounds(case, events) -> list[Round]:
    """The answered rounds of a Case. A round starts when a request (or reconsider reply) is sent."""
    groups = []
    for event in events:
        if event.kind == CaseEvent.Kind.SENT and event.details.get("draft_kind") in services.ROUND_STARTS:
            groups.append([event])
        elif groups:
            groups[-1].append(event)
    organization = case.organization
    rounds = []
    for group in groups:
        if any(event.kind == CaseEvent.Kind.BOUNCE for event in group[1:]):
            continue  # it never arrived: the clock never started
        answer = next((event for event in group[1:] if event.kind in ANSWER_KINDS), None)
        if answer is None:
            continue
        first_kind = lifecycle.DraftKind(group[0].details["draft_kind"])
        request = lifecycle.DRAFT_REQUEST.get(first_kind, lifecycle.Request.REMOVAL)
        before = group[: group.index(answer)]
        deadline = deadlines.compute_deadline(
            drafting.jurisdiction_for(organization),
            drafting.country_for(organization),
            _round_deadline_events(before),
            kind=request,
        )
        overdue_from = deadline.overdue_from
        rounds.append(
            Round(
                days_to_answer=(answer.occurred_on - group[0].occurred_on).days,
                on_time=overdue_from is None or answer.occurred_on < overdue_from,
            )
        )
    return rounds


@dataclass
class OrganizationFigures:
    organization: object
    cases: int = 0
    days: list[int] = field(default_factory=list)
    on_time: int = 0
    id_demands: int = 0

    @property
    def answered(self) -> int:
        return len(self.days)

    @property
    def median_days(self) -> float | None:
        return statistics.median(self.days) if self.days else None

    @property
    def on_time_percent(self) -> int | None:
        return round(100 * self.on_time / self.answered) if self.answered else None


def organization_figures() -> list[OrganizationFigures]:
    """One row per Organization with at least one Case, sorted by name. All Subjects of this instance."""
    rows: dict[int, OrganizationFigures] = {}
    for case in Case.objects.select_related("organization").prefetch_related("events"):
        row = rows.setdefault(case.organization_id, OrganizationFigures(case.organization))
        row.cases += 1
        events = list(case.events.all())
        row.id_demands += sum(event.kind == CaseEvent.Kind.ID_OR_DETAILS_ASKED for event in events)
        for found in _rounds(case, events):
            row.days.append(found.days_to_answer)
            row.on_time += bool(found.on_time)
    return sorted(rows.values(), key=lambda row: (row.organization.name.lower(), row.organization.pk))
