# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Complaint drafts (#52): authority, language, contents, the UK first step, evidence, gentle first."""

import email
import io
import tempfile
import zipfile
from datetime import timedelta
from email import policy
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from unlist import paths
from unlist.cases import complaints, lifecycle, services, storage
from unlist.cases.complaints import Ground, Stage
from unlist.cases.lifecycle import Action, CaseState, Request, State
from unlist.cases.models import CaseEvent
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.organizations.loading import load_supervisory_authorities
from unlist.organizations.models import SupervisoryAuthority


def days(n):
    return DAY0 + timedelta(days=n)


class Fixtures:
    def setUp(self):
        load_supervisory_authorities()
        self.data_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.object(paths, "DATA_DIR", self.data_dir))

    def subject(self, country="FR", name="Alex Example", email="alex@example.org"):
        subject = make_subject(name=name, email=email)
        subject.country = country
        subject.save()
        return subject

    def missed_deadline(self, subject, *, slug="acme", draft=True, **fields):
        """Sent on day 0, overdue, reminder on day 60, overdue again; Complaint drafted on day 90."""
        organization = make_organization(slug=slug, name=slug.upper(), **fields)
        case = services.open_case(subject, organization, on=DAY0)
        send(case, DAY0)
        services.mark_overdue_if_due(case, today=days(60))
        services.send_reminder(case, on=days(60))
        send(case, days(60))
        services.mark_overdue_if_due(case, today=days(90))
        if draft:
            services.draft_complaint(case, on=days(90))
        case.refresh_from_db()
        return case


class AuthoritySelectionTests(Fixtures, TestCase):
    def test_germany_without_a_land_offers_a_chooser(self):
        choice = complaints.select_authority(self.subject("DE"), make_organization())
        self.assertIsNone(choice.authority)
        slugs = {authority.slug for authority in choice.candidates}
        self.assertEqual(len(slugs), 17)  # 16 Länder (BayLDA for Bavaria) and the federal BfDI
        self.assertIn("debfdi", slugs)
        self.assertIn("debaylda", slugs)
        self.assertFalse(slugs & {"debayldb", "derf", "derfdw", "deekdbfd", "dekathdsz"})
        self.assertIn("Land", choice.rule)

    def test_germany_uses_the_organizations_own_german_authority(self):
        subject = self.subject("DE")
        bavarian = complaints.select_authority(subject, make_organization(supervisory_authority="debaylda"))
        self.assertEqual(bavarian.authority.slug, "debaylda")
        telecom = complaints.select_authority(
            subject, make_organization(slug="tel", name="Tel", supervisory_authority="debfdi")
        )
        self.assertEqual(telecom.authority.slug, "debfdi")
        foreign = complaints.select_authority(
            subject, make_organization(slug="ie", name="IE", supervisory_authority="iedpc")
        )
        self.assertIsNone(foreign.authority)

    def test_germany_remembers_the_choice_for_the_subject(self):
        subject = self.subject("DE")
        case = self.missed_deadline(subject)
        complaints.choose_authority(case, "deberlbdi", on=days(91))
        self.assertEqual(complaints.build_complaint(case).authority.slug, "deberlbdi")
        other = complaints.select_authority(subject, make_organization(slug="b", name="B"))
        self.assertEqual(other.authority.slug, "deberlbdi")
        with self.assertRaisesMessage(services.CaseError, "Choose one of the Supervisory Authorities"):
            complaints.choose_authority(case, "frcnil")

    def test_austria(self):
        choice = complaints.select_authority(self.subject("AT"))
        self.assertEqual(choice.authority.slug, "atdsb")

    def test_united_kingdom_is_the_information_commission(self):
        for code in ("GB", "UK"):
            choice = complaints.select_authority(self.subject(code, email=f"{code}@example.org"))
            self.assertEqual(choice.authority.slug, "gbico")
            self.assertEqual(choice.name, "Information Commission")

    def test_unknown_country_offers_every_authority(self):
        choice = complaints.select_authority(self.subject("US"))
        self.assertIsNone(choice.authority)
        self.assertEqual(len(choice.candidates), SupervisoryAuthority.objects.count())
        self.assertIn("(US)", choice.rule)
        chosen = complaints.select_authority(self.subject("US", email="b@example.org"), chosen="iedpc")
        self.assertEqual(chosen.authority.slug, "iedpc")

    def test_language(self):
        self.assertEqual(complaints.complaint_language(self.subject("DE")), "de")
        self.assertEqual(complaints.complaint_language(self.subject("AT", email="a@example.org")), "de")
        self.assertEqual(complaints.complaint_language(self.subject("GB", email="g@example.org")), "en")
        self.assertEqual(complaints.complaint_language(self.subject("FR", email="f@example.org")), "en")


