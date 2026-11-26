# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""ID and details demands, pushback and authority letters (#50)."""

from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from unlist.cases import lifecycle, replies, sending, services
from unlist.cases.deadlines import add_months, next_working_day
from unlist.cases.forms import AuthorityLetterForm, DetailsChoiceForm, PortalForm, SendIdForm
from unlist.cases.lifecycle import Action, CaseState, Request, State
from unlist.cases.models import Attachment, CaseEvent
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.cases.tests.mail import DataDirMixin, make_message
from unlist.subjects.models import IdentifyingDetail, Mailbox


def days(n):
    return DAY0 + timedelta(days=n)


class DemandTestCase(DataDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)
        self.subject = make_subject()
        self.organization = make_organization()

    def open_and_send(self, organization=None, on=DAY0):
        case = services.open_case(self.subject, organization or self.organization, on=on)
        draft = send(case, on)
        return case, draft

    def ask_for_id(self, case, draft, on=None):
        """An ID demand arrives as a reply and the Operator confirms it."""
        message = make_message(
            in_reply_to=draft.message_id,
            body="To verify your identity, please send us a copy of your passport.",
        )
        reply = replies.ingest_message(self.subject, message, source="imap")
        self.assertEqual(reply.suggested_outcome, "id_or_details_asked")
        replies.confirm(reply, "id_or_details_asked", on=on or days(7))
        case.refresh_from_db()
        self.assertEqual(case.state, State.PAUSED)
        return reply


class NoIdDocumentTests(DemandTestCase):
    def test_the_id_demand_flow_has_no_file_field_at_all(self):
        case, draft = self.open_and_send()
        self.ask_for_id(case, draft)
        for form in (DetailsChoiceForm(case=case), SendIdForm(), PortalForm(), AuthorityLetterForm()):
            self.assertFalse(any(isinstance(field, forms.FileField) for field in form.fields.values()), form)
        for url in (f"/cases/{case.pk}/details/", f"/cases/{case.pk}/send-id/", f"/cases/{case.pk}/authority-letter/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, 'type="file"')
            self.assertNotContains(response, "multipart/form-data")

    def test_a_file_posted_to_the_id_flow_is_never_stored(self):
        case, draft = self.open_and_send()
        self.ask_for_id(case, draft)
        files_before = self.stored_files()
        passport = SimpleUploadedFile("passport.jpg", b"\xff\xd8 not really a passport", content_type="image/jpeg")
        response = self.client.post(f"/cases/{case.pk}/send-id/", {"decided": "on", "file": passport})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.stored_files(), files_before)
        self.assertFalse(Attachment.objects.filter(original_name="passport.jpg").exists())

    def test_reply_and_outcome_uploads_carry_the_warning(self):
        case, _draft = self.open_and_send()
        for url in (f"/cases/{case.pk}/", f"/cases/{case.pk}/outcome/"):
            self.assertContains(self.client.get(url), "Never upload an ID document")


