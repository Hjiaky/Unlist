# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Ticket #42: deadline engine. Pure unittest, no database."""

import unittest
from datetime import date

from unlist.cases.deadlines import (
    Event,
    EventKind,
    ExtensionIgnoredReason,
    Jurisdiction,
    RequestKind,
    add_months,
    compute_deadline,
    easter_sunday,
    holiday_countries,
    is_working_day,
    next_working_day,
    public_holidays,
)

K = EventKind


def sent(on):
    return Event(K.SENT, on)


def moving_dates(result):
    return [step.on for step in result.steps if step.moves_deadline]


class MonthArithmeticTests(unittest.TestCase):
    def test_same_day_next_month(self):
        self.assertEqual(add_months(date(2024, 3, 5), 1), date(2024, 4, 5))
        self.assertEqual(compute_deadline("EU", None, [sent(date(2024, 3, 5))]).due_date, date(2024, 4, 5))

    def test_last_day_when_the_day_does_not_exist(self):
        self.assertEqual(add_months(date(2026, 8, 31), 1), date(2026, 9, 30))
        self.assertEqual(compute_deadline("EU", None, [sent(date(2026, 8, 31))]).due_date, date(2026, 9, 30))

    def test_31_january_leap_and_non_leap_year(self):
        self.assertEqual(add_months(date(2028, 1, 31), 1), date(2028, 2, 29))
        self.assertEqual(add_months(date(2027, 1, 31), 1), date(2027, 2, 28))
        self.assertEqual(compute_deadline("EU", None, [sent(date(2028, 1, 31))]).due_date, date(2028, 2, 29))
        self.assertEqual(compute_deadline("EU", None, [sent(date(2025, 1, 31))]).due_date, date(2025, 2, 28))

    def test_month_end_fallback_is_explained(self):
        result = compute_deadline("EU", None, [sent(date(2026, 8, 31))])
        self.assertIn("no day 31", result.steps[0].text)
        self.assertIn("Wednesday 30 September 2026", result.steps[0].text)

    def test_add_months_across_the_year(self):
        self.assertEqual(add_months(date(2026, 11, 30), 3), date(2027, 2, 28))
        self.assertEqual(add_months(date(2026, 12, 15), 1), date(2027, 1, 15))


class WorkingDayTests(unittest.TestCase):
    def test_weekend_roll(self):
        # 7 November 2026 is a Saturday.
        result = compute_deadline("EU", None, [sent(date(2026, 10, 7))])
        self.assertEqual(result.due_date, date(2026, 11, 9))
        roll = [step for step in result.steps if step.on == date(2026, 11, 7) and step.moves_deadline]
        self.assertEqual(len(roll), 1)
        self.assertIn("weekend", roll[0].text)
        self.assertIn("Monday 9 November 2026", roll[0].text)

    def test_german_unity_day_roll(self):
        # 3 October 2024 is a Thursday and a public holiday in Germany.
        result = compute_deadline("EU", "DE", [sent(date(2024, 9, 3))])
        self.assertEqual(result.due_date, date(2024, 10, 4))
        self.assertTrue(result.holidays_known)
        self.assertTrue(any("German Unity Day" in step.text for step in result.steps if step.moves_deadline))
        # Without a country only weekends count.
        self.assertEqual(compute_deadline("EU", None, [sent(date(2024, 9, 3))]).due_date, date(2024, 10, 3))

    def test_uk_bank_holiday_roll(self):
        # 4 May 2026 is the Early May bank holiday.
        result = compute_deadline("UK", "GB", [sent(date(2026, 4, 4))])
        self.assertEqual(result.due_date, date(2026, 5, 5))
        self.assertTrue(any("Early May bank holiday" in step.text for step in result.steps))

    def test_uk_substitute_bank_holiday_roll(self):
        # Boxing Day 2026 is a Saturday, so Monday 28 December is the substitute day.
        result = compute_deadline("UK", "UK", [sent(date(2026, 11, 28))])
        self.assertEqual(result.country, "GB")
        self.assertEqual(result.due_date, date(2026, 12, 29))

    def test_unknown_country_uses_weekends_only(self):
        result = compute_deadline("EU", "US", [sent(date(2024, 9, 3))])
        self.assertEqual(result.due_date, date(2024, 10, 3))
        self.assertFalse(result.holidays_known)
        self.assertTrue(any("no public holidays for country US" in step.text for step in result.steps))

    def test_next_working_day_helpers(self):
        self.assertTrue(is_working_day(date(2026, 3, 2), "DE"))
        self.assertFalse(is_working_day(date(2026, 4, 3), "DE"))  # Good Friday
        self.assertEqual(next_working_day(date(2026, 4, 3), "DE"), date(2026, 4, 7))  # past Easter Monday
        self.assertEqual(next_working_day(date(2026, 4, 3), None), date(2026, 4, 3))


