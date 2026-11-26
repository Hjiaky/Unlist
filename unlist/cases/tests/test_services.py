# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Case services: opening, approval, hand-over, deadlines, hooks and the scheduler job (#47)."""

import email
import sqlite3
import tempfile
from datetime import timedelta
from email import policy
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from unlist import paths
from unlist.backup import hooks as backup_hooks
from unlist.cases import jobs, sending, services, storage
from unlist.cases.lifecycle import Action, State
from unlist.cases.models import Case, CaseEvent, Draft
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.core import scheduler
from unlist.organizations import hooks as organization_hooks
from unlist.organizations.models import LocalOverride
from unlist.subjects.consent import ConsentRequired, withdraw_consent
from unlist.subjects.deletion import delete_subject
from unlist.subjects.models import IdentifyingDetail, Mailbox


def days(n):
    return DAY0 + timedelta(days=n)


class LiveSenders:
    """Register live senders for one test and restore the registry afterwards."""

    def __init__(self, *senders):
        self.senders = senders

    def __enter__(self):
        self.saved = list(sending.live_senders)
        sending.live_senders[:] = list(self.senders)

    def __exit__(self, *exc):
        sending.live_senders[:] = self.saved


class OpenCaseTests(TestCase):
    def setUp(self):
        self.subject = make_subject()
        self.organization = make_organization()

    def test_opens_with_an_access_request_awaiting_approval(self):
        case = services.open_case(self.subject, self.organization, on=DAY0)
        self.assertRegex(case.reference, r"^U-[2-9A-HJ-NP-Z]{4}$")
        draft = case.pending_draft
        self.assertEqual((draft.kind, draft.status, draft.channel), ("access_request", "awaiting_approval", "email"))
        self.assertEqual(draft.recipient, "privacy@acme.example")
        self.assertEqual(draft.sender, "alex@example.org")
        self.assertIn(f"[Ref {case.reference}]", draft.subject_line)
        self.assertIn("Alex Example", draft.body)
        self.assertEqual(draft.return_state, State.FOUND)
        self.assertEqual(list(case.events.values_list("kind", flat=True)), ["opened", "drafted"])

    def test_direct_removal_drafts_a_removal_request(self):
        case = services.open_case(self.subject, self.organization, direct_removal=True)
        self.assertEqual(case.pending_draft.kind, "removal_request")
        self.assertIn("no longer necessary", case.pending_draft.body)

    def test_refuses_without_consent(self):
        subject = make_subject(name="Sam", email="sam@example.org", consent=False)
        with self.assertRaises(ConsentRequired):
            services.open_case(subject, self.organization)
        self.assertFalse(Case.objects.exists())

    def test_refuses_an_unconfirmed_contact(self):
        scraped = make_organization(slug="scraped", name="Scraped Ltd", quality="scraped")
        with self.assertRaisesMessage(services.ContactNotConfirmed, "has not been confirmed"):
            services.open_case(self.subject, scraped)
        self.assertFalse(Case.objects.exists())
        # Once the Operator confirms the contact with a local override, it works.
        LocalOverride.objects.create(organization_slug="scraped", field="email", value="privacy@scraped.example")
        scraped.field_sources = {"email": "local override"}
        scraped.save()
        services.open_case(self.subject, scraped)

    def test_refuses_without_contact_or_mailbox_and_a_second_case(self):
        nowhere = make_organization(slug="nowhere", name="Nowhere", email="")
        with self.assertRaises(services.NoContact):
            services.open_case(self.subject, nowhere)
        no_mail = make_subject(name="No Mail", email="x@example.org")
        no_mail.mailboxes.all().delete()
        with self.assertRaises(services.NoMailbox):
            services.open_case(no_mail, self.organization)
        services.open_case(self.subject, self.organization)
        with self.assertRaises(services.CaseExists):
            services.open_case(self.subject, self.organization)

    def test_language_jurisdiction_and_details(self):
        IdentifyingDetail.objects.create(
            subject=self.subject, kind="customer_number", value="K-1", organization_label="UK Shop"
        )
        IdentifyingDetail.objects.create(subject=self.subject, kind="customer_number", value="OTHER-9")
        IdentifyingDetail.objects.create(subject=self.subject, kind="date_of_birth", value="1 April 1990")
        IdentifyingDetail.objects.create(subject=self.subject, kind="previous_address", value="1 Old Road")
        shop = make_organization(
            slug="uk-shop",
            name="UK Shop",
            relevant_countries=["gb"],
            required_elements=[
                {"desc": "Customer number", "type": "input"},
                {"desc": "Name", "type": "name"},
            ],
        )
        draft = services.open_case(self.subject, shop).pending_draft
        self.assertIn("UK GDPR", draft.body)
        self.assertIn("Customer number: K-1", draft.body)
        self.assertNotIn("OTHER-9", draft.body)
        self.assertNotIn("1990", draft.body)
        self.assertNotIn("Old Road", draft.body)

        german = make_organization(
            slug="de-shop",
            name="DE Shop",
            request_language="de",
            required_elements=[{"desc": "Geburtsdatum", "type": "birthdate"}],
        )
        draft = services.open_case(self.subject, german).pending_draft
        self.assertEqual(draft.lang, "de")
        self.assertIn("DSGVO", draft.body)
        self.assertIn("Geburtsdatum: 1 April 1990", draft.body)


