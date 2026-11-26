# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Reply matching, suggestions and the review queue (#49)."""

import mailbox
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from unlist.cases import replies, services, storage
from unlist.cases.lifecycle import State
from unlist.cases.models import Attachment, CaseEvent, Reply
from unlist.cases.replies import Suggestion, rules_suggestion
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.cases.tests.mail import ARRIVED, DataDirMixin, delivery_report, make_message
from unlist.mail import importer
from unlist.subjects.models import Mailbox

ON = ARRIVED.date()


class Registry:
    """Register suggesters for one test and restore the registry afterwards."""

    def __init__(self, *suggesters):
        self.suggesters = suggesters

    def __enter__(self):
        self.saved = list(replies.suggesters)
        replies.suggesters[:] = list(self.suggesters)

    def __exit__(self, *exc):
        replies.suggesters[:] = self.saved


class ReplyTestCase(DataDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.subject = make_subject()
        self.organization = make_organization()
        self.case = services.open_case(self.subject, self.organization, on=DAY0)
        self.draft = send(self.case, DAY0)

    def ingest(self, message, **kwargs):
        kwargs.setdefault("source", "imap")
        return replies.ingest_message(self.subject, message, **kwargs)


class MatchingTests(ReplyTestCase):
    def test_in_reply_to_names_a_sent_draft(self):
        reply = self.ingest(make_message(sender="someone@elsewhere.example", in_reply_to=self.draft.message_id))
        self.assertEqual((reply.case, reply.matched_by), (self.case, "in_reply_to"))
        self.assertEqual(reply.status, "to_confirm")
        self.assertEqual(reply.raw_attachment.case, self.case)
        self.assertEqual(reply.raw_attachment.content_type, "message/rfc822")
        self.assertTrue(storage.attachment_path(reply.raw_attachment).is_file())

    def test_references_name_a_sent_draft(self):
        references = f"<other@x.example> {self.draft.message_id}"
        reply = self.ingest(make_message(sender="someone@elsewhere.example", references=references))
        self.assertEqual((reply.case, reply.matched_by), (self.case, "in_reply_to"))

    def test_ticket_system_reply_in_a_new_thread_with_the_reference_in_the_subject(self):
        message = make_message(
            sender="Support <support@helpdesk-provider.example>",
            subject=f"[Ticket#88213] Re: Access request [Ref {self.case.reference}]",
        )
        reply = self.ingest(message)
        self.assertEqual((reply.case, reply.matched_by), (self.case, "reference"))

    def test_bare_reference_code_in_the_subject(self):
        reply = self.ingest(make_message(sender="a@b.example", subject=f"Your case {self.case.reference.lower()}"))
        self.assertEqual((reply.case, reply.matched_by), (self.case, "reference"))

    def test_authenticated_sender_domain_with_one_open_case(self):
        reply = self.ingest(make_message(authenticated_for="acme.example", subject="About your enquiry"))
        self.assertEqual((reply.case, reply.matched_by), (self.case, "sender_domain"))
        self.assertTrue(reply.authenticated)

    def test_sender_domain_not_authenticated_goes_to_the_unmatched_queue(self):
        reply = self.ingest(make_message(subject="About your enquiry"))
        self.assertIsNone(reply.case)
        self.assertTrue(reply.is_unmatched)
        self.assertTrue((self.data_dir / reply.raw_path).is_file())

    def test_sender_domain_with_two_open_cases_goes_to_the_unmatched_queue(self):
        other = make_organization("acme-sales", "ACME Sales", email="sales@acme.example")
        send(services.open_case(self.subject, other, on=DAY0), DAY0)
        reply = self.ingest(make_message(authenticated_for="acme.example"))
        self.assertTrue(reply.is_unmatched)

    def test_bulk_mail_from_the_organization_is_not_stored(self):
        message = make_message(
            authenticated_for="acme.example", headers={"List-Unsubscribe": "<mailto:u@acme.example>"}
        )
        self.assertIsNone(self.ingest(message))
        self.assertFalse(Reply.objects.exists())

    def test_mail_from_before_the_request_was_sent_is_not_stored(self):
        message = make_message(authenticated_for="acme.example", date=ARRIVED.replace(year=2024))
        self.assertIsNone(self.ingest(message))

    def test_unrelated_message_is_not_stored(self):
        self.assertIsNone(self.ingest(make_message(sender="news@unrelated.example", subject="Big sale")))
        self.assertFalse(Reply.objects.exists())
        self.assertEqual(self.stored_files(), [])

    def test_unknown_reference_like_code_is_queued(self):
        reply = self.ingest(make_message(sender="a@b.example", subject="Re: [Ref U-ZZZZ]"))
        self.assertTrue(reply.is_unmatched)

    def test_duplicates_are_taken_in_once(self):
        message = make_message(in_reply_to=self.draft.message_id, message_id="<same@acme.example>")
        self.assertIsNotNone(self.ingest(message))
        again = make_message(in_reply_to=self.draft.message_id, message_id="<SAME@acme.example>")
        self.assertIsNone(self.ingest(again, source="mbox"))
        self.assertEqual(Reply.objects.count(), 1)

    def test_own_messages_are_never_taken_in(self):
        sent = make_message(sender="Alex <alex@example.org>", subject=f"Request [Ref {self.case.reference}]")
        self.assertIsNone(self.ingest(sent))
        draft_copy = make_message(sender="x@y.example", message_id=self.draft.message_id)
        self.assertIsNone(self.ingest(draft_copy))
        self.assertIsNone(self.ingest(sent, case=self.case, source="upload"))
        self.assertFalse(Reply.objects.exists())

    def test_files_of_a_reply_are_stored_on_the_case(self):
        message = make_message(
            in_reply_to=self.draft.message_id,
            attachments=[("export.csv", b"name,email\nAlex,alex@example.org\n", "text/csv")],
        )
        reply = self.ingest(message)
        files = replies.reply_attachments(reply)
        self.assertEqual([file.original_name for file in files], ["export.csv"])
        self.assertEqual(files[0].case, self.case)
        self.assertEqual(storage.attachment_path(files[0]).read_bytes(), b"name,email\nAlex,alex@example.org\n")

    def test_html_only_reply_is_converted_to_text(self):
        html = "<html><head><style>p{}</style></head><body><p>We do not hold any data about you.</p>"
        html += "<blockquote>Your request text</blockquote></body></html>"
        reply = self.ingest(make_message(in_reply_to=self.draft.message_id, body=None, html=html))
        self.assertIn("We do not hold any data about you.", reply.body)
        self.assertIn("> Your request text", reply.body)
        self.assertNotIn("<p>", reply.body)
        self.assertEqual(reply.suggested_outcome, "nothing_held")

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ingest(make_message(), source="carrier pigeon")


class AutomaticTests(ReplyTestCase):
    def test_bounce_is_recorded_automatically(self):
        reply = self.ingest(delivery_report(self.draft.message_id))
        self.case.refresh_from_db()
        self.assertEqual((reply.kind, reply.status), ("bounce", "auto_recorded"))
        self.assertEqual(reply.matched_by, "in_reply_to")
        self.assertEqual(self.case.state, State.UNDELIVERABLE)
        self.assertEqual(reply.event.kind, CaseEvent.Kind.BOUNCE)
        self.assertEqual(reply.event.occurred_on, ON)
        self.assertEqual(reply.raw_attachment.event, reply.event)

    def test_bounce_matched_by_the_reference_of_the_returned_message(self):
        report = delivery_report("<unknown@example.org>", f"Access request [Ref {self.case.reference}]")
        reply = self.ingest(report)
        self.case.refresh_from_db()
        self.assertEqual(reply.status, "auto_recorded")
        self.assertEqual(self.case.state, State.UNDELIVERABLE)

    def test_delayed_delivery_report_changes_nothing(self):
        reply = self.ingest(delivery_report(self.draft.message_id, action="delayed"))
        self.case.refresh_from_db()
        self.assertEqual(reply.kind, "auto_reply")
        self.assertEqual(self.case.state, State.WAITING)

    def test_bounce_that_cannot_be_recorded_waits_for_the_operator(self):
        services.record_outcome(self.case, "extension_announced", on=DAY0)
        services.record_outcome(self.case, "nothing_held", on=DAY0)
        reply = self.ingest(delivery_report(self.draft.message_id))
        self.assertEqual((reply.status, reply.suggested_outcome), ("to_confirm", "bounce"))

    def test_out_of_office_reply_is_attached_without_a_state_change(self):
        message = make_message(
            subject=f"Out of Office: Access request [Ref {self.case.reference}]",
            body="I am away until Monday.",
        )
        reply = self.ingest(message)
        self.case.refresh_from_db()
        self.assertEqual((reply.kind, reply.status), ("auto_reply", "auto_recorded"))
        self.assertEqual(self.case.state, State.WAITING)
        self.assertEqual(reply.event.kind, CaseEvent.Kind.NOTE)
        self.assertEqual(reply.raw_attachment.event, reply.event)

    def test_auto_submitted_header_marks_an_automatic_reply(self):
        for headers in ({"Auto-Submitted": "auto-replied"}, {"X-Autoreply": "yes"}):
            message = make_message(in_reply_to=self.draft.message_id, headers=headers, body="Your data was deleted.")
            reply = self.ingest(message)
            self.assertEqual(reply.kind, "auto_reply", headers)
        self.case.refresh_from_db()
        self.assertEqual(self.case.state, State.WAITING)

    def test_german_out_of_office_subject(self):
        reply = self.ingest(make_message(subject=f"Abwesenheitsnotiz: [Ref {self.case.reference}]"))
        self.assertEqual(reply.kind, "auto_reply")


class SuggestionTests(ReplyTestCase):
    def test_confirming_a_suggestion_records_the_outcome(self):
        message = make_message(
            in_reply_to=self.draft.message_id, body="We do not hold any personal data about you.\n\nKind regards"
        )
        reply = self.ingest(message)
        self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("nothing_held", "rules"))
        self.case.refresh_from_db()
        self.assertEqual(self.case.state, State.WAITING)  # no state change on a guess
        event = replies.confirm(reply, "nothing_held")
        self.case.refresh_from_db()
        reply.refresh_from_db()
        self.assertEqual(self.case.state, State.CLOSED)
        self.assertEqual((event.kind, event.occurred_on, event.details["reply"]), ("nothing_held", ON, reply.pk))
        self.assertEqual((reply.status, reply.event), ("confirmed", event))
        self.assertEqual(reply.raw_attachment.event, event)
        with self.assertRaises(services.CaseError):
            replies.confirm(reply, "nothing_held")

    def test_the_operator_may_choose_another_outcome_and_keep_it_without_one(self):
        reply = self.ingest(make_message(in_reply_to=self.draft.message_id, body="We received your request."))
        self.assertEqual(reply.suggested_outcome, "")
        event = replies.confirm(reply, replies.ATTACH_ONLY)
        self.case.refresh_from_db()
        self.assertEqual(event.kind, CaseEvent.Kind.NOTE)
        self.assertEqual(self.case.state, State.WAITING)

    def test_refusal_suggestion_carries_the_cited_exception(self):
        body = "We cannot delete your data. We must retain invoices for ten years under § 147 AO."
        reply = self.ingest(make_message(in_reply_to=self.draft.message_id, body=body))
        self.assertEqual(reply.suggested_outcome, "refused")
        self.assertIn("147 AO", reply.suggested_exception)
        replies.confirm(reply, "refused", exception=reply.suggested_exception)
        self.assertIn("147 AO", self.case.events.get(kind="refused").exception_text)

    def test_suggesters_are_asked_before_the_rules(self):
        seen = []

        def failing(reply):
            raise RuntimeError("model offline")

        def llm(reply):
            seen.append(reply.body)
            return Suggestion("listing_found", "llm", "The model read it")

        with Registry(failing, llm), self.assertLogs("unlist.cases", "WARNING"):
            reply = self.ingest(make_message(in_reply_to=self.draft.message_id, body="We do not hold any data."))
        self.assertEqual(seen, ["We do not hold any data."])
        self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("listing_found", "llm"))

    def test_a_suggester_returning_none_falls_back_to_the_rules(self):
        with Registry(lambda reply: None):
            reply = self.ingest(make_message(in_reply_to=self.draft.message_id, body="Keine Daten gespeichert."))
        self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("nothing_held", "rules"))


