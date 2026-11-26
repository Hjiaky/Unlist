# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Re-checks (#51): intervals, the scheduler job, the early re-check guard and suggestion, returned Listings."""

from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from unlist.cases import lifecycle, rechecks, sending, services
from unlist.cases.lifecycle import Action, CaseState, Request, State
from unlist.cases.models import CaseEvent, Draft
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.core import scheduler
from unlist.mail.models import Discovery
from unlist.subjects.models import Mailbox


def days(n):
    return DAY0 + timedelta(days=n)


def at_noon(day):
    return timezone.make_aware(datetime(day.year, day.month, day.day, 12, 0))


class RecheckFixtures:
    def setUp(self):
        self.subject = make_subject()

    def open(self, *, broker=True, slug="acme", **fields):
        organization = make_organization(slug=slug, name=slug.upper(), broker=broker, **fields)
        case = services.open_case(self.subject, organization, on=DAY0)
        send(case, DAY0)
        return case

    def removed(self, *, broker=True, suppression=True, slug="acme", **fields):
        """A Case resting after "removed" on day 32."""
        case = self.open(broker=broker, slug=slug, **fields)
        services.record_outcome(case, "listing_found", on=days(5))
        services.request_removal(case, on=days(5))
        send(case, days(5))
        services.record_outcome(case, "removed", on=days(32), suppression_confirmed=suppression)
        case.refresh_from_db()
        return case

    def nothing_held(self, *, broker=True, slug="acme", **fields):
        case = self.open(broker=broker, slug=slug, **fields)
        services.record_outcome(case, "nothing_held", on=days(10))
        case.refresh_from_db()
        return case


class IntervalTests(RecheckFixtures, TestCase):
    def test_broker_rests_90_days_after_removed(self):
        case = self.removed()
        self.assertEqual((case.state, case.recheck_on), (State.RESTING, days(32 + 90)))

    def test_broker_rests_90_days_after_nothing_held(self):
        case = self.nothing_held()
        self.assertEqual((case.state, case.recheck_on), (State.RESTING, days(10 + 90)))

    def test_others_rest_365_days_after_removed(self):
        case = self.removed(broker=False, suppression=False)
        self.assertEqual((case.state, case.recheck_on), (State.RESTING, days(32 + 365)))

    def test_no_recheck_after_nothing_held_for_others(self):
        case = self.nothing_held(broker=False)
        self.assertEqual((case.state, case.recheck_on), (State.CLOSED, None))

    def test_no_recheck_after_kept_by_choice(self):
        case = self.open()
        services.record_outcome(case, "listing_found", on=days(5))
        services.keep_listing(case, on=days(6))
        case.refresh_from_db()
        self.assertEqual((case.state, case.recheck_on), (State.CLOSED, None))

    def test_no_recheck_after_an_accepted_refusal_of_access(self):
        case = self.open()
        services.record_outcome(case, "refused", on=days(5), exception="Trade secret")
        services.accept_refusal(case, on=days(6))
        case.refresh_from_db()
        self.assertEqual((case.state, case.recheck_on), (State.CLOSED, None))

    def test_organization_default_and_case_override(self):
        case = self.nothing_held(broker=False, slug="shop", recheck_default=180)
        self.assertEqual((case.state, case.recheck_on), (State.RESTING, days(10 + 180)))
        other = self.open(slug="other")
        services.set_recheck_override(other, "30")
        services.record_outcome(other, "nothing_held", on=days(10))
        other.refresh_from_db()
        self.assertEqual(other.recheck_on, days(10 + 30))


class OverrideMovesRecheckTests(RecheckFixtures, TestCase):
    def test_changing_the_override_moves_a_set_recheck_date(self):
        case = self.removed()
        services.set_recheck_override(case, "30")
        case.refresh_from_db()
        self.assertEqual((case.state, case.recheck_on), (State.RESTING, days(32 + 30)))
        note = case.events.filter(kind=CaseEvent.Kind.NOTE).last()
        self.assertEqual(note.details["recheck_on"], days(62).isoformat())

        services.set_recheck_override(case, "")
        case.refresh_from_db()
        self.assertEqual(case.recheck_on, days(32 + 90))

    def test_after_nothing_held_the_nothing_held_interval_counts(self):
        case = self.nothing_held(broker=False, slug="shop", recheck_default=180)
        services.set_recheck_override(case, "45")
        case.refresh_from_db()
        self.assertEqual(case.recheck_on, days(10 + 45))

    def test_close_closes_a_resting_case(self):
        case = self.removed()
        services.set_recheck_override(case, "close")
        case.refresh_from_db()
        self.assertEqual((case.state, case.recheck_on), (State.CLOSED, None))
        self.assertIn("close", case.result)

    def test_an_open_case_only_stores_the_override(self):
        case = self.open()
        services.set_recheck_override(case, "close")
        case.refresh_from_db()
        self.assertEqual((case.state, case.recheck_override, case.recheck_on), (State.WAITING, "close", None))