class ApprovalTests(TestCase):
    def setUp(self):
        self.subject = make_subject()
        self.organization = make_organization()
        self.case = services.open_case(self.subject, self.organization, on=DAY0)
        self.draft = self.case.pending_draft

    def test_nothing_leaves_without_approval(self):
        seen = []

        def sender_side_effect(draft):
            seen.append((draft.status, draft.approved_at is not None))
            return True

        sender = mock.Mock(side_effect=sender_side_effect)
        live = self.subject.mailboxes.get()
        live.mode = Mailbox.Mode.LIVE
        live.save()
        with LiveSenders(sender):
            with self.assertRaises(services.IllegalStep):
                services.mark_sent(self.draft, on=DAY0)
            with self.assertRaises(sending.NotApproved):
                sending.try_live_send(self.draft)
            sender.assert_not_called()
            self.assertFalse(CaseEvent.objects.filter(kind=CaseEvent.Kind.SENT).exists())
            services.approve(self.draft, on=DAY0)
        sender.assert_called_once()
        self.assertEqual(seen, [(Draft.Status.APPROVED, True)])
        self.draft.refresh_from_db()
        self.case.refresh_from_db()
        self.assertEqual(self.draft.status, Draft.Status.SENT)
        self.assertEqual(self.draft.sent_on, DAY0)
        self.assertEqual(self.case.state, State.WAITING)
        self.assertIsNotNone(self.case.due_date)

    def test_import_mode_hands_over_even_with_a_live_sender(self):
        sender = mock.Mock(return_value=True)
        with LiveSenders(sender):
            services.approve(self.draft, on=DAY0)
        sender.assert_not_called()
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Draft.Status.HANDED_OVER)
        self.assertTrue(self.draft.message_id.endswith("@example.org>"))
        self.case.refresh_from_db()
        self.assertEqual(self.case.state, State.HANDED_OVER)
        self.assertIsNone(self.case.due_date)

    def test_live_sender_declining_hands_over(self):
        live = self.subject.mailboxes.get()
        live.mode = Mailbox.Mode.LIVE
        live.save()
        with LiveSenders(mock.Mock(return_value=False)):
            services.approve(self.draft, on=DAY0)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Draft.Status.HANDED_OVER)

    def test_webform_organization_is_handed_over(self):
        form_only = make_organization(
            slug="form", name="Form Ltd", email="", webform="https://form.example/privacy", preferred_channel="webform"
        )
        draft = services.open_case(self.subject, form_only).pending_draft
        self.assertEqual((draft.channel, draft.recipient), ("webform", "https://form.example/privacy"))
        self.assertTrue(sending.hands_over(draft))

    def test_eml_has_reference_from_to_and_message_id(self):
        services.approve(self.draft, on=DAY0)
        self.draft.refresh_from_db()
        message = email.message_from_bytes(sending.eml_bytes(self.draft), policy=policy.default)
        self.assertIn(self.case.reference, message["Subject"])
        self.assertEqual(message["From"].addresses[0].addr_spec, "alex@example.org")
        self.assertEqual(message["From"].addresses[0].display_name, "Alex Example")
        self.assertEqual(message["To"], "privacy@acme.example")
        self.assertEqual(message["Message-ID"], self.draft.message_id)
        self.assertIn("Article 15", message.get_content())

    def test_mailto_link(self):
        services.approve(self.draft, on=DAY0)
        link = sending.mailto_link(self.draft)
        self.assertTrue(link.startswith("mailto:privacy@acme.example?subject="))
        self.assertIn(self.case.reference, link)
        self.assertIn("%0D%0A", link)

    def test_mark_sent_dates(self):
        services.approve(self.draft, on=days(2))
        with self.assertRaisesMessage(services.CaseError, "before the day"):
            services.mark_sent(self.draft, on=days(1))
        with self.assertRaisesMessage(services.CaseError, "future"):
            services.mark_sent(self.draft, on=timezone.localdate() + timedelta(days=1))
        services.mark_sent(self.draft, on=days(2))
        sent = self.case.events.get(kind=CaseEvent.Kind.SENT)
        self.assertEqual((sent.occurred_on, sent.details["request"]), (days(2), "access"))

    def test_discard_goes_back(self):
        services.discard(self.draft)
        self.draft.refresh_from_db()
        self.case.refresh_from_db()
        self.assertEqual(self.draft.status, Draft.Status.DISCARDED)
        self.assertEqual(self.case.state, State.FOUND)
        self.assertIn(Action.PREPARE_REQUEST, services.available_actions(self.case))

    def test_edit_keeps_reference(self):
        with self.assertRaisesMessage(services.CaseError, "Keep the reference"):
            services.edit_draft(self.draft, subject_line="Hello", body="Hi")
        services.edit_draft(self.draft, subject_line=f"Access [Ref {self.case.reference}]", body="Text")
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.body, "Text")