class IdFlowTests(DemandTestCase):
    def test_pushback_draft(self):
        case, draft = self.open_and_send()
        self.ask_for_id(case, draft)
        self.client.post(f"/cases/{case.pk}/action/push_back/")
        pushback = case.pending_draft
        self.assertEqual(pushback.kind, "id_pushback")
        self.assertIn("Article 12(6)", pushback.body)

    def test_details_draft_with_only_the_chosen_details(self):
        case, draft = self.open_and_send()
        customer = IdentifyingDetail.objects.create(
            subject=self.subject, kind="customer_number", value="CN-12345", organization_label="ACME Ltd"
        )
        birth = IdentifyingDetail.objects.create(subject=self.subject, kind="date_of_birth", value="1 April 1990")
        IdentifyingDetail.objects.create(subject=self.subject, kind="previous_address", value="1 Old Road")
        self.ask_for_id(case, draft)
        page = self.client.get(f"/cases/{case.pk}/details/")
        self.assertContains(page, "Customer number: CN-12345")
        self.assertContains(page, "Previous address: 1 Old Road")
        self.client.post(f"/cases/{case.pk}/details/", {"details": [customer.pk, birth.pk]})
        reply = case.pending_draft
        self.assertEqual(reply.kind, "details_reply")
        self.assertIn("- Customer number: CN-12345", reply.body)
        self.assertIn("- Date of birth: 1 April 1990", reply.body)
        self.assertNotIn("Old Road", reply.body)

    def test_details_reply_needs_a_choice(self):
        case, draft = self.open_and_send()
        IdentifyingDetail.objects.create(subject=self.subject, kind="date_of_birth", value="1 April 1990")
        self.ask_for_id(case, draft)
        response = self.client.post(f"/cases/{case.pk}/details/", {})
        self.assertContains(response, "Choose at least one detail")
        self.assertIsNone(case.pending_draft)

    def test_id_sent_is_recorded_without_any_stored_file(self):
        Mailbox.objects.filter(subject=self.subject).update(mode=Mailbox.Mode.LIVE)
        case, draft = self.open_and_send()
        self.ask_for_id(case, draft)
        self.client.post(f"/cases/{case.pk}/send-id/", {"decided": "on"})
        case.refresh_from_db()
        id_reply = case.pending_draft
        self.assertEqual(id_reply.kind, "id_copy_reply")
        self.assertIn("I attach a copy of an identity document", id_reply.body)
        called = []
        saved = list(sending.live_senders)
        sending.live_senders[:] = [lambda d: called.append(d) or True]
        try:
            services.approve(id_reply, on=days(9))
        finally:
            sending.live_senders[:] = saved
        id_reply.refresh_from_db()
        self.assertEqual((id_reply.status, called), ("handed_over", []))  # never sent by Unlist
        attachments_before = Attachment.objects.count()
        services.mark_sent(id_reply, on=days(10))
        case.refresh_from_db()
        event = case.events.get(kind=CaseEvent.Kind.ID_SENT)
        self.assertEqual(event.occurred_on, days(10))
        self.assertIn("ID sent on", event.text)
        self.assertEqual(Attachment.objects.count(), attachments_before)
        self.assertEqual(case.state, State.WAITING)
        self.assertEqual(case.due_date, next_working_day(add_months(DAY0, 1) + timedelta(days=3), "DE"))

    def test_persistent_demand_offers_send_id_or_a_complaint(self):
        case, draft = self.open_and_send()
        self.ask_for_id(case, draft)
        self.assertNotIn(Action.DRAFT_COMPLAINT, services.available_actions(case))
        services.push_back(case, on=days(8))
        pushback = send(case, days(8))
        message = make_message(
            in_reply_to=pushback.message_id,
            subject="Re: identity",
            body="We still need a copy of your ID card.",
            message_id="<second@acme.example>",
        )
        reply = replies.ingest_message(self.subject, message, source="imap")
        replies.confirm(reply, "id_or_details_asked", on=days(12))
        case.refresh_from_db()
        actions = services.available_actions(case)
        self.assertIn(Action.SEND_ID, actions)
        self.assertIn(Action.DRAFT_COMPLAINT, actions)
        self.assertNotIn(Action.PUSH_BACK, actions)
        self.assertContains(self.client.get(f"/cases/{case.pk}/"), "The Organization insists on ID")
        services.draft_complaint(case, on=days(13))
        case.refresh_from_db()
        self.assertEqual(case.state, State.COMPLAINT_DRAFT)

    def test_portal_only_demand_is_handed_over(self):
        case, _draft = self.open_and_send()
        self.client.post(f"/cases/{case.pk}/portal/", {"url": "https://acme.example/privacy-portal"})
        event = case.events.get(kind=CaseEvent.Kind.PORTAL_HANDED_OVER)
        self.assertEqual(event.details["url"], "https://acme.example/privacy-portal")
        case.refresh_from_db()
        self.assertEqual(case.state, State.WAITING)