class HolidayDataTests(unittest.TestCase):
    def test_easter(self):
        known = {
            2024: date(2024, 3, 31),
            2025: date(2025, 4, 20),
            2026: date(2026, 4, 5),
            2027: date(2027, 3, 28),
            2038: date(2038, 4, 25),
            2285: date(2285, 3, 22),
        }
        for year, easter in known.items():
            self.assertEqual(easter_sunday(year), easter)

    def test_every_required_country_is_bundled_and_computes(self):
        required = {
            "DE",
            "AT",
            "GB",
            "FR",
            "NL",
            "BE",
            "IE",
            "IT",
            "ES",
            "LU",
            "DK",
            "SE",
            "FI",
            "PL",
            "CZ",
            "PT",
            "CH",
        }
        self.assertLessEqual(required, holiday_countries())
        for country in holiday_countries():
            for year in range(1990, 2101):
                holidays = public_holidays(country, year)
                self.assertGreaterEqual(len(holidays), 4, (country, year))
                self.assertTrue(all(day.year == year for day in holidays), (country, year))

    def test_england_and_wales_2026_and_2027(self):
        self.assertEqual(
            set(public_holidays("GB", 2026)),
            {
                date(2026, 1, 1),
                date(2026, 4, 3),
                date(2026, 4, 6),
                date(2026, 5, 4),
                date(2026, 5, 25),
                date(2026, 8, 31),
                date(2026, 12, 25),
                date(2026, 12, 26),
                date(2026, 12, 28),
            },
        )
        holidays_2027 = public_holidays("GB", 2027)
        # Christmas on Saturday and Boxing Day on Sunday: substitutes on Monday 27 and Tuesday 28.
        self.assertIn("substitute day for Christmas Day", holidays_2027[date(2027, 12, 27)])
        self.assertIn("substitute day for Boxing Day", holidays_2027[date(2027, 12, 28)])
        # New Year's Day 2022 was a Saturday: substitute Monday 3 January.
        self.assertIn(date(2022, 1, 3), public_holidays("GB", 2022))

    def test_special_rules(self):
        self.assertIn(date(2025, 2, 3), public_holidays("IE", 2025))  # first Monday of February
        self.assertIn(date(2030, 2, 1), public_holidays("IE", 2030))  # 1 February is a Friday
        self.assertIn(date(2023, 5, 5), public_holidays("DK", 2023))  # General Prayer Day, abolished 2024
        self.assertNotIn(date(2024, 4, 26), public_holidays("DK", 2024))
        self.assertIn(date(2026, 6, 19), public_holidays("SE", 2026))  # Midsummer Eve, a Friday
        self.assertIn(date(2026, 10, 4), public_holidays("IT", 2026))
        self.assertNotIn(date(2025, 10, 4), public_holidays("IT", 2025))
        self.assertEqual(public_holidays(None, 2026), {})