class FollowUpTests(TestCase):
    def setUp(self):
        self.subject = make_subject()
        self.case = services.open_case(self.subject, make_organization(), on=DAY0)
        send(self.case, DAY0)

    def test_reminder_only_after_overdue(self):
        with self.assertRaises(services.IllegalStep):
            services.send_reminder(self.case)
        self.assertTrue(services.mark_overdue_if_due(self.case, today=days(60)))
        reminder = services.send_reminder(self.case, on=days(60))
        self.assertIn("ended on", reminder.body)
        self.assertIn("3 April 2025", reminder.body)  # the passed deadline
        self.assertIn("3 March 2025", reminder.body)  # the original request

    def test_complaint_only_after_overdue_and_reminder_or_refusal(self):
        drafted = []
        with mock.patch.object(services, "complaint_drafters", [drafted.append]):
            with self.assertRaises(services.IllegalStep):
                services.draft_complaint(self.case)
            services.mark_overdue_if_due(self.case, today=days(60))
            with self.assertRaisesMessage(services.IllegalStep, "Gentle first"):
                services.draft_complaint(self.case)
            services.send_reminder(self.case, on=days(60))
            with self.assertRaises(services.IllegalStep):
                services.draft_complaint(self.case)
            send(self.case, days(60))
            services.mark_overdue_if_due(self.case, today=days(90))
            services.draft_complaint(self.case, on=days(90))
            self.assertEqual(drafted, [self.case])

        other = services.open_case(self.subject, make_organization(slug="b", name="B"), on=DAY0)
        send(other, DAY0)
        services.record_outcome(other, "refused", on=days(3), exception="Not our data")
        services.draft_complaint(other, on=days(4))
        other.refresh_from_db()
        self.assertEqual(other.state, State.COMPLAINT_DRAFT)

    def test_late_answer_discards_a_pending_reminder(self):
        services.mark_overdue_if_due(self.case, today=days(60))
        reminder = services.send_reminder(self.case, on=days(60))
        services.record_outcome(self.case, "nothing_held", on=days(61))
        reminder.refresh_from_db()
        self.case.refresh_from_db()
        self.assertEqual(reminder.status, Draft.Status.DISCARDED)
        self.assertEqual(self.case.state, State.CLOSED)

    def test_bounce_means_no_clock_and_fix_contact_redrafts(self):
        services.record_outcome(self.case, "bounce", on=days(1))
        self.case.refresh_from_db()
        self.assertEqual(self.case.state, State.UNDELIVERABLE)
        self.assertIsNone(services.case_deadline(self.case))
        self.assertIsNone(self.case.due_date)
        draft = services.fix_contact(self.case, on=days(2))
        self.assertEqual(draft.kind, "access_request")
        send(self.case, days(3))
        self.assertEqual(services.case_deadline(self.case).clock_start, days(3))

    def test_details_reply_and_reconsider(self):
        services.record_outcome(self.case, "id_or_details_asked", on=days(2))
        draft = services.send_details(self.case, ["Customer number: 12345"], on=days(3))
        self.assertIn("Customer number: 12345", draft.body)
        send(self.case, days(3))
        services.record_outcome(self.case, "listing_found", on=days(9))
        services.request_removal(self.case, on=days(9))
        send(self.case, days(9))
        services.record_outcome(self.case, "refused", on=days(12), exception="Tax law retention")
        draft = services.ask_reconsider(self.case, on=days(13))
        self.assertIn("Tax law retention", draft.body)
        send(self.case, days(13))
        self.assertEqual(services.case_deadline(self.case).clock_start, days(13))

    def test_reconsider_not_offered_after_a_refused_access_request(self):
        services.record_outcome(self.case, "refused", on=days(3))
        with self.assertRaisesMessage(services.IllegalStep, "Removal Request"):
            services.ask_reconsider(self.case)
        services.accept_refusal(self.case)
        self.case.refresh_from_db()
        self.assertEqual((self.case.state, self.case.recheck_on), (State.CLOSED, None))

    def test_recheck_overrides(self):
        self.case.recheck_override = "30"
        self.case.save()
        services.record_outcome(self.case, "nothing_held", on=days(5))
        self.case.refresh_from_db()
        self.assertEqual((self.case.state, self.case.recheck_on), (State.RESTING, days(35)))

        broker = make_organization(slug="br", name="Broker", broker=True)
        case = services.open_case(self.subject, broker, on=DAY0)
        services.set_recheck_override(case, "close")
        send(case, DAY0)
        services.record_outcome(case, "nothing_held", on=days(5))
        case.refresh_from_db()
        self.assertEqual(case.state, State.CLOSED)

        shop = make_organization(slug="shop", name="Shop", recheck_default=200)
        case = services.open_case(self.subject, shop, on=DAY0)
        send(case, DAY0)
        services.record_outcome(case, "nothing_held", on=days(5))
        case.refresh_from_db()
        self.assertEqual(case.recheck_on, days(205))


