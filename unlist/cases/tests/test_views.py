# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Case pages (#47)."""

import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from unlist import paths
from unlist.cases import services
from unlist.cases.lifecycle import State
from unlist.cases.models import Case, CaseEvent, Draft
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject


class CaseViewTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)
        self.subject = make_subject()
        self.organization = make_organization()

    def open(self):
        return services.open_case(self.subject, self.organization, on=DAY0)

    def test_pages_need_login(self):
        case = self.open()
        self.client.logout()
        for url in ["/cases/", "/cases/new/", f"/cases/{case.pk}/", f"/cases/{case.pk}/outcome/"]:
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_open_a_case_by_search(self):
        response = self.client.get("/cases/new/", {"subject": self.subject.pk, "q": "acme"})
        self.assertContains(response, "ACME Ltd")
        response = self.client.post(
            "/cases/new/", {"subject": self.subject.pk, "organization": "acme", "direct_removal": "on"}
        )
        case = Case.objects.get()
        self.assertRedirects(response, f"/cases/{case.pk}/", fetch_redirect_response=False)
        self.assertTrue(case.direct_removal)
        self.assertEqual(case.pending_draft.kind, "removal_request")

    def test_open_refused_without_consent_shows_why(self):
        subject = make_subject(name="Sam", email="sam@example.org", consent=False)
        response = self.client.post("/cases/new/", {"subject": subject.pk, "organization": "acme"}, follow=True)
        self.assertContains(response, "no active consent")
        self.assertFalse(Case.objects.exists())

    def test_list_filters(self):
        case = self.open()
        self.assertContains(self.client.get("/cases/"), case.reference)
        self.assertContains(self.client.get("/cases/", {"state": "awaiting_approval"}), case.reference)
        self.assertNotContains(self.client.get("/cases/", {"state": "closed"}), case.reference)
        self.assertNotContains(self.client.get("/cases/", {"subject": self.subject.pk + 1}), case.reference)

    def test_detail_approve_hand_over_and_mark_sent(self):
        case = self.open()
        draft = case.pending_draft
        response = self.client.get(f"/cases/{case.pk}/")
        self.assertContains(response, "Approve and hand over to the Subject, to send to privacy@acme.example")
        self.assertContains(response, "Stop pursuing this Organization")
        self.assertNotContains(response, "Prepare a reminder")
        self.assertNotContains(response, "Record the Organization")
        self.assertNotContains(response, 'style="')
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "cases/cases.css")

        self.assertEqual(self.client.get(f"/cases/drafts/{draft.pk}/eml/").status_code, 404)
        self.client.post(f"/cases/drafts/{draft.pk}/approve/")
        draft.refresh_from_db()
        self.assertEqual(draft.status, Draft.Status.HANDED_OVER)
        response = self.client.get(f"/cases/{case.pk}/")
        self.assertContains(response, "Download the .eml")
        self.assertContains(response, "mailto:privacy@acme.example?subject=")

        eml = self.client.get(f"/cases/drafts/{draft.pk}/eml/")
        self.assertEqual(eml["Content-Type"], "message/rfc822")
        self.assertIn(case.reference.encode(), eml.content)
        self.assertIn(b"To: privacy@acme.example", eml.content)

        response = self.client.post(f"/cases/drafts/{draft.pk}/sent/", {"sent_on": DAY0.isoformat()}, follow=True)
        self.assertContains(response, "before the day the draft was approved")
        self.client.post(f"/cases/drafts/{draft.pk}/sent/", {"sent_on": timezone.localdate().isoformat()})
        case.refresh_from_db()
        self.assertEqual(case.state, State.WAITING)
        response = self.client.get(f"/cases/{case.pk}/")
        self.assertContains(response, "How the deadline was worked out")
        self.assertContains(response, "Rule used")
        self.assertContains(response, "Record the Organization")

    def test_record_outcome_with_upload(self):
        case = self.open()
        services.approve(case.pending_draft, on=DAY0)
        services.mark_sent(case.pending_draft, on=DAY0)
        with tempfile.TemporaryDirectory() as data_dir, mock.patch.object(paths, "DATA_DIR", Path(data_dir)):
            response = self.client.get(f"/cases/{case.pk}/outcome/")
            self.assertContains(response, "Sent the data it holds")
            self.assertNotContains(response, "Confirmed removal")
            upload = SimpleUploadedFile("reply.eml", b"Subject: Re\n\nWe hold nothing.", content_type="message/rfc822")
            response = self.client.post(
                f"/cases/{case.pk}/outcome/",
                {"outcome": "nothing_held", "occurred_on": "2025-03-10", "note": "Polite answer", "file": upload},
            )
            self.assertRedirects(response, f"/cases/{case.pk}/", fetch_redirect_response=False)
            event = case.events.get(kind=CaseEvent.Kind.NOTHING_HELD)
            self.assertEqual(event.details["note"], "Polite answer")
            attachment = event.attachments.get()
            download = self.client.get(f"/cases/attachments/{attachment.pk}/")
            self.assertEqual(b"".join(download.streaming_content), b"Subject: Re\n\nWe hold nothing.")
        case.refresh_from_db()
        self.assertEqual(case.state, State.CLOSED)

    def test_illegal_action_is_refused_with_a_message(self):
        case = self.open()
        response = self.client.post(f"/cases/{case.pk}/action/send_reminder/", follow=True)
        self.assertContains(response, "only for an Organization that has missed its deadline")
        self.assertEqual(self.client.post(f"/cases/{case.pk}/action/approve_all/").status_code, 404)

    def test_stop_and_edit(self):
        case = self.open()
        draft = case.pending_draft
        response = self.client.post(
            f"/cases/drafts/{draft.pk}/edit/", {"subject_line": f"Access [Ref {case.reference}]", "body": "Hello"}
        )
        self.assertRedirects(response, f"/cases/{case.pk}/", fetch_redirect_response=False)
        draft.refresh_from_db()
        self.assertEqual(draft.body, "Hello")
        self.client.post(f"/cases/{case.pk}/action/stop/")
        case.refresh_from_db()
        self.assertEqual(case.state, State.CLOSED)
        self.assertContains(self.client.get(f"/cases/{case.pk}/"), "Reopen the Case")

    def test_letter_page(self):
        letter_org = make_organization(
            slug="post", name="Post Ltd", email="", address="Post Ltd\n1 Street", preferred_channel="letter"
        )
        case = services.open_case(self.subject, letter_org, on=DAY0)
        draft = case.pending_draft
        response = self.client.get(f"/cases/{case.pk}/")
        self.assertContains(response, "Approve and hand over to the Subject, to post to the address shown")
        services.approve(draft, on=DAY0)
        response = self.client.get(f"/cases/drafts/{draft.pk}/letter/")
        self.assertContains(response, "1 Street")
        self.assertContains(response, case.reference)

    def test_recheck_override_form(self):
        case = self.open()
        self.client.post(f"/cases/{case.pk}/recheck/", {"recheck_override": "close"})
        case.refresh_from_db()
        self.assertEqual(case.recheck_override, "close")
        self.client.post(f"/cases/{case.pk}/recheck/", {"recheck_override": "soon"})
        case.refresh_from_db()
        self.assertEqual(case.recheck_override, "close")