class PauseTests(unittest.TestCase):
    def test_eu_id_request_pauses_by_the_paused_days(self):
        events = [
            sent(date(2026, 3, 2)),
            Event(K.ID_OR_DETAILS_ASKED, date(2026, 3, 10)),
            Event(K.ID_OR_DETAILS_ANSWERED, date(2026, 3, 17)),
        ]
        result = compute_deadline(Jurisdiction.EU, None, events)
        self.assertEqual(result.due_date, date(2026, 4, 9))  # 2 April + 7 days
        self.assertFalse(result.paused)
        self.assertEqual(moving_dates(result), [date(2026, 3, 2), date(2026, 3, 10), date(2026, 3, 17)])
        answer = [step for step in result.steps if step.on == date(2026, 3, 17)][0]
        self.assertIn("7 days", answer.text)

    def test_eu_overlapping_pauses_count_once(self):
        events = [
            sent(date(2026, 3, 2)),
            Event(K.ID_OR_DETAILS_ASKED, date(2026, 3, 5)),
            Event(K.CLARIFICATION_ASKED, date(2026, 3, 7)),
            Event(K.ID_OR_DETAILS_ANSWERED, date(2026, 3, 10)),
            Event(K.CLARIFICATION_ANSWERED, date(2026, 3, 12)),
        ]
        self.assertEqual(compute_deadline("EU", None, events).due_date, date(2026, 4, 9))  # 2 April + 7 days

    def test_eu_clock_paused_while_unanswered(self):
        events = [sent(date(2026, 3, 2)), Event(K.ID_OR_DETAILS_ASKED, date(2026, 3, 5))]
        result = compute_deadline("EU", "DE", events)
        self.assertTrue(result.paused)
        self.assertEqual(result.paused_since, date(2026, 3, 5))
        self.assertEqual(result.paused_by, (K.ID_OR_DETAILS_ASKED,))
        self.assertIsNone(result.due_date)
        self.assertIsNone(result.overdue_from)

    def test_eu_question_after_the_deadline_does_not_pause(self):
        events = [
            sent(date(2026, 3, 2)),
            Event(K.ID_OR_DETAILS_ASKED, date(2026, 4, 10)),
        ]
        result = compute_deadline("EU", None, events)
        self.assertFalse(result.paused)
        self.assertEqual(result.due_date, date(2026, 4, 2))
        self.assertTrue(any("undue delay" in step.text for step in result.steps))

    def test_uk_id_request_restarts_the_month(self):
        events = [
            sent(date(2026, 3, 2)),
            Event(K.ID_OR_DETAILS_ASKED, date(2026, 3, 5)),
            Event(K.ID_OR_DETAILS_ANSWERED, date(2026, 3, 20)),
        ]
        result = compute_deadline("UK", "GB", events)
        self.assertEqual(result.clock_start, date(2026, 3, 20))
        self.assertEqual(result.due_date, date(2026, 4, 20))
        restart = [step for step in result.steps if step.on == date(2026, 3, 20)][0]
        self.assertTrue(restart.moves_deadline)
        self.assertIn("new start", restart.text)

    def test_uk_id_request_while_unanswered_pauses(self):
        events = [sent(date(2026, 3, 2)), Event(K.ID_OR_DETAILS_ASKED, date(2026, 3, 5))]
        result = compute_deadline("UK", "GB", events)
        self.assertEqual(result.paused_since, date(2026, 3, 5))
        self.assertIsNone(result.due_date)

    def test_uk_late_id_request_still_restarts_and_says_so(self):
        events = [
            sent(date(2026, 3, 2)),
            Event(K.ID_OR_DETAILS_ASKED, date(2026, 4, 10)),
            Event(K.ID_OR_DETAILS_ANSWERED, date(2026, 4, 14)),
        ]
        result = compute_deadline("UK", "GB", events)
        self.assertEqual(result.due_date, date(2026, 5, 14))
        self.assertTrue(any("had already passed" in step.text for step in result.steps))

    def test_uk_stopped_clock_example_gives_18_june(self):
        # ICO worked example: received 14 May, clarification asked 15 May, answered 18 May.
        events = [
            sent(date(2026, 5, 14)),
            Event(K.CLARIFICATION_ASKED, date(2026, 5, 15)),
            Event(K.CLARIFICATION_ANSWERED, date(2026, 5, 18)),
        ]
        result = compute_deadline("UK", "GB", events)
        self.assertEqual(result.due_date, date(2026, 6, 18))
        answer = [step for step in result.steps if step.on == date(2026, 5, 18)][0]
        self.assertTrue(answer.moves_deadline)
        self.assertIn("both inclusive", answer.text)
        self.assertIn("4 days", answer.text)

    def test_clarification_does_not_pause_a_removal_request(self):
        events = [
            sent(date(2026, 5, 14)),
            Event(K.CLARIFICATION_ASKED, date(2026, 5, 15)),
            Event(K.CLARIFICATION_ANSWERED, date(2026, 5, 18)),
        ]
        result = compute_deadline("UK", None, events, kind=RequestKind.REMOVAL)
        self.assertEqual(result.due_date, date(2026, 6, 15))  # 14 June is a Sunday


