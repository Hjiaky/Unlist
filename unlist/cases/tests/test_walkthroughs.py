# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The eight walkthroughs of docs/prototypes/request-lifecycle.html, against the real model (#47).

All run in import-only mode: where the prototype approves in live mode (approving sends), the
Subject here sends the handed-over draft and marks it sent on the same day. "Time passes" is
the overdue check the scheduler runs (``services.mark_overdue_if_due``) on the given day.
"""

from datetime import timedelta

from django.test import TestCase

from unlist.cases import services
from unlist.cases.deadlines import add_months, next_working_day
from unlist.cases.lifecycle import Action, State
from unlist.cases.models import CaseEvent, Draft
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send


def days(n):
    return DAY0 + timedelta(days=n)


class WalkthroughTests(TestCase):
    def setUp(self):
        self.subject = make_subject()

    def open(self, broker):
        organization = make_organization(broker=broker)
        case = services.open_case(self.subject, organization, on=DAY0)
        self.assertEqual(case.state, State.AWAITING_APPROVAL)
        self.assertEqual(case.pending_draft.kind, "access_request")
        return case

    def assertState(self, case, state):
        case.refresh_from_db()
        self.assertEqual(case.state, state)

    def test_happy_path(self):
        case = self.open(broker=True)
        send(case, DAY0)
        self.assertState(case, State.WAITING)
        self.assertIsNotNone(case.due_date)

        services.record_outcome(case, "listing_found", on=days(12))
        self.assertState(case, State.LISTING_FOUND)
        self.assertIsNone(case.due_date)

        draft = services.request_removal(case, on=days(12))
        self.assertEqual(draft.kind, "removal_request")
        self.assertIn("suppression record", draft.body)
        send(case, days(12))
        self.assertState(case, State.WAITING)
        self.assertEqual(services.case_deadline(case).clock_start, days(12))

        event = services.record_outcome(case, "removed", on=days(32), suppression_confirmed=True)
        self.assertTrue(event.suppression_confirmed)
        self.assertState(case, State.RESTING)
        self.assertEqual(case.result, "Removed, Suppression Record confirmed")
        self.assertEqual(case.recheck_on, days(32 + 90))

        draft = services.prepare_recheck(case, on=days(122))
        self.assertState(case, State.AWAITING_APPROVAL)
        self.assertEqual(draft.kind, "access_request")
        self.assertEqual(draft.status, Draft.Status.AWAITING_APPROVAL)

    def test_nothing_held(self):
        case = self.open(broker=False)
        send(case, DAY0)
        services.record_outcome(case, "nothing_held", on=days(7))
        self.assertState(case, State.CLOSED)
        self.assertEqual(case.result, "Nothing held")
        self.assertIsNone(case.recheck_on)
        self.assertEqual(case.drafts.filter(kind="removal_request").count(), 0)

    def test_silence(self):
        case = self.open(broker=True)
        send(case, DAY0)
        deadline = services.case_deadline(case)
        self.assertEqual(deadline.due_date, next_working_day(add_months(DAY0, 1), "DE"))

        self.assertFalse(services.mark_overdue_if_due(case, today=deadline.due_date))
        self.assertState(case, State.WAITING)
        self.assertTrue(services.mark_overdue_if_due(case, today=deadline.due_date + timedelta(days=7)))
        self.assertState(case, State.OVERDUE)

        with self.assertRaisesMessage(services.IllegalStep, "Gentle first"):
            services.draft_complaint(case)

        reminder = services.send_reminder(case, on=days(40))
        self.assertEqual(reminder.kind, "reminder")
        self.assertIn(case.reference, reminder.subject_line)
        send(case, days(40))
        self.assertState(case, State.WAITING)
        self.assertEqual(case.overdue_from, days(40 + 14 + 3))

        self.assertTrue(services.mark_overdue_if_due(case, today=days(70)))
        self.assertState(case, State.OVERDUE)
        services.draft_complaint(case, on=days(70))
        self.assertState(case, State.COMPLAINT_DRAFT)
        services.complaint_lodged(case, on=days(72))
        self.assertState(case, State.COMPLAINT_LODGED)

        services.record_outcome(case, "listing_found", on=days(80))
        self.assertState(case, State.LISTING_FOUND)

    def test_id_demand_and_extension(self):
        case = self.open(broker=False)
        send(case, DAY0)
        self.assertEqual(case.due_date, next_working_day(add_months(DAY0, 1), "DE"))

        services.record_outcome(case, "id_or_details_asked", on=days(7))
        self.assertState(case, State.PAUSED)
        self.assertIsNone(case.due_date)
        self.assertFalse(services.mark_overdue_if_due(case, today=days(200)))
        self.assertState(case, State.PAUSED)

        draft = services.push_back(case, on=days(14))
        self.assertEqual(draft.kind, "id_pushback")
        send(case, days(14))
        self.assertState(case, State.WAITING)
        self.assertEqual(case.due_date, next_working_day(add_months(DAY0, 1) + timedelta(days=7), "DE"))

        event = services.record_outcome(case, "extension_announced", on=days(14), with_reasons=True)
        self.assertEqual(event.details["extension"], "accepted")
        case.refresh_from_db()
        extended = next_working_day(add_months(DAY0, 3) + timedelta(days=7), "DE")
        self.assertEqual(case.due_date, extended)

        event = services.record_outcome(case, "extension_announced", on=days(15), with_reasons=True)
        self.assertEqual(event.details["extension"], "ignored: second_extension")
        case.refresh_from_db()
        self.assertEqual(case.due_date, extended)
        self.assertState(case, State.WAITING)

    def test_refusal(self):
        case = self.open(broker=False)
        send(case, DAY0)
        services.record_outcome(case, "listing_found", on=days(5))
        services.request_removal(case, on=days(5))
        send(case, days(5))
        event = services.record_outcome(case, "refused", on=days(20), exception="Retention duty under tax law")
        self.assertEqual(event.exception_text, "Retention duty under tax law")
        self.assertState(case, State.REFUSED)
        self.assertIn(Action.ASK_RECONSIDER, services.available_actions(case))
        self.assertIn(Action.DRAFT_COMPLAINT, services.available_actions(case))

        services.accept_refusal(case, on=days(21))
        self.assertState(case, State.RESTING)
        self.assertEqual(case.recheck_on, days(21 + 365))

    def test_import_only(self):
        case = self.open(broker=True)
        draft = case.pending_draft
        services.approve(draft, on=DAY0)
        self.assertState(case, State.HANDED_OVER)
        self.assertIsNone(services.case_deadline(case))
        self.assertFalse(services.mark_overdue_if_due(case, today=days(3)))

        services.mark_sent(draft, on=days(3))
        self.assertState(case, State.WAITING)
        self.assertEqual(services.case_deadline(case).clock_start, days(3))

        services.record_outcome(case, "nothing_held", on=days(13))
        self.assertState(case, State.RESTING)
        self.assertEqual(case.recheck_on, days(13 + 90))

    def test_still_a_customer(self):
        case = self.open(broker=False)
        send(case, DAY0)
        services.record_outcome(case, "listing_found", on=days(4))
        services.keep_listing(case, on=days(5))
        self.assertState(case, State.CLOSED)
        self.assertTrue(case.result.startswith("Kept by choice"))
        self.assertIsNone(case.recheck_on)
        services.reopen(case, on=days(6))
        self.assertState(case, State.FOUND)

    def test_should_be_impossible(self):
        case = self.open(broker=True)
        draft = case.pending_draft

        def refused(step, message):
            before_state, before_events = case.state, case.events.count()
            with self.assertRaisesMessage(services.IllegalStep, message):
                step()
            case.refresh_from_db()
            self.assertEqual((case.state, case.events.count()), (before_state, before_events))

        refused(lambda: services.request_removal(case), "Ask, then delete")
        refused(lambda: services.record_outcome(case, "listing_found", on=DAY0), "has not been asked anything")
        refused(lambda: services.mark_sent(draft, on=DAY0), "approved and handed over")
        send(case, DAY0)
        refused(lambda: services.send_reminder(case), "missed its deadline")
        refused(lambda: services.draft_complaint(case), "only drafted after a missed deadline")
        refused(lambda: services.record_outcome(case, "removed", on=DAY0), "none is open")
        self.assertEqual(case.events.filter(kind=CaseEvent.Kind.SENT).count(), 1)
