# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The pure state machine and drafting helpers, without the database (#47)."""

from types import SimpleNamespace
from unittest import TestCase

from unlist.cases import drafting, lifecycle
from unlist.cases.lifecycle import Action, CaseState, DraftKind, Request, State, transition


def run(state, *actions):
    for action in actions:
        if isinstance(action, tuple):
            action, kwargs = action
        else:
            kwargs = {}
        result = transition(state, action, **kwargs)
        assert result.ok, (action, result.error)
        state = result.case
    return state


class LifecycleTests(TestCase):
    def test_illegal_steps_change_nothing_and_say_why(self):
        start = lifecycle.initial(broker=True)
        result = transition(start, Action.REQUEST_REMOVAL)
        self.assertIs(result.case, start)
        self.assertIn("Ask, then delete", result.error)
        self.assertEqual(transition(start, "no_such_action").error, "Unknown action.")

    def test_import_only_round_trip(self):
        state = run(lifecycle.initial(broker=True), Action.PREPARE_REQUEST, Action.APPROVE)
        self.assertEqual(state.state, State.HANDED_OVER)
        self.assertEqual(state.draft, DraftKind.ACCESS_REQUEST)
        result = transition(state, Action.MARK_SENT)
        self.assertEqual(result.delivered, DraftKind.ACCESS_REQUEST)
        self.assertEqual((result.case.state, result.case.request), (State.WAITING, Request.ACCESS))

    def test_live_approval_delivers(self):
        state = run(lifecycle.initial(), Action.PREPARE_REQUEST)
        result = transition(state, Action.APPROVE, sent=True)
        self.assertEqual(result.delivered, DraftKind.ACCESS_REQUEST)
        self.assertEqual(result.case.state, State.WAITING)
        self.assertFalse(transition(result.case, Action.MARK_SENT).ok)

    def test_direct_removal(self):
        state = lifecycle.initial(direct_removal=True)
        result = transition(state, Action.PREPARE_REQUEST)
        self.assertEqual(result.new_draft, DraftKind.REMOVAL_REQUEST)
        state = run(result.case, (Action.APPROVE, {"sent": True}))
        self.assertEqual(state.request, Request.REMOVAL)
        self.assertFalse(transition(state, Action.LISTING_FOUND).ok)
        self.assertEqual(transition(state, Action.NOTHING_HELD).case.state, State.CLOSED)

    def test_recheck_intervals(self):
        self.assertEqual(lifecycle.recheck_intervals(True), (90, 90))
        self.assertEqual(lifecycle.recheck_intervals(False), (None, 365))
        self.assertEqual(lifecycle.recheck_intervals(False, 120), (120, 120))
        self.assertEqual(lifecycle.recheck_intervals(True, 120, "30"), (30, 30))
        self.assertEqual(lifecycle.recheck_intervals(True, 120, "close"), (None, None))

    def test_removed_broker_rests_with_suppression_result(self):
        waiting = CaseState(state=State.WAITING, request=Request.REMOVAL, broker=True, recheck_after_removed=90)
        result = transition(waiting, Action.REMOVED, suppression_confirmed=True)
        self.assertEqual((result.case.state, result.recheck_in_days), (State.RESTING, 90))
        self.assertEqual(result.case.result, "Removed, Suppression Record confirmed")
        result = transition(waiting, Action.REMOVED)
        self.assertEqual(result.case.result, "Removed, no Suppression Record confirmed")

    def test_gentle_first(self):
        overdue = CaseState(state=State.OVERDUE, request=Request.ACCESS)
        self.assertIn("Gentle first", transition(overdue, Action.DRAFT_COMPLAINT).error)
        self.assertEqual(
            lifecycle.allowed(overdue, lifecycle.OUTCOMES)[:2], [Action.NOTHING_HELD, Action.LISTING_FOUND]
        )
        reminded = CaseState(state=State.OVERDUE, request=Request.ACCESS, reminders=1)
        self.assertTrue(lifecycle.can(reminded, Action.DRAFT_COMPLAINT))
        refused = CaseState(state=State.REFUSED, request=Request.ACCESS)
        self.assertTrue(lifecycle.can(refused, Action.DRAFT_COMPLAINT))

    def test_answer_while_reminder_pending(self):
        pending = CaseState(
            state=State.AWAITING_APPROVAL, request=Request.ACCESS, draft=DraftKind.REMINDER, draft_back=State.OVERDUE
        )
        result = transition(pending, Action.LISTING_FOUND)
        self.assertEqual(result.discarded_draft, DraftKind.REMINDER)
        self.assertEqual((result.case.state, result.case.draft), (State.LISTING_FOUND, None))
        first_request = CaseState(state=State.AWAITING_APPROVAL, draft=DraftKind.ACCESS_REQUEST, draft_back=State.FOUND)
        self.assertFalse(transition(first_request, Action.LISTING_FOUND).ok)

    def test_stop_and_reopen(self):
        state = run(lifecycle.initial(), Action.PREPARE_REQUEST)
        result = transition(state, Action.STOP, reason="consent withdrawn")
        self.assertEqual(result.discarded_draft, DraftKind.ACCESS_REQUEST)
        self.assertEqual((result.case.state, result.case.result), (State.CLOSED, "consent withdrawn"))
        self.assertFalse(transition(result.case, Action.STOP).ok)
        self.assertEqual(transition(result.case, Action.REOPEN).case.state, State.FOUND)