class ClockTests(DemandTestCase):
    def test_eu_pause(self):
        case, draft = self.open_and_send()
        self.ask_for_id(case, draft, on=days(7))
        self.assertIsNone(case.due_date)
        IdentifyingDetail.objects.create(subject=self.subject, kind="date_of_birth", value="1 April 1990")
        services.send_chosen_details(case, self.subject.details.all(), on=days(14))
        send(case, days(14))
        self.assertEqual(case.due_date, next_working_day(add_months(DAY0, 1) + timedelta(days=7), "DE"))

    def test_uk_restart(self):
        uk = make_organization("ukshop", "UK Shop", email="privacy@ukshop.example", relevant_countries=["gb"])
        case, draft = self.open_and_send(uk)
        self.ask_for_id(case, draft, on=days(7))
        services.push_back(case, on=days(14))
        send(case, days(14))
        self.assertEqual(case.due_date, next_working_day(add_months(days(14), 1), "GB"))

    def test_clarification_pauses_an_access_request_and_is_answered_by_details(self):
        case, draft = self.open_and_send()
        message = make_message(in_reply_to=draft.message_id, body="Please specify which data you are requesting.")
        reply = replies.ingest_message(self.subject, message, source="imap")
        self.assertEqual(reply.suggested_outcome, "clarification_asked")
        replies.confirm(reply, "clarification_asked", on=days(7))
        case.refresh_from_db()
        self.assertEqual(case.state, State.PAUSED)
        actions = services.available_actions(case)
        self.assertIn(Action.SEND_DETAILS, actions)
        self.assertNotIn(Action.PUSH_BACK, actions)
        self.assertNotIn(Action.SEND_ID, actions)
        services.send_details(case, ["The data you hold about my customer account"], on=days(14))
        send(case, days(14))
        self.assertEqual(case.due_date, next_working_day(add_months(DAY0, 1) + timedelta(days=7), "DE"))
        steps = " ".join(step.text for step in services.case_deadline(case).steps)
        self.assertIn("clarification", steps)

    def test_uk_clarification_excludes_the_days_from_ask_to_answer(self):
        uk = make_organization("ukshop", "UK Shop", email="privacy@ukshop.example", relevant_countries=["gb"])
        case, _draft = self.open_and_send(uk)
        services.record_outcome(case, "clarification_asked", on=days(7))
        services.send_details(case, ["My customer account"], on=days(14))
        send(case, days(14))
        self.assertEqual(case.due_date, next_working_day(add_months(DAY0, 1) + timedelta(days=8), "GB"))

    def test_clarification_does_not_apply_to_a_removal_request(self):
        case = services.open_case(self.subject, self.organization, direct_removal=True, on=DAY0)
        send(case, DAY0)
        with self.assertRaises(services.IllegalStep):
            services.record_outcome(case, "clarification_asked", on=days(3))


class AuthorityLetterTests(DemandTestCase):
    def test_a_letter_per_organization(self):
        case, _draft = self.open_and_send()
        beta_case, _ = self.open_and_send(make_organization("beta", "Beta GmbH", email="privacy@beta.example"))
        response = self.client.post(f"/cases/{case.pk}/authority-letter/", {"operator_name": "Sam Operator"})
        event = case.events.get(kind=CaseEvent.Kind.AUTHORITY_LETTER)
        self.assertRedirects(response, f"/cases/authority-letters/{event.pk}/")
        letter = event.details["letter"]
        self.assertIn("ACME Ltd", letter)
        self.assertIn("Sam Operator", letter)
        self.assertIn(case.reference, letter)
        self.assertNotIn("Beta", letter)
        self.assertEqual(event.details["organization"], "acme")

        beta_letter = services.authority_letter(beta_case, "Sam Operator", on=days(20))
        self.assertIn("Beta GmbH", beta_letter.details["letter"])
        self.assertNotIn("ACME", beta_letter.details["letter"])
        self.assertIn("23 March 2025", beta_letter.details["letter"])
        page = self.client.get(f"/cases/authority-letters/{event.pk}/")
        self.assertContains(page, "Sam Operator")
        self.assertContains(page, "for ACME Ltd only")


class LifecycleTests(SimpleTestCase):
    def test_clarification_and_pushback_rules(self):
        waiting = CaseState(state=State.WAITING, request=Request.ACCESS)
        paused = lifecycle.transition(waiting, Action.CLARIFICATION_ASKED).case
        self.assertEqual((paused.state, paused.asked), (State.PAUSED, "clarification"))
        self.assertFalse(lifecycle.can(paused, Action.PUSH_BACK))
        self.assertFalse(lifecycle.can(paused, Action.SEND_ID))
        self.assertTrue(lifecycle.can(paused, Action.SEND_DETAILS))
        removal = CaseState(state=State.WAITING, request=Request.REMOVAL)
        self.assertFalse(lifecycle.can(removal, Action.CLARIFICATION_ASKED))

    def test_one_pushback_per_request(self):
        state = CaseState(state=State.PAUSED, request=Request.ACCESS, asked="id_or_details", pushed_back=True)
        self.assertFalse(lifecycle.can(state, Action.PUSH_BACK))
        self.assertTrue(lifecycle.can(state, Action.SEND_ID))
        self.assertTrue(lifecycle.can(state, Action.DRAFT_COMPLAINT))
        self.assertFalse(lifecycle.can(CaseState(state=State.PAUSED, asked="id_or_details"), Action.DRAFT_COMPLAINT))