class UnmatchedQueueTests(ReplyTestCase):
    def test_assigning_moves_the_eml_onto_the_case(self):
        reply = self.ingest(make_message(body="Wir haben Ihre Daten gelöscht.", subject="Ihre Anfrage"))
        raw_path = self.data_dir / reply.raw_path
        replies.assign(reply, self.case)
        reply.refresh_from_db()
        self.assertEqual((reply.case, reply.matched_by, reply.raw_path), (self.case, "operator", ""))
        self.assertFalse(raw_path.exists())
        self.assertTrue(storage.attachment_path(reply.raw_attachment).is_file())
        self.assertEqual(reply.suggested_outcome, "removed")

    def test_dismissing_deletes_text_and_files_but_keeps_it_deduplicated(self):
        message = make_message(body="Hello", subject="Ihre Anfrage", message_id="<q@acme.example>")
        reply = self.ingest(message)
        replies.dismiss(reply)
        reply.refresh_from_db()
        self.assertEqual((reply.status, reply.body, reply.raw_path), ("dismissed", "", ""))
        self.assertEqual(self.stored_files(), [])
        self.assertIsNone(self.ingest(message))

    def test_assigning_to_another_subjects_case_is_refused(self):
        reply = self.ingest(make_message(subject="Ihre Anfrage"))
        other = make_subject("Sam", "sam@example.org")
        other_case = services.open_case(other, make_organization("beta", "Beta"), on=DAY0)
        with self.assertRaises(services.CaseError):
            replies.assign(reply, other_case)

    def test_integrity_check_covers_unmatched_files(self):
        reply = self.ingest(make_message(subject="Ihre Anfrage"))
        (self.data_dir / reply.raw_path).unlink()
        problems = storage.attachment_problems(
            [(f"unmatched reply {reply.pk}", reply.raw_path, reply.raw_sha256, "(none)")], self.data_dir
        )
        self.assertEqual(len(problems), 1)