class ComplaintContentTests(Fixtures, TestCase):
    def test_missed_deadline_and_reminder(self):
        case = self.missed_deadline(self.subject("FR"))
        self.assertEqual(case.state, State.COMPLAINT_DRAFT)
        complaint = complaints.build_complaint(case)
        self.assertEqual(complaint.ground, Ground.MISSED_DEADLINE)
        self.assertEqual((complaint.lang, complaint.jurisdiction), ("en", "EU"))
        self.assertEqual(complaint.authority.slug, "frcnil")
        body = complaint.body
        self.assertIn(f"[Ref {case.reference}]", complaint.subject_line)
        self.assertIn("Article 77", body)
        self.assertIn(complaint.choice.name, body)
        self.assertIn("Commission Nationale de l'Informatique", body)  # plain text, not HTML-escaped
        # Subject and Organization
        self.assertIn("Name: Alex Example", body)
        self.assertIn("Email: alex@example.org", body)
        self.assertIn("Privacy contact (email): privacy@acme.example", body)
        self.assertIn("Country: DE", body)
        # The timeline holds every step of the deadline engine, dated, and the sends with addresses.
        deadline = services.case_deadline(case)
        self.assertTrue(deadline.reminder_due_date)
        for step in deadline.steps:
            self.assertIn(f"- {complaints.drafting.format_date(step.on, 'en')}: {step.text}", body)
        self.assertIn(
            "3 March 2025: Access request (Article 15 GDPR) sent from alex@example.org to privacy@acme.example.", body
        )
        self.assertIn("Reminder sent on Friday 2 May 2025", body)
        # Infringement, remedy, prior contact, attachments
        self.assertIn("It had to answer within one month (Article 12(3) GDPR), by 3 April 2025.", body)
        self.assertIn("I sent a reminder on 2 May 2025, giving it until 16 May 2025", body)
        self.assertIn("my right of access (Article 15 GDPR)", body)
        self.assertIn("ask ACME to answer my access request in full", body)
        self.assertIn("a reminder of 2 May 2025", body)
        self.assertIn("It has not replied.", body)
        self.assertIn(f"01-{case.reference}-access_request.eml: Access request of 3 March 2025, as sent", body)
        self.assertIn(f"02-{case.reference}-reminder.eml: Reminder of 2 May 2025", body)
        self.assertEqual(complaints.templating.missing_variables(body), [])
        for word in ("compensation", "damages", "legal action"):
            self.assertNotIn(word, body.lower())

    def test_timeline_dates_are_in_order(self):
        case = self.missed_deadline(self.subject("FR"))
        complaint = complaints.build_complaint(case)
        steps = sorted(services.case_deadline(case).steps, key=lambda step: step.on)  # the engine appends by rule
        positions = [complaint.body.index(step.text) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(complaint.body.index("is a working day"), complaint.body.index("Reminder sent on"))

    def test_german_complaint(self):
        subject = self.subject("DE")
        case = self.missed_deadline(subject, supervisory_authority="dehmbbfdi")
        complaint = complaints.build_complaint(case)
        self.assertEqual(complaint.lang, "de")
        self.assertIn("Art. 77 DSGVO", complaint.subject_line)
        body = complaint.body
        self.assertIn("Der Hamburgische Beauftragte", body)
        self.assertIn("3. März 2025: Auskunftsersuchen (Art. 15 DSGVO) gesendet", body)
        self.assertIn("2. Mai 2025: Erinnerung gesendet", body)
        self.assertIn("3. April 2025: Ende der Frist für die Antwort (Art. 12 Abs. 3 DSGVO).", body)
        self.assertIn("Datenschutzkontakt (E-Mail): privacy@acme.example", body)
        self.assertEqual(complaints.templating.missing_variables(body), [])

    def test_german_subject_without_a_choice_gets_a_placeholder(self):
        case = self.missed_deadline(self.subject("DE"))
        complaint = complaints.build_complaint(case)
        self.assertIsNone(complaint.authority)
        self.assertIn("[Aufsichtsbehörde auswählen]", complaint.body)
        with self.assertRaisesMessage(services.CaseError, "Choose the Supervisory Authority first"):
            complaints.mark_lodged(case, on=days(95))

    def test_refusal_names_the_exception(self):
        organization = make_organization()
        case = services.open_case(self.subject("FR"), organization, on=DAY0)
        send(case, DAY0)
        services.record_outcome(case, "refused", on=days(10), exception="Trade secrets of our scoring")
        services.draft_complaint(case, on=days(11))
        complaint = complaints.build_complaint(case)
        self.assertEqual(complaint.ground, Ground.REFUSAL)
        self.assertIn("relying on: “Trade secrets of our scoring”", complaint.body)
        self.assertIn("whether the refusal is lawful", complaint.body)
        self.assertNotIn("Unlist treats the request as overdue", complaint.body)

    def test_persistent_id_demand(self):
        case = services.open_case(self.subject("FR"), make_organization(), on=DAY0)
        send(case, DAY0)
        services.record_outcome(case, "id_or_details_asked", on=days(5))
        with self.assertRaisesMessage(services.IllegalStep, "push back on the ID demand"):
            services.draft_complaint(case, on=days(6))
        services.push_back(case, on=days(6))
        send(case, days(6))
        services.record_outcome(case, "id_or_details_asked", on=days(12))
        self.assertIn(Action.DRAFT_COMPLAINT, services.available_actions(case))
        services.draft_complaint(case, on=days(13))
        complaint = complaints.build_complaint(case)
        self.assertEqual(complaint.ground, Ground.ID_DEMAND)
        self.assertIn("Article 12(6) GDPR", complaint.body)
        self.assertIn("On 15 March 2025 it repeated the demand.", complaint.body)
        self.assertIn("The clock has been paused since", complaint.body)

    def test_returned_listing_after_a_suppression_record(self):
        case = services.open_case(self.subject("FR"), make_organization(broker=True), on=DAY0)
        send(case, DAY0)
        services.record_outcome(case, "listing_found", on=days(5))
        services.request_removal(case, on=days(5))
        send(case, days(5))
        services.record_outcome(case, "removed", on=days(32), suppression_confirmed=True)
        services.prepare_recheck(case, on=days(122))
        send(case, days(122))
        services.record_outcome(case, "listing_found", on=days(130))
        services.draft_complaint(case, on=days(131))
        complaint = complaints.build_complaint(case)
        self.assertEqual(complaint.ground, Ground.RELISTED)
        self.assertIn("keeps a minimal suppression record", complaint.body)
        self.assertIn("erase my personal data again", complaint.body)

    def test_lifecycle_persistent_id_rule(self):
        paused = CaseState(state=State.PAUSED, request=Request.ACCESS)
        self.assertIn("push back", lifecycle.transition(paused, Action.DRAFT_COMPLAINT).error)
        result = lifecycle.transition(
            CaseState(state=State.PAUSED, request=Request.ACCESS, pushbacks=1), Action.DRAFT_COMPLAINT
        )
        self.assertEqual(result.case.state, State.COMPLAINT_DRAFT)


class GentleFirstTests(Fixtures, TestCase):
    def test_drafting_refused_when_not_allowed(self):
        subject = self.subject("FR")
        case = services.open_case(subject, make_organization(), on=DAY0)
        with self.assertRaisesMessage(services.IllegalStep, "only drafted after a missed deadline"):
            complaints.build_complaint(case)
        send(case, DAY0)
        with self.assertRaisesMessage(services.IllegalStep, "only drafted after a missed deadline"):
            services.draft_complaint(case)
        services.mark_overdue_if_due(case, today=days(60))
        with self.assertRaisesMessage(services.IllegalStep, "Gentle first"):
            complaints.build_complaint(case)
        with self.assertRaisesMessage(services.IllegalStep, "Gentle first"):
            services.draft_complaint(case, on=days(60))
        self.assertFalse(case.events.filter(kind=CaseEvent.Kind.COMPLAINT_DRAFTED).exists())

    def test_the_drafter_refuses_outside_a_complaint_draft(self):
        case = services.open_case(self.subject("FR"), make_organization(), on=DAY0)
        with self.assertRaises(services.IllegalStep):
            complaints.on_complaint_drafted(case)

    def test_the_drafter_is_registered(self):
        self.assertIn(complaints.on_complaint_drafted, services.complaint_drafters)
        case = self.missed_deadline(self.subject("FR"))
        event = case.events.get(kind=CaseEvent.Kind.COMPLAINT_DRAFTED)
        self.assertEqual(event.details[complaints.STAGE_KEY], Stage.AUTHORITY)
        self.assertIn("Addressed to", event.text)


class UkTwoStageTests(Fixtures, TestCase):
    def uk_case(self, slug="acme"):
        subject = self.subject("GB", email=f"sam@{slug}.example.org", name="Sam Example")
        return self.missed_deadline(subject, slug=slug, relevant_countries=["gb"])

    def test_the_organization_first_then_the_regulator(self):
        case = self.uk_case()
        progress = complaints.progress(case)
        self.assertEqual((progress.stage, progress.authority_ready), (Stage.UK_ORGANIZATION, False))
        letter = complaints.uk_letter(case)
        self.assertIn("section 164A of the Data Protection Act 2018", letter.body)
        self.assertIn("You did not answer my access request within one month", letter.body)
        self.assertIn("reminder of 2 May 2025", letter.body)
        self.assertIn(f"[Ref {case.reference}]", letter.subject_line)
        self.assertTrue(letter.message_id)
        with self.assertRaisesMessage(services.CaseError, "not offered yet"):
            complaints.mark_lodged(case, on=days(95))

        complaints.uk_letter_sent(case, on=days(92))
        progress = complaints.progress(case, today=days(100))
        self.assertEqual((progress.stage, progress.authority_ready), (Stage.UK_SENT, False))
        self.assertEqual(progress.wait_until, days(122))
        self.assertTrue(complaints.progress(case, today=days(122)).authority_ready)

        complaints.uk_letter_answered(case, on=days(110))
        self.assertTrue(complaints.progress(case, today=days(110)).authority_ready)
        complaint = complaints.build_complaint(case)
        self.assertEqual((complaint.authority.slug, complaint.jurisdiction), ("gbico", "UK"))
        self.assertIn("Information Commission", complaint.body)
        self.assertIn("section 165 of the Data Protection Act 2018", complaint.body)
        self.assertIn("a complaint to the organisation under section 164A", complaint.body)
        self.assertIn("It answered the section 164A complaint on 21 June 2025.", complaint.body)
        self.assertIn("Articles 12(3) and 12A UK GDPR", complaint.body)
        self.assertNotIn("It has not replied", complaint.body)
        self.assertTrue(any("uk-complaint-to-organization.eml" in item.filename for item in complaint.evidence))

        event = complaints.mark_lodged(case, on=days(111))
        case.refresh_from_db()
        self.assertEqual(case.state, State.COMPLAINT_LODGED)
        self.assertEqual(event.details["complaint"]["authority"], "gbico")
        self.assertIn("section 165", event.details["complaint"]["body"])

    def test_the_first_step_can_be_skipped(self):
        case = self.uk_case()
        complaints.skip_uk_step(case, on=days(91))
        self.assertTrue(complaints.progress(case).authority_ready)
        with self.assertRaisesMessage(services.CaseError, "does not fit"):
            complaints.uk_letter_sent(case, on=days(92))
        complaints.mark_lodged(case, on=days(92))
        case.refresh_from_db()
        self.assertEqual(case.state, State.COMPLAINT_LODGED)

    def test_answer_cannot_precede_the_complaint(self):
        case = self.uk_case()
        complaints.uk_letter_sent(case, on=days(92))
        with self.assertRaisesMessage(services.CaseError, "before the complaint was sent"):
            complaints.uk_letter_answered(case, on=days(91))

    def test_uk_subject_at_an_eu_organization_goes_to_the_regulator(self):
        subject = self.subject("GB", email="sam@example.org")
        case = self.missed_deadline(subject)
        self.assertEqual(complaints.progress(case).stage, Stage.AUTHORITY)
        self.assertEqual(complaints.build_complaint(case).authority.slug, "gbico")


class EvidenceTests(Fixtures, TestCase):
    def test_zip_contains_the_sent_request_with_its_message_id_and_the_replies(self):
        case = self.missed_deadline(self.subject("FR"), draft=False)
        services.record_outcome(case, "refused", on=days(95), exception="We keep it for tax reasons")
        event = case.events.get(kind=CaseEvent.Kind.REFUSED)
        storage.store_attachment(case, "reply.eml", b"From: privacy@acme.example\r\n\r\nNo.", event=event)
        services.draft_complaint(case, on=days(96))
        complaint = complaints.build_complaint(case)
        request = case.drafts.get(kind="access_request")
        archive = zipfile.ZipFile(io.BytesIO(complaints.evidence_zip(complaint)))
        names = archive.namelist()
        self.assertEqual(names[0], "complaint.txt")
        self.assertIn(complaint.body, archive.read("complaint.txt").decode("utf-8"))
        eml_name = f"01-{case.reference}-access_request.eml"
        message = email.message_from_bytes(archive.read(eml_name), policy=policy.default)
        self.assertEqual(message["Message-ID"], request.message_id)
        self.assertEqual(message["From"].addresses[0].addr_spec, "alex@example.org")
        self.assertEqual(message["To"], "privacy@acme.example")
        self.assertIn(f"02-{case.reference}-reminder.eml", names)
        self.assertEqual(archive.read("03-reply.eml"), b"From: privacy@acme.example\r\n\r\nNo.")
        self.assertIn("03-reply.eml: Correspondence from the organisation, received on 6 June 2025", complaint.body)


class ComplaintPageTests(Fixtures, TestCase):
    def setUp(self):
        super().setUp()
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)

    def test_page_choose_download_and_lodge(self):
        case = self.missed_deadline(self.subject("DE"))
        detail = self.client.get(f"/cases/{case.pk}/")
        self.assertContains(detail, "Open the Complaint")
        page = self.client.get(f"/cases/{case.pk}/complaint/")
        self.assertContains(page, "Choose…")
        self.assertContains(page, "complaints.css")
        self.client.post(f"/cases/{case.pk}/complaint/authority/", {"authority": "dehmbbfdi"})
        page = self.client.get(f"/cases/{case.pk}/complaint/")
        self.assertContains(page, "Der Hamburgische Beauftragte")
        self.assertContains(page, "mailbox@datenschutz.hamburg.de")
        response = self.client.get(f"/cases/{case.pk}/complaint/evidence.zip")
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("complaint.txt", zipfile.ZipFile(io.BytesIO(response.content)).namelist())
        response = self.client.post(f"/cases/{case.pk}/complaint/lodged/", {"on": days(95).isoformat()}, follow=True)
        self.assertContains(response, "Marked as lodged")
        self.assertContains(response, "Lodged on 6 June 2025")
        case.refresh_from_db()
        self.assertEqual(case.state, State.COMPLAINT_LODGED)

    def test_page_refused_before_a_complaint_is_allowed(self):
        case = services.open_case(self.subject("FR"), make_organization(), on=DAY0)
        response = self.client.get(f"/cases/{case.pk}/complaint/", follow=True)
        self.assertContains(response, "only drafted after a missed deadline")

    def test_uk_steps_on_the_page(self):
        subject = self.subject("GB", email="sam@example.org")
        case = self.missed_deadline(subject, relevant_countries=["gb"])
        page = self.client.get(f"/cases/{case.pk}/complaint/")
        self.assertContains(page, "First step: a complaint to the Organization")
        self.assertNotContains(page, "Mark lodged")
        eml = self.client.get(f"/cases/{case.pk}/complaint/uk-complaint.eml")
        self.assertIn(b"section 164A", eml.content)
        self.client.post(f"/cases/{case.pk}/complaint/uk/skip/")
        page = self.client.get(f"/cases/{case.pk}/complaint/")
        self.assertContains(page, "To Information Commission")
        self.assertContains(page, "Mark lodged")

    def test_generic_lodged_button_keeps_the_text(self):
        case = self.missed_deadline(self.subject("FR"))
        self.client.post(f"/cases/{case.pk}/action/complaint_lodged/")
        case.refresh_from_db()
        self.assertEqual(case.state, State.COMPLAINT_LODGED)
        self.assertIn("Article 77", case.events.get(kind=CaseEvent.Kind.COMPLAINT_LODGED).details["complaint"]["body"])


class PlainTextRenderingTests(TestCase):
    def test_mail_templates_are_not_html_escaped(self):
        context = {
            "jurisdiction": "EU",
            "reference": "U-7KQ3",
            "subject_name": "Alex O'Brien",
            "subject_email": "alex@example.org",
            "organization_name": "Smith & Sons' Data",
        }
        subject_line, body = complaints.templating.render("access_request", "en", context)
        self.assertIn("Alex O'Brien", body)
        self.assertNotIn("&#x27;", subject_line + body)
        self.assertNotIn("&amp;", body)
