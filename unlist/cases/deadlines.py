# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Deadline engine: when an Organization has to answer an Access Request or Removal Request.

Pure functions: no database, no network. The only file read is the bundled holiday data
(``data/holidays.json``), which holds rules rather than dates, so any year can be computed.

Call :func:`compute_deadline` with the jurisdiction (``"EU"`` or ``"UK"``, by the Organization's
Supervisory Authority), the Organization's country (ISO 3166 alpha-2, or ``None``) and the dated
events of one request. It returns a :class:`Deadline` with the due date, the overdue date, the
reminder date, whether the clock is paused, what happened to each announced extension, and a list
of plain-English :class:`Step` objects that a Complaint draft can quote as the timeline.

Rules (spec section 8; ``docs/research/gdpr-request-requirements.md`` section 2)
----------------------------------------------------------------------------------
- Clock start: the date the request was sent.
- One month: the same day-number in the following month, or the last day of that month if that
  day does not exist (Reg. 1182/71 Art. 3(2)(c), EDPB 01/2022 paras. 160-161; ICO counting guidance).
- EU, ID or details asked: the clock is paused from the ask until the answer is sent, and the due
  date moves by the paused days (answer date minus ask date). Clarification of a broad Access
  Request pauses the same way (EDPB 01/2022 para. 159). Overlapping pauses count once.
- UK, ID or details asked: the month starts afresh from the answer (UK GDPR Art. 12A: the
  "relevant time" is the latest of receipt of the request and receipt of the requested identity
  information). Clarification of an Access Request: the days from ask to answer, both inclusive,
  do not count (UK GDPR Art. 12A(5)), so the due date moves by that many days.
- Extension: two further months, accepted only if announced on or before the last day of the first
  month (after the working-day roll and any pauses) and with reasons, and only once. Any other
  announcement is recorded and ignored.
- Working days: a due date on a Saturday, Sunday or public holiday of the Organization's country
  moves to the next working day. Unknown country, or one without bundled data: weekends only.
- Grace: overdue from 3 days after the due date. A reminder gives 14 days. Both are fixed.

Order of operations
-------------------
1. Clock start: the send date (UK: replaced by the date the requested ID or details were sent).
2. Months: add 1 month to the clock start, or 3 months when an extension was accepted. The
   extended period is counted as three months from the clock start, not two months from the
   end of the first month, because Art. 12(3) extends the one period "by two further months"
   (and it is the later of the two readings, so Unlist never calls an answer late too early).
3. Paused and excluded days: added to that date as calendar days. This is what "the due date
   moves by the paused days" means, and matches the ICO's worked example (received 14 May,
   clarification asked 15 May and answered 18 May: the one-month deadline is extended by four
   days, due 18 June).
4. Working-day roll: applied once, to the final date only. Reg. 1182/71 Art. 3(4) and the ICO
   both roll the last day of a period; rolling an intermediate date would let one weekend move
   the deadline twice.
5. Grace (3 days) and the reminder period (14 days) are plain calendar days added to the due
   date and to the reminder date; they are Unlist's own margins, not legal periods, so they are
   not rolled.