class SchedulerJobTests(RecheckFixtures, TestCase):
    def test_prepares_a_fresh_access_request_but_never_sends(self):
        case = self.removed()
        later = self.removed(slug="later")
        services.set_recheck_override(later, "400")
        Mailbox.objects.filter(subject=self.subject).update(mode=Mailbox.Mode.LIVE)
        live = mock.Mock(return_value=True)
        with mock.patch.object(sending, "live_senders", [live]):
            self.assertIsNone(rechecks.prepare_due_rechecks(at_noon(days(121))))
            results = scheduler.run_once(at_noon(days(122)))
        self.assertEqual(results["prepare_due_rechecks"], "1 re-check(s) prepared for approval.")
        live.assert_not_called()
        case.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(case.state, State.AWAITING_APPROVAL)
        draft = case.pending_draft
        self.assertEqual((draft.kind, draft.status), ("access_request", Draft.Status.AWAITING_APPROVAL))
        self.assertFalse(case.events.filter(kind=CaseEvent.Kind.SENT, occurred_on=days(122)).exists())
        self.assertEqual(case.events.filter(kind=CaseEvent.Kind.RECHECK_DUE).count(), 1)
        self.assertEqual(later.state, State.RESTING)

        # Run again: nothing more to do.
        self.assertIsNone(rechecks.prepare_due_rechecks(at_noon(days(123))))

    def test_skips_subjects_without_consent(self):
        case = self.removed()
        self.subject.consents.update(withdrawn_at=timezone.now())
        self.assertIsNone(rechecks.prepare_due_rechecks(at_noon(days(200))))
        case.refresh_from_db()
        self.assertEqual(case.state, State.RESTING)


class EarlyRecheckGuardTests(RecheckFixtures, TestCase):
    def test_never_earlier_than_the_interval(self):
        case = self.removed()
        with self.assertRaisesMessage(services.CaseError, "Too early"):
            services.prepare_recheck(case, on=days(100))
        with self.assertRaisesMessage(services.CaseError, "Say why"):
            rechecks.early_recheck(case, "   ", on=days(100))
        case.refresh_from_db()
        self.assertEqual(case.state, State.RESTING)
        self.assertFalse(case.drafts.filter(status=Draft.Status.AWAITING_APPROVAL).exists())

    def test_the_operator_may_ask_early_with_a_reason(self):
        case = self.removed()
        draft = rechecks.early_recheck(case, "New newsletter arrived", on=days(100))
        self.assertEqual((draft.kind, draft.status), ("access_request", Draft.Status.AWAITING_APPROVAL))
        event = case.events.get(kind=CaseEvent.Kind.RECHECK_DUE)
        self.assertEqual(event.details["early"], True)
        self.assertEqual(event.details["reason"], "New newsletter arrived")
        self.assertIn("New newsletter arrived", event.text)

    def test_on_the_due_date_no_reason_is_needed(self):
        case = self.removed()
        services.prepare_recheck(case, on=days(122))
        event = case.events.get(kind=CaseEvent.Kind.RECHECK_DUE)
        self.assertNotIn("early", event.details)

    def test_an_incomplete_answer_is_followed_up_not_rechecked(self):
        """EDPB 01/2022 para. 29: repeating after an incomplete answer is a reminder, not a new request."""
        case = self.open(broker=False)
        services.record_outcome(case, "listing_found", on=days(5))
        services.request_removal(case, on=days(5))
        send(case, days(5))
        services.record_outcome(case, "refused", on=days(20), exception="Only the account was closed")
        case.refresh_from_db()
        self.assertEqual(case.state, State.REFUSED)
        self.assertIsNone(case.recheck_on)
        self.assertIn(Action.ASK_RECONSIDER, services.available_actions(case))
        draft = services.ask_reconsider(case, on=days(21))
        self.assertEqual(draft.kind, "reconsider")