class ExtensionTests(unittest.TestCase):
    def events(self, *extensions):
        return [sent(date(2026, 3, 2)), *extensions]

    def test_valid_extension(self):
        result = compute_deadline("EU", "DE", self.events(Event(K.EXTENSION_ANNOUNCED, date(2026, 3, 20), True)))
        self.assertEqual(result.due_date, date(2026, 6, 2))
        self.assertTrue(result.extended)
        self.assertTrue(result.extensions[0].accepted)
        self.assertIn(date(2026, 3, 20), moving_dates(result))

    def test_extension_on_the_last_day_of_the_first_month_counts(self):
        result = compute_deadline("EU", None, self.events(Event(K.EXTENSION_ANNOUNCED, date(2026, 4, 2), True)))
        self.assertEqual(result.due_date, date(2026, 6, 2))

    def test_first_month_end_is_rolled_before_judging_lateness(self):
        # The first month ends on Saturday 7 November 2026, so it runs to Monday 9 November.
        events = [sent(date(2026, 10, 7)), Event(K.EXTENSION_ANNOUNCED, date(2026, 11, 9), True)]
        result = compute_deadline("EU", None, events)
        self.assertTrue(result.extended)
        self.assertEqual(result.due_date, date(2027, 1, 7))

    def test_extension_after_the_first_month_is_ignored(self):
        result = compute_deadline("EU", None, self.events(Event(K.EXTENSION_ANNOUNCED, date(2026, 4, 10), True)))
        self.assertEqual(result.due_date, date(2026, 4, 2))
        self.assertFalse(result.extended)
        self.assertEqual(result.extensions[0].ignored_reason, ExtensionIgnoredReason.LATE)
        self.assertTrue(any("recorded and ignored" in step.text for step in result.steps))

    def test_extension_without_reasons_is_ignored(self):
        result = compute_deadline("UK", "GB", self.events(Event(K.EXTENSION_ANNOUNCED, date(2026, 3, 20), False)))
        self.assertEqual(result.due_date, date(2026, 4, 2))
        self.assertEqual(result.extensions[0].ignored_reason, ExtensionIgnoredReason.NO_REASONS)

    def test_second_extension_is_ignored(self):
        events = self.events(
            Event(K.EXTENSION_ANNOUNCED, date(2026, 3, 20), True),
            Event(K.EXTENSION_ANNOUNCED, date(2026, 3, 25), True),
        )
        result = compute_deadline("EU", "DE", events)
        self.assertEqual(result.due_date, date(2026, 6, 2))
        self.assertTrue(result.extensions[0].accepted)
        self.assertFalse(result.extensions[1].accepted)
        self.assertEqual(result.extensions[1].ignored_reason, ExtensionIgnoredReason.SECOND_EXTENSION)

    def test_extension_and_eu_pause_combine(self):
        events = self.events(
            Event(K.EXTENSION_ANNOUNCED, date(2026, 3, 20), True),
            Event(K.ID_OR_DETAILS_ASKED, date(2026, 3, 23)),
            Event(K.ID_OR_DETAILS_ANSWERED, date(2026, 3, 30)),
        )
        self.assertEqual(compute_deadline("EU", None, events).due_date, date(2026, 6, 9))  # 2 June + 7 days


class GraceAndReminderTests(unittest.TestCase):
    def test_overdue_three_days_after_the_due_date(self):
        result = compute_deadline("EU", None, [sent(date(2024, 3, 5))])
        self.assertEqual(result.overdue_from, date(2024, 4, 8))
        self.assertTrue(any("overdue from" in step.text for step in result.steps))

    def test_reminder_gives_fourteen_days(self):
        events = [sent(date(2026, 3, 2)), Event(K.REMINDER_SENT, date(2026, 4, 8))]
        result = compute_deadline("EU", None, events)
        self.assertEqual(result.reminder_due_date, date(2026, 4, 22))
        self.assertEqual(result.due_date, date(2026, 4, 2))

    def test_no_reminder(self):
        self.assertIsNone(compute_deadline("EU", None, [sent(date(2026, 3, 2))]).reminder_due_date)


class InputTests(unittest.TestCase):
    def test_unsent_request_has_no_deadline(self):
        with self.assertRaises(ValueError):
            compute_deadline("EU", None, [Event(K.REMINDER_SENT, date(2026, 3, 2))])

    def test_events_are_sorted_and_early_events_ignored(self):
        events = [
            Event(K.ID_OR_DETAILS_ANSWERED, date(2026, 3, 17)),
            sent(date(2026, 3, 2)),
            Event(K.ID_OR_DETAILS_ASKED, date(2026, 3, 10)),
            Event(K.EXTENSION_ANNOUNCED, date(2026, 2, 20), True),
        ]
        result = compute_deadline("EU", None, events)
        self.assertEqual(result.due_date, date(2026, 4, 9))
        self.assertFalse(result.extended)
        self.assertIn("before the request was sent", result.steps[0].text)

    def test_string_kinds_are_accepted(self):
        result = compute_deadline("UK", "gb", [Event("sent", date(2026, 4, 4))], kind="access")
        self.assertEqual(result.due_date, date(2026, 5, 5))

    def test_answer_without_question_moves_nothing(self):
        events = [sent(date(2026, 3, 2)), Event(K.CLARIFICATION_ANSWERED, date(2026, 3, 10))]
        result = compute_deadline("EU", None, events)
        self.assertEqual(result.due_date, date(2026, 4, 2))
        self.assertIn("no question was open", result.steps[1].text)


if __name__ == "__main__":
    unittest.main()