def organization(**fields):
    defaults = {
        "name": "Shop",
        "slug": "shop",
        "runs": ["Shop Brand"],
        "domains": ["shop.example"],
        "relevant_countries": ["de"],
        "supervisory_authority": "",
        "request_language": "",
        "required_elements": [],
        "email": "privacy@shop.example",
        "webform": "",
        "address": "",
        "preferred_channel": "",
    }
    return SimpleNamespace(**{**defaults, **fields})


def detail(kind, value, label=""):
    return SimpleNamespace(kind=kind, value=value, organization_label=label)


class DraftingTests(TestCase):
    def test_jurisdiction_and_country(self):
        self.assertEqual(drafting.jurisdiction_for(organization()), "EU")
        self.assertEqual(drafting.jurisdiction_for(organization(relevant_countries=["gb"])), "UK")
        self.assertEqual(drafting.jurisdiction_for(organization(relevant_countries=["gb", "de"])), "EU")
        self.assertEqual(
            drafting.jurisdiction_for(organization(relevant_countries=["all"], supervisory_authority="gbico")), "UK"
        )
        self.assertIsNone(drafting.country_for(organization(relevant_countries=["all"])))
        self.assertEqual(drafting.country_for(organization(relevant_countries=["all", "at"])), "AT")

    def test_identifying_lines_only_what_is_asked(self):
        details = [
            detail("customer_number", "123", "shop.example"),
            detail("customer_number", "999", "Other Shop"),
            detail("date_of_birth", "1 April 1990"),
            detail("previous_address", "1 Old Road"),
            detail("other", "nickname"),
        ]
        nothing_asked = organization()
        self.assertEqual(drafting.identifying_lines(nothing_asked, details, "en"), [])
        asks = organization(
            required_elements=[
                {"desc": "Kundennummer", "type": "input"},
                {"desc": "Adresse", "type": "address"},
                {"desc": "Voranschriften der letzten zwei Jahre", "type": "address"},
                {"desc": "Geburtsdatum", "type": "birthdate", "optional": True},
                {"desc": "Username", "type": "input"},
            ]
        )
        self.assertEqual(
            drafting.identifying_lines(asks, details, "de"),
            ["Kundennummer: 123", "Frühere Anschrift: 1 Old Road", "Geburtsdatum: 1 April 1990"],
        )

    def test_channel_and_dates(self):
        self.assertEqual(drafting.choose_channel(organization()), ("email", "privacy@shop.example"))
        letter = organization(email="", address="Shop GmbH\nStraße 1", preferred_channel="letter")
        self.assertEqual(drafting.choose_channel(letter), ("letter", "Shop GmbH\nStraße 1"))
        preferred_missing = organization(preferred_channel="webform")
        self.assertEqual(drafting.choose_channel(preferred_missing)[0], "email")
        from datetime import date

        self.assertEqual(drafting.format_date(date(2026, 10, 2), "de"), "2. Oktober 2026")
        self.assertEqual(drafting.format_date(date(2026, 10, 2), "en"), "2 October 2026")