class EarlyRecheckSuggestionTests(RecheckFixtures, TestCase):
    def discovery(self, case, last_seen):
        return Discovery.objects.create(
            subject=self.subject, organization=case.organization, last_seen=at_noon(last_seen), email_count=3
        )

    def test_newer_mail_suggests_an_early_recheck(self):
        case = self.nothing_held()
        self.discovery(case, days(40))
        suggestion = rechecks.early_recheck_suggestion(case, today=days(50))
        self.assertEqual(suggestion.last_seen, days(40))
        self.assertIn("since it said it holds nothing", suggestion.text)

    def test_removed_wording(self):
        case = self.removed()
        self.discovery(case, days(40))
        self.assertIn("removed the Subject's data", rechecks.early_recheck_suggestion(case, today=days(50)).text)

    def test_no_suggestion_for_older_mail_or_without_mail(self):
        case = self.nothing_held()
        self.assertIsNone(rechecks.early_recheck_suggestion(case, today=days(50)))
        self.discovery(case, days(10))
        self.assertIsNone(rechecks.early_recheck_suggestion(case, today=days(50)))

    def test_no_suggestion_once_the_recheck_is_due_anyway(self):
        case = self.nothing_held()
        self.discovery(case, days(40))
        self.assertIsNone(rechecks.early_recheck_suggestion(case, today=days(100)))


class ReturnedListingTests(RecheckFixtures, TestCase):
    def recheck_finds_listing(self, suppression):
        case = self.removed(suppression=suppression)
        services.prepare_recheck(case, on=days(122))
        send(case, days(122))
        services.record_outcome(case, "listing_found", on=days(130))
        case.refresh_from_db()
        return case

    def test_returned_listing_after_a_suppression_record_offers_a_complaint(self):
        case = self.recheck_finds_listing(suppression=True)
        self.assertEqual(case.state, State.LISTING_FOUND)
        actions = services.available_actions(case)
        self.assertIn(Action.DRAFT_COMPLAINT, actions)
        self.assertIn(Action.REQUEST_REMOVAL, actions)
        self.assertEqual(rechecks.returned_listing(case).occurred_on, days(32))
        with mock.patch.object(services, "complaint_drafters", []):
            services.draft_complaint(case, on=days(131))
        case.refresh_from_db()
        self.assertEqual(case.state, State.COMPLAINT_DRAFT)

    def test_without_a_suppression_record_no_complaint_is_offered(self):
        case = self.recheck_finds_listing(suppression=False)
        self.assertNotIn(Action.DRAFT_COMPLAINT, services.available_actions(case))
        self.assertIsNone(rechecks.returned_listing(case))
        with self.assertRaisesMessage(services.IllegalStep, "only drafted after"):
            services.draft_complaint(case, on=days(131))

    def test_lifecycle_rule(self):
        found = CaseState(state=State.LISTING_FOUND, request=Request.ACCESS, broker=True)
        self.assertFalse(lifecycle.can(found, Action.DRAFT_COMPLAINT))
        result = lifecycle.transition(
            CaseState(state=State.LISTING_FOUND, request=Request.ACCESS, broker=True, suppression_record=True),
            Action.DRAFT_COMPLAINT,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.case.state, State.COMPLAINT_DRAFT)
        self.assertIn("Suppression Record", result.text)


class RecheckPageTests(RecheckFixtures, TestCase):
    def setUp(self):
        super().setUp()
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)

    def test_suggestion_and_early_recheck_on_the_case_page(self):
        case = self.nothing_held()
        services.set_recheck_override(case, "1000")  # the re-check lies in the future
        Discovery.objects.create(subject=self.subject, organization=case.organization, last_seen=timezone.now())
        page = self.client.get(f"/cases/{case.pk}/")
        self.assertContains(page, "New mail from this Organization since it said it holds nothing")
        self.assertContains(page, "Prepare an early re-check")

        response = self.client.post(f"/cases/{case.pk}/early-recheck/", {"reason": ""}, follow=True)
        self.assertContains(response, "Say why")
        case.refresh_from_db()
        self.assertEqual(case.state, State.RESTING)

        response = self.client.post(f"/cases/{case.pk}/early-recheck/", {"reason": "New mail since"}, follow=True)
        self.assertContains(response, "Early re-check prepared")
        case.refresh_from_db()
        self.assertEqual(case.state, State.AWAITING_APPROVAL)
        self.assertEqual(case.events.get(kind=CaseEvent.Kind.RECHECK_DUE).details["reason"], "New mail since")

    def test_returned_listing_panel(self):
        case = self.removed()
        services.prepare_recheck(case, on=days(122))
        send(case, days(122))
        services.record_outcome(case, "listing_found", on=days(130))
        page = self.client.get(f"/cases/{case.pk}/")
        self.assertContains(page, "The Listing has returned")
        self.assertContains(page, "Draft a Complaint")

    def test_override_form_moves_the_date(self):
        case = self.removed()
        self.client.post(f"/cases/{case.pk}/recheck/", {"recheck_override": "60"})
        case.refresh_from_db()
        self.assertEqual(case.recheck_on, days(32 + 60))