class HookTests(TestCase):
    def setUp(self):
        self.subject = make_subject()
        self.organization = make_organization()

    def test_has_case(self):
        self.assertFalse(organization_hooks.organization_has_case("acme"))
        services.open_case(self.subject, self.organization)
        self.assertTrue(organization_hooks.organization_has_case("acme"))
        self.assertFalse(organization_hooks.organization_has_case("other"))

    def test_consent_withdrawal_stops_cases(self):
        waiting = services.open_case(self.subject, self.organization, on=DAY0)
        send(waiting, DAY0)
        pending = services.open_case(self.subject, make_organization(slug="b", name="B"))
        pending_draft = pending.pending_draft
        withdraw_consent(self.subject)
        for case in (waiting, pending):
            case.refresh_from_db()
            self.assertEqual((case.state, case.result), (State.CLOSED, "consent withdrawn"))
        pending_draft.refresh_from_db()
        self.assertEqual(pending_draft.status, Draft.Status.DISCARDED)
        services.reopen(pending)
        with self.assertRaises(ConsentRequired):
            services.prepare_request(pending)

    def test_deleting_a_subject_removes_attachment_files(self):
        with tempfile.TemporaryDirectory() as data_dir, mock.patch.object(paths, "DATA_DIR", Path(data_dir)):
            case = services.open_case(self.subject, self.organization)
            attachment = storage.store_attachment(case, "../reply.eml", b"Subject: hi\n\nhello")
            path = storage.attachment_path(attachment)
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent, Path(data_dir) / "attachments" / str(self.subject.pk) / str(case.pk))
            self.assertTrue(path.name.endswith("reply.eml"))
            other = make_subject(name="Other", email="other@example.org")
            other_case = services.open_case(other, self.organization)
            kept = storage.attachment_path(storage.store_attachment(other_case, "a.txt", b"a"))
            delete_subject(self.subject)
            self.assertFalse(path.exists())
            self.assertFalse((Path(data_dir) / "attachments" / str(self.subject.pk)).exists())
            self.assertTrue(kept.exists())

    def test_integrity_check(self):
        self.assertIn(storage.integrity_check, backup_hooks.integrity_checks)
        with tempfile.TemporaryDirectory() as data_dir, mock.patch.object(paths, "DATA_DIR", Path(data_dir)):
            case = services.open_case(self.subject, self.organization)
            good = storage.store_attachment(case, "good.eml", b"good")
            changed = storage.store_attachment(case, "changed.eml", b"before")
            missing = storage.store_attachment(case, "missing.eml", b"gone")
            self.assertEqual(good.sha256, "770e607624d689265ca6c44884d0807d9b054d23c473c106c72be9de08b7376c")
            storage.attachment_path(changed).write_bytes(b"after")
            storage.attachment_path(missing).unlink()
            self.assertEqual(storage.integrity_check(Path(data_dir)), [])  # no database file there
            # The check reads the restored database file itself; write a minimal one.
            rows = [(a.id, a.case_id, a.original_name, a.stored_path, a.sha256) for a in (good, changed, missing)]
            connection = sqlite3.connect(Path(data_dir) / storage.DB_NAME)
            connection.execute("CREATE TABLE cases_case (id INTEGER PRIMARY KEY, reference TEXT)")
            connection.execute(
                "CREATE TABLE cases_attachment (id INTEGER PRIMARY KEY, case_id INTEGER, original_name TEXT, "
                "stored_path TEXT, sha256 TEXT)"
            )
            connection.execute("INSERT INTO cases_case VALUES (?, ?)", (case.id, case.reference))
            connection.executemany("INSERT INTO cases_attachment VALUES (?, ?, ?, ?, ?)", rows)
            connection.commit()
            connection.close()
            problems = storage.integrity_check(Path(data_dir))
        self.assertEqual(len(problems), 2)
        self.assertIn(f'"changed.eml" of Case {case.reference} has changed', problems[0])
        self.assertIn('"missing.eml"', problems[1])
        self.assertIn("is missing", problems[1])