class MboxImportTests(ReplyTestCase):
    def test_the_mbox_import_takes_in_replies_and_still_discovers(self):
        path = self.data_dir / "upload.mbox"
        box = mailbox.mbox(path)
        box.add(make_message(in_reply_to=self.draft.message_id, body="Anbei die Auskunft."))
        box.add(make_message(sender="news@unrelated.example", subject="Sale"))
        box.close()
        upload = SimpleUploadedFile("takeout.mbox", path.read_bytes(), content_type="application/mbox")
        run = importer.import_mbox(self.subject, upload, background=False)
        self.assertEqual(run.total, 2)
        reply = Reply.objects.get()
        self.assertEqual((reply.source, reply.case, reply.suggested_outcome), ("mbox", self.case, "listing_found"))

    def test_a_failing_reply_never_stops_the_import(self):
        messages = [make_message(in_reply_to=self.draft.message_id), None]
        with (
            mock.patch.object(replies, "ingest", side_effect=RuntimeError("boom")) as ingest,
            self.assertLogs("unlist.cases", "WARNING"),
        ):
            passed = list(replies.ingest_each(self.subject, messages))
        self.assertEqual(passed, messages)
        self.assertEqual(ingest.call_count, 1)


class ReplyViewTests(ReplyTestCase):
    def setUp(self):
        super().setUp()
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)

    def upload(self, message):
        data = message.as_bytes()
        return self.client.post(
            f"/cases/{self.case.pk}/reply-upload/",
            {"eml": SimpleUploadedFile("reply.eml", data, content_type="message/rfc822")},
        )

    def test_upload_goes_through_ingest_with_the_case_selected(self):
        response = self.upload(make_message(sender="x@unrelated.example", body="We do not hold any data about you."))
        self.assertEqual(response.status_code, 302)
        reply = Reply.objects.get()
        self.assertEqual((reply.case, reply.source, reply.matched_by), (self.case, "upload", "operator"))
        page = self.client.get(f"/cases/{self.case.pk}/")
        self.assertContains(page, "Never upload an ID document")
        self.assertContains(page, "Review and confirm")

    def test_upload_of_the_subjects_own_mail_is_refused(self):
        response = self.upload(make_message(sender="alex@example.org"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Reply.objects.exists())
        self.assertFalse(Attachment.objects.exists())

    def test_queue_shows_replies_to_confirm_and_unmatched_ones(self):
        self.ingest(make_message(in_reply_to=self.draft.message_id, body="Wir haben keine Daten zu Ihnen."))
        self.ingest(make_message(subject="Something else", body="Hello"))
        page = self.client.get("/cases/replies/")
        self.assertContains(page, "Suggested: &quot;We hold nothing&quot;")
        self.assertContains(page, "Wir haben keine Daten zu Ihnen.")
        self.assertContains(page, "Something else")
        self.assertContains(page, self.case.reference)

    def test_queue_lists_the_nearest_deadline_first(self):
        other = services.open_case(self.subject, make_organization("beta", "Beta", email="p@beta.example"), on=DAY0)
        later = send(other, date(2025, 3, 20))
        self.ingest(make_message(in_reply_to=later.message_id, subject="Later deadline"))
        self.ingest(make_message(in_reply_to=self.draft.message_id, subject="Earlier deadline"))
        content = self.client.get("/cases/replies/").content.decode()
        self.assertLess(content.index("Earlier deadline"), content.index("Later deadline"))

    def test_confirm_assign_and_dismiss_through_the_pages(self):
        reply = self.ingest(make_message(in_reply_to=self.draft.message_id, body="We do not hold any data about you."))
        prefix = f"r{reply.pk}"
        response = self.client.post(
            f"/cases/replies/{reply.pk}/confirm/",
            {f"{prefix}-outcome": "nothing_held", f"{prefix}-occurred_on": ON.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        self.case.refresh_from_db()
        self.assertEqual(self.case.state, State.CLOSED)

        unmatched = self.ingest(make_message(subject="Ihre Anfrage"))
        other_case = services.open_case(self.subject, make_organization("beta", "Beta"), on=DAY0)
        prefix = f"r{unmatched.pk}"
        self.client.post(f"/cases/replies/{unmatched.pk}/assign/", {f"{prefix}-case": other_case.pk})
        unmatched.refresh_from_db()
        self.assertEqual(unmatched.case, other_case)
        self.client.post(f"/cases/replies/{unmatched.pk}/dismiss/")
        unmatched.refresh_from_db()
        self.assertEqual(unmatched.status, "dismissed")


class RulesTests(SimpleTestCase):
    def assertSuggests(self, text, outcome, subject=""):
        found = rules_suggestion(subject, text)
        self.assertIsNotNone(found, text)
        self.assertEqual(found.outcome, outcome, text)
        return found

    def test_english_and_german_rules(self):
        cases = [
            ("Please find attached a copy of your personal data.", "listing_found"),
            ("Anbei erhalten Sie die Auskunft nach Art. 15 DSGVO.", "listing_found"),
            ("We do not hold any personal data about you.", "nothing_held"),
            ("Zu Ihrer Person sind keine Daten gespeichert.", "nothing_held"),
            ("To verify your identity, please send us a copy of your passport.", "id_or_details_asked"),
            ("Bitte senden Sie uns eine Kopie Ihres Ausweises.", "id_or_details_asked"),
            ("Please send a photo of your ID.", "id_or_details_asked"),
            ("Please specify which data you are requesting.", "clarification_asked"),
            (
                "We need to extend the deadline by two further months because of the number of requests.",
                "extension_announced",
            ),
            ("Wir müssen die Frist um zwei weitere Monate verlängern.", "extension_announced"),
            ("We are unable to delete your data because of a legal obligation.", "refused"),
            ("Ihre Daten können wir wegen gesetzlicher Aufbewahrungspflichten nicht löschen.", "refused"),
            ("We have deleted your personal data.", "removed"),
            ("Ihre Daten wurden vollständig gelöscht.", "removed"),
        ]
        for text, outcome in cases:
            self.assertSuggests(text, outcome)

    def test_suppression_and_reasons_are_picked_up(self):
        found = self.assertSuggests(
            "Your data has been deleted and your address added to our suppression list.", "removed"
        )
        self.assertTrue(found.suppression_confirmed)
        self.assertFalse(self.assertSuggests("Ihre Daten wurden gelöscht.", "removed").suppression_confirmed)
        self.assertTrue(
            self.assertSuggests(
                "Ihre Daten wurden gelöscht und auf die Sperrliste gesetzt.", "removed"
            ).suppression_confirmed
        )
        self.assertTrue(
            self.assertSuggests("We need an extension because of complexity.", "extension_announced").with_reasons
        )

    def test_keeping_a_suppression_record_after_removal_is_no_refusal(self):
        text = "We have deleted your data. We need to keep your email address on our suppression list."
        self.assertTrue(self.assertSuggests(text, "removed").suppression_confirmed)

    def test_ticket_ids_are_not_id_demands_and_acknowledgements_are_no_answer(self):
        self.assertIsNone(rules_suggestion("Ticket ID 12345", "Thank you for contacting us."))
        self.assertIsNone(rules_suggestion("", "We have received your request about your data."))

    def test_quoted_original_request_is_ignored(self):
        body = "Thanks.\n\nOn Mon, 3 Mar 2025, Alex wrote:\n> Please send me a copy of my data and verify..."
        self.assertIsNone(rules_suggestion("Re: request", body))

    def test_attached_files_suggest_a_listing(self):
        self.assertEqual(rules_suggestion("Re: request", "Hello", has_files=True).outcome, "listing_found")


class MailboxModeTests(ReplyTestCase):
    def test_live_mailbox_messages_use_the_same_entry_point(self):
        Mailbox.objects.filter(subject=self.subject).update(mode=Mailbox.Mode.LIVE)
        reply = self.ingest(make_message(in_reply_to=self.draft.message_id), source="imap")
        self.assertEqual(reply.source, "imap")