Decisions the law leaves open (decided by agent, see ticket #42)
-----------------------------------------------------------------
- An extension announced on the last day of the first month counts as within the month.
- EU: a question asked after the deadline has passed does not pause the clock (EDPB 01/2022
  para. 159 allows a suspension only if the Organization asked "without undue delay").
  UK: a clarification asked after the deadline has passed changes nothing (the excluded days lie
  outside the period); an ID request asked after the deadline still restarts the month, because
  Art. 12A sets no condition on when it is asked, and a step records that the earlier deadline
  had already passed.
- Only the first ``SENT`` event starts the clock; a bounced send should not be passed in.
- Events dated before the clock start, answers with no open question, and a repeated question
  while the same question is still open are recorded in the steps and otherwise ignored.
- Clarification events only apply to Access Requests; for a Removal Request they are recorded
  and ignored.
- While the clock is paused there is no due date (``due_date`` is ``None``): it depends on when
  the answer is sent.
"""

import calendar
import json
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from functools import cache
from pathlib import Path

HOLIDAYS_FILE = Path(__file__).resolve().parent / "data" / "holidays.json"

GRACE_DAYS = 3
REMINDER_DAYS = 14
EXTENSION_MONTHS = 2

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_WEEKDAYS = {name.lower(): number for number, name in enumerate(_WEEKDAY_NAMES)}
_COUNTRY_ALIASES = {"UK": "GB"}


class Jurisdiction(StrEnum):
    """Which rule book applies, by the Organization's Supervisory Authority."""

    EU = "EU"
    UK = "UK"


class RequestKind(StrEnum):
    ACCESS = "access"
    REMOVAL = "removal"


class EventKind(StrEnum):
    SENT = "sent"
    ID_OR_DETAILS_ASKED = "id_or_details_asked"
    ID_OR_DETAILS_ANSWERED = "id_or_details_answered"
    CLARIFICATION_ASKED = "clarification_asked"
    CLARIFICATION_ANSWERED = "clarification_answered"
    EXTENSION_ANNOUNCED = "extension_announced"
    REMINDER_SENT = "reminder_sent"


_ANSWER_TO_ASK = {
    EventKind.ID_OR_DETAILS_ANSWERED: EventKind.ID_OR_DETAILS_ASKED,
    EventKind.CLARIFICATION_ANSWERED: EventKind.CLARIFICATION_ASKED,
}
_ASK_WORDS = {
    EventKind.ID_OR_DETAILS_ASKED: "proof of identity or further details",
    EventKind.CLARIFICATION_ASKED: "clarification of what the Access Request covers",
}


@dataclass(frozen=True)
class Event:
    """One dated thing that happened to a request. ``with_reasons`` matters only for extensions."""

    kind: EventKind
    on: date
    with_reasons: bool = False


class ExtensionIgnoredReason(StrEnum):
    LATE = "late"
    NO_REASONS = "no_reasons"
    SECOND_EXTENSION = "second_extension"


@dataclass(frozen=True)
class ExtensionDecision:
    announced_on: date
    accepted: bool
    ignored_reason: ExtensionIgnoredReason | None = None


@dataclass(frozen=True)
class Step:
    """One line of the timeline: what happened on ``on`` and which rule was applied.

    ``moves_deadline`` is true when this step started, paused, restarted or moved the deadline.
    """

    on: date
    text: str
    moves_deadline: bool = False


@dataclass(frozen=True)
class Deadline:
    jurisdiction: Jurisdiction
    country: str | None
    """Normalised country code (``"UK"`` becomes ``"GB"``), or ``None``."""
    holidays_known: bool
    """Whether public holidays were applied; if false, only weekends were skipped."""
    clock_start: date
    """The day the current period runs from: the send date, or in the UK the date ID was sent."""
    due_date: date | None
    """``None`` while the clock is paused."""
    overdue_from: date | None
    reminder_due_date: date | None
    paused_since: date | None
    paused_by: tuple[EventKind, ...]
    """The unanswered questions keeping the clock paused (``*_ASKED`` kinds)."""
    extended: bool
    extensions: tuple[ExtensionDecision, ...]
    steps: tuple[Step, ...]

    @property
    def paused(self) -> bool:
        return self.paused_since is not None


# --- Calendar arithmetic -----------------------------------------------------------------


def add_months(start: date, months: int) -> date:
    """Same day-number ``months`` later, or the last day of that month if the day does not exist."""
    years, month_index = divmod(start.month - 1 + months, 12)
    year = start.year + years
    month = month_index + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def easter_sunday(year: int) -> date:
    """Western (Gregorian) Easter Sunday, by the anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def format_date(day: date) -> str:
    """English long form, independent of the locale: ``Monday 5 October 2026``."""
    return f"{_WEEKDAY_NAMES[day.weekday()]} {day.day} {_MONTHS[day.month - 1]} {day.year}"


# --- Public holidays ---------------------------------------------------------------------


@cache
def _holiday_rules() -> dict:
    with HOLIDAYS_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)["countries"]


def normalise_country(country: str | None) -> str | None:
    if not country or not country.strip():
        return None
    code = country.strip().upper()
    return _COUNTRY_ALIASES.get(code, code)


def holiday_countries() -> frozenset[str]:
    """Country codes with bundled public-holiday data."""
    return frozenset(_holiday_rules())


def country_name(country: str) -> str:
    rules = _holiday_rules().get(country)
    return rules["name"] if rules else country


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    if nth > 0:
        first = date(year, month, 1)
        day = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    else:
        last = date(year, month, calendar.monthrange(year, month)[1])
        day = last - timedelta(days=(last.weekday() - weekday) % 7 + 7 * (-nth - 1))
    if day.month != month:
        raise ValueError(f"no weekday number {nth} in {year}-{month:02d}")
    return day


def _rule_date(rule: dict, year: int) -> date:
    kind = rule["rule"]
    if kind == "fixed":
        return date(year, rule["month"], rule["day"])
    if kind == "easter":
        return easter_sunday(year) + timedelta(days=rule["offset"])
    if kind == "nth_weekday":
        unless = rule.get("unless_day_falls_on")
        if unless:
            alternative = date(year, rule["month"], unless["day"])
            if alternative.weekday() == _WEEKDAYS[unless["weekday"]]:
                return alternative
        return _nth_weekday(year, rule["month"], _WEEKDAYS[rule["weekday"]], rule["nth"])
    if kind == "weekday_on_or_after":
        start = date(year, rule["month"], rule["day"])
        return start + timedelta(days=(_WEEKDAYS[rule["weekday"]] - start.weekday()) % 7)
    raise ValueError(f"unknown holiday rule {kind!r}")


def _holiday_label(rule: dict) -> str:
    local = rule.get("local_name")
    return f"{rule['name']} ({local})" if local and local != rule["name"] else rule["name"]


@cache
def _holidays(country: str, year: int) -> dict[date, str]:
    rules = _holiday_rules().get(country)
    if rules is None:
        return {}
    found: dict[date, str] = {}
    substitutes: list[tuple[date, str]] = []
    for rule in rules["holidays"]:
        if not rule.get("from_year", year) <= year <= rule.get("until_year", year):
            continue
        day = _rule_date(rule, year)
        label = _holiday_label(rule)
        found[day] = f"{found[day]} / {label}" if day in found else label
        if rule.get("substitute"):
            substitutes.append((day, label))
    # England and Wales: a bank holiday on a weekend gets the next weekday that is not
    # already a holiday ("bank holiday in lieu"), e.g. Christmas on Saturday and Boxing Day
    # on Sunday give Monday 27 and Tuesday 28 December.
    for day, label in sorted(substitutes):
        if day.weekday() < 5:
            continue
        candidate = day + timedelta(days=1)
        while candidate.weekday() >= 5 or candidate in found:
            candidate += timedelta(days=1)
        found[candidate] = f"substitute day for {label}"
    return found


def public_holidays(country: str | None, year: int) -> dict[date, str]:
    """Bundled public holidays (date -> English name) for one country and year; empty if unknown."""
    code = normalise_country(country)
    return dict(_holidays(code, year)) if code else {}


def _non_working_reason(day: date, country: str | None) -> str | None:
    if day.weekday() >= 5:
        return "a weekend day"
    if country:
        holiday = _holidays(country, day.year).get(day)
        if holiday:
            return f"a public holiday in {country_name(country)}: {holiday}"
    return None


def is_working_day(day: date, country: str | None) -> bool:
    return _non_working_reason(day, normalise_country(country)) is None


def next_working_day(day: date, country: str | None) -> date:
    """``day`` itself if it is a working day, else the first working day after it."""
    code = normalise_country(country)
    while _non_working_reason(day, code) is not None:
        day += timedelta(days=1)
    return day


# --- The engine --------------------------------------------------------------------------


def _days(n: int) -> str:
    return "1 day" if n == 1 else f"{n} days"


class _Clock:
    """Running state while the events are replayed in date order."""

    def __init__(self, jurisdiction: Jurisdiction, country: str | None, kind: RequestKind):
        self.jurisdiction = jurisdiction
        self.country = country
        self.kind = kind
        self.start: date | None = None
        self.months = 1
        self.shift = 0
        self.open_asks: dict[EventKind, date] = {}
        self.pause_began: date | None = None  # EU: start of the current (merged) pause
        self.extensions: list[ExtensionDecision] = []
        self.reminder_due: date | None = None
        self.steps: list[Step] = []

    # Helpers

    @property
    def eu(self) -> bool:
        return self.jurisdiction is Jurisdiction.EU

    def law(self, eu: str, uk: str) -> str:
        return eu if self.eu else uk

    def step(self, on: date, text: str, moves: bool = False) -> None:
        self.steps.append(Step(on=on, text=text, moves_deadline=moves))

    def raw_due(self, months: int | None = None) -> date:
        return add_months(self.start, self.months if months is None else months) + timedelta(days=self.shift)

    def due(self, months: int | None = None) -> date:
        return next_working_day(self.raw_due(months), self.country)

    def due_sentence(self) -> str:
        if self.open_asks:
            return "The clock stays paused while another question is unanswered."
        return f"The period now ends on {format_date(self.raw_due())}."

    # Events

    def sent(self, event: Event) -> None:
        if self.start is not None:
            self.step(
                event.on,
                f"Sent again on {format_date(event.on)}. The clock still runs from the first send date, "
                f"{format_date(self.start)}.",
            )
            return
        self.start = event.on
        rule = self.law(
            "Art. 12(3) GDPR: the Organization must answer within one month of receipt, counted under "
            "Reg. 1182/71 as EDPB Guidelines 01/2022 paras. 160-161 explain",
            "UK GDPR Arts. 12(3) and 12A: the Organization must answer within one month beginning with "
            "receipt, counted as the ICO's guidance explains",
        )
        one_month = add_months(event.on, 1)
        text = f"Request sent on {format_date(event.on)}; the clock starts on that day. {rule}. "
        if one_month.day != event.on.day:
            text += (
                f"The month after has no day {event.on.day}, so the period ends on the last day of that month, "
                f"{format_date(one_month)}."
            )
        else:
            text += f"One month later is {format_date(one_month)}."
        self.step(event.on, text, moves=True)

    def asked(self, event: Event) -> None:
        what = _ASK_WORDS[event.kind]
        when = format_date(event.on)
        if event.kind is EventKind.CLARIFICATION_ASKED and self.kind is RequestKind.REMOVAL:
            self.step(
                event.on,
                f"On {when} the Organization asked for {what}. A clarification only pauses the clock for an "
                "Access Request, so the deadline does not move.",
            )
            return
        if event.kind in self.open_asks:
            self.step(
                event.on,
                f"On {when} the Organization asked again for {what} while the earlier question, of "
                f"{format_date(self.open_asks[event.kind])}, was still unanswered. The clock stays paused.",
            )
            return
        passed_deadline = None
        if not self.open_asks and event.on > self.due():
            passed_deadline = self.due()
        if passed_deadline and (self.eu or event.kind is EventKind.CLARIFICATION_ASKED):
            reason = self.law(
                "a pause needs the question to be asked without undue delay (EDPB Guidelines 01/2022 para. 159)",
                "the days excluded by UK GDPR Art. 12A(5) would lie after the period had already ended",
            )
            self.step(
                event.on,
                f"On {when} the Organization asked for {what}, after the deadline of {format_date(passed_deadline)} "
                f"had passed. This does not pause the clock: {reason}.",
            )
            return

        self.open_asks[event.kind] = event.on
        if self.eu:
            if self.pause_began is None:
                self.pause_began = event.on
            text = (
                f"On {when} the Organization asked for {what}. The clock is paused from this day until the "
                "answer is sent (EDPB Guidelines 01/2022 para. 159)."
            )
        elif event.kind is EventKind.ID_OR_DETAILS_ASKED:
            text = (
                f"On {when} the Organization asked for {what}. Under UK GDPR Art. 12A the month starts afresh "
                "on the day the requested information is received."
            )
            if passed_deadline:
                text += (
                    f" The deadline of {format_date(passed_deadline)} had already passed when it asked; UK GDPR "
                    "Art. 12A still restarts the month."
                )
        else:
            text = (
                f"On {when} the Organization asked for {what}. Under UK GDPR Art. 12A(5) the days from this "
                "day until the day the answer is received, both inclusive, do not count."
            )
        self.step(event.on, text, moves=True)

    def answered(self, event: Event) -> None:
        ask_kind = _ANSWER_TO_ASK[event.kind]
        what = _ASK_WORDS[ask_kind]
        when = format_date(event.on)
        asked_on = self.open_asks.pop(ask_kind, None)
        if asked_on is None:
            self.step(event.on, f"On {when} the Subject sent {what}, but no question was open, so nothing moves.")
            return
        answer = f"On {when} the Subject answered the Organization's question of {format_date(asked_on)} ({what})."

        if self.eu:
            if self.open_asks:
                self.step(
                    event.on,
                    f"{answer} {self.due_sentence()}",
                    moves=True,
                )
                return
            paused = (event.on - self.pause_began).days
            began = self.pause_began
            self.pause_began = None
            self.shift += paused
            self.step(
                event.on,
                f"{answer} The clock was "
                f"paused from {format_date(began)} to {when}, {_days(paused)}, so the deadline moves by "
                f"{_days(paused)}. {self.due_sentence()}",
                moves=True,
            )
        elif ask_kind is EventKind.ID_OR_DETAILS_ASKED:
            self.start = event.on
            self.shift = 0
            months = "three months (one month and the two-month extension)" if self.months > 1 else "one month"
            text = f"{answer} Under UK GDPR Art. 12A this is the new start: the period is {months} from {when}. "
            self.step(event.on, text + self.due_sentence(), moves=True)
        else:
            counted_from = max(asked_on, self.start)
            excluded = (event.on - counted_from).days + 1 if event.on >= self.start else 0
            self.shift += excluded
            self.step(
                event.on,
                f"{answer} The days from "
                f"{format_date(counted_from)} to {when}, both inclusive, do not count (UK GDPR Art. 12A(5)): "
                f"{_days(excluded)}, so the deadline moves by {_days(excluded)}. {self.due_sentence()}",
                moves=True,
            )

    def extension(self, event: Event) -> None:
        when = format_date(event.on)
        if any(decision.accepted for decision in self.extensions):
            self.extensions.append(ExtensionDecision(event.on, False, ExtensionIgnoredReason.SECOND_EXTENSION))
            self.step(
                event.on,
                f"On {when} the Organization announced another extension. Only one extension of two months is "
                f"allowed ({self.law('Art. 12(3) GDPR', 'UK GDPR Art. 12A(3)')}), so it is recorded and ignored.",
            )
            return

        first_month_end = None if self.open_asks else self.due(months=1)
        late = first_month_end is not None and event.on > first_month_end
        problems = []
        if late:
            problems.append(f"it came after the first month ended on {format_date(first_month_end)}")
        if not event.with_reasons:
            problems.append("it gave no reasons for the delay")
        rule = self.law(
            "Art. 12(3) GDPR allows two further months only if the Organization says so within one month of "
            "receipt, with the reasons",
            "UK GDPR Art. 12A(3)-(4) allows two further months only if the Organization says so before the end "
            "of the first month, stating the reasons",
        )
        if problems:
            reason = ExtensionIgnoredReason.LATE if late else ExtensionIgnoredReason.NO_REASONS
            self.extensions.append(ExtensionDecision(event.on, False, reason))
            self.step(
                event.on,
                f"On {when} the Organization announced an extension, but {' and '.join(problems)}. {rule}, so the "
                "extension is recorded and ignored.",
            )
            return

        self.extensions.append(ExtensionDecision(event.on, True))
        self.months = 1 + EXTENSION_MONTHS
        within = (
            "while the clock was paused, so within the first month"
            if first_month_end is None
            else f"within the first month, which ended on {format_date(first_month_end)}"
        )
        self.step(
            event.on,
            f"On {when} the Organization announced an extension with reasons, {within}. {rule}; the period is "
            f"now three months from {format_date(self.start)}. {self.due_sentence()}",
            moves=True,
        )

    def reminder(self, event: Event) -> None:
        self.reminder_due = event.on + timedelta(days=REMINDER_DAYS)
        self.step(
            event.on,
            f"Reminder sent on {format_date(event.on)}, giving the Organization {REMINDER_DAYS} days, until "
            f"{format_date(self.reminder_due)}. This does not change the legal deadline.",
        )

    def finish(self) -> Deadline:
        due = overdue = paused_since = None
        if self.open_asks:
            paused_since = self.pause_began if self.eu else min(self.open_asks.values())
            waiting = " and ".join(_ASK_WORDS[kind] for kind in self.open_asks)
            self.step(
                paused_since,
                f"The clock has been paused since {format_date(paused_since)}, waiting for the Subject to send "
                f"{waiting}. The deadline is set again once the answer is sent.",
            )
        else:
            raw = self.raw_due()
            due = next_working_day(raw, self.country)
            if self.country is None:
                self.step(raw, "The Organization's country is unknown, so only weekends count as non-working days.")
            elif self.country not in holiday_countries():
                self.step(
                    raw,
                    f"Unlist has no public holidays for country {self.country}, so only weekends count as "
                    "non-working days.",
                )
            if due != raw:
                skipped = []
                day = raw
                while day < due:
                    skipped.append(f"{format_date(day)} is {_non_working_reason(day, self.country)}")
                    day += timedelta(days=1)
                rule = self.law("Reg. 1182/71 Art. 3(4), EDPB Guidelines 01/2022 para. 161", "ICO guidance")
                self.step(
                    raw,
                    f"{'; '.join(skipped)}. A deadline on a weekend or public holiday moves to the next working day "
                    f"({rule}): the deadline is {format_date(due)}.",
                    moves=True,
                )
            else:
                self.step(raw, f"{format_date(due)} is a working day, so the deadline is {format_date(due)}.")
            overdue = due + timedelta(days=GRACE_DAYS)
            self.step(
                due,
                f"Unlist treats the request as overdue from {format_date(overdue)}, {GRACE_DAYS} days after the "
                "deadline, to allow for differences in counting.",
            )
        return Deadline(
            jurisdiction=self.jurisdiction,
            country=self.country,
            holidays_known=self.country in holiday_countries() if self.country else False,
            clock_start=self.start,
            due_date=due,
            overdue_from=overdue,
            reminder_due_date=self.reminder_due,
            paused_since=paused_since,
            paused_by=tuple(self.open_asks),
            extended=self.months > 1,
            extensions=tuple(self.extensions),
            steps=tuple(self.steps),
        )


def compute_deadline(
    jurisdiction: Jurisdiction | str,
    country: str | None,
    events: list[Event] | tuple[Event, ...],
    *,
    kind: RequestKind | str = RequestKind.ACCESS,
) -> Deadline:
    """Replay a request's events and work out its deadline.

    ``events`` may come in any order; they are sorted by date, keeping the given order for events on
    the same day. Raises ``ValueError`` if no event is ``SENT``: an unsent request has no deadline.
    """
    jurisdiction = Jurisdiction(jurisdiction)
    clock = _Clock(jurisdiction, normalise_country(country), RequestKind(kind))
    # Sort by date; on the same day a send comes first, otherwise the given order is kept.
    ordered = sorted(
        (Event(EventKind(event.kind), event.on, event.with_reasons) for event in events),
        key=lambda event: (event.on, event.kind is not EventKind.SENT),
    )
    first_sent = next((event for event in ordered if event.kind is EventKind.SENT), None)
    if first_sent is None:
        raise ValueError("the request was never sent, so it has no deadline")

    handlers = {
        EventKind.SENT: clock.sent,
        EventKind.ID_OR_DETAILS_ASKED: clock.asked,
        EventKind.CLARIFICATION_ASKED: clock.asked,
        EventKind.ID_OR_DETAILS_ANSWERED: clock.answered,
        EventKind.CLARIFICATION_ANSWERED: clock.answered,
        EventKind.EXTENSION_ANNOUNCED: clock.extension,
        EventKind.REMINDER_SENT: clock.reminder,
    }
    for event in ordered:
        if clock.start is None and event is not first_sent:
            clock.step(
                event.on,
                f"An event ({event.kind.value.replace('_', ' ')}) is dated {format_date(event.on)}, before the "
                "request was sent, and is ignored.",
            )
            continue
        handlers[event.kind](event)
    return clock.finish()