class SchedulerTests(TestCase):
    def test_overdue_job_marks_and_suggests_but_sends_nothing(self):
        self.assertIn(jobs.mark_overdue_cases, scheduler.JOBS)
        subject = make_subject(mode=Mailbox.Mode.LIVE)
        case = services.open_case(subject, make_organization(), on=DAY0)
        sender = mock.Mock(return_value=True)
        with LiveSenders(sender):
            services.approve(case.pending_draft, on=DAY0)  # sent live: the clock starts
            sender.reset_mock()
            case.refresh_from_db()
            self.assertEqual(case.state, State.WAITING)

            self.assertIsNone(jobs.mark_overdue_cases(timezone.make_aware(timezone.datetime(2025, 4, 4, 12))))
            case.refresh_from_db()
            self.assertEqual(case.state, State.WAITING)

            summary = jobs.mark_overdue_cases(timezone.make_aware(timezone.datetime(2025, 4, 10, 12)))
            self.assertEqual(summary, "1 Case(s) overdue, 1 reminder(s) prepared for approval.")
            sender.assert_not_called()
        case.refresh_from_db()
        self.assertEqual(case.state, State.AWAITING_APPROVAL)
        reminder = case.pending_draft
        self.assertEqual((reminder.kind, reminder.status), ("reminder", Draft.Status.AWAITING_APPROVAL))
        overdue = case.events.get(kind=CaseEvent.Kind.OVERDUE)
        self.assertEqual(overdue.occurred_on, services.case_deadline(case).overdue_from)
        self.assertEqual(case.events.filter(kind=CaseEvent.Kind.SENT).count(), 1)
        # Running again changes nothing.
        self.assertIsNone(jobs.mark_overdue_cases(timezone.make_aware(timezone.datetime(2025, 4, 11, 12))))
