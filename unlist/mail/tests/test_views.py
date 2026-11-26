# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import os
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from unlist.mail import importer
from unlist.mail.models import Discovery, ImportRun, UnassignedSender
from unlist.mail.tests.helpers import DataDirMixin, fake_cases_module, fixture_upload, load_organizations, make_subject
from unlist.organizations import lookup
from unlist.organizations.models import Organization


class ViewTests(DataDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.operator = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(self.operator)
        load_organizations()
        self.subject = make_subject()
        patcher = mock.patch.object(importer, "RUN_IN_BACKGROUND", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def url(self, name):
        return f"/mail/subjects/{self.subject.pk}/{name}"

    def upload(self):
        return self.client.post(self.url("import/"), {"file": fixture_upload()})

    def test_pages_need_login(self):
        self.client.logout()
        self.upload()
        self.assertFalse(ImportRun.objects.exists())
        for path in ["import/", "discoveries/", "unassigned/"]:
            response = self.client.get(self.url(path))
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/login/", response["Location"])
        for path in ["discoveries/pursue-all/", "discoveries/1/pursue/", "discoveries/1/ignore/"]:
            self.assertEqual(self.client.post(self.url(path)).status_code, 302, path)

    def test_upload_page_explains_exports(self):
        response = self.client.get(self.url("import/"))
        self.assertContains(response, "Google Takeout")
        self.assertContains(response, "import-only")
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, "unlist/unlist.css")  # the one stylesheet (#53)
        self.assertNotContains(response, "style=")

    def test_upload_imports_and_lists_discoveries_by_evidence(self):
        response = self.client.post(self.url("import/"), {"file": fixture_upload()}, follow=True)
        self.assertRedirects(response, self.url("discoveries/"))
        run = ImportRun.objects.get()
        self.assertEqual((run.total, run.authenticated), (10, 7))
        self.assertEqual(self.leftover_files(), [])  # the upload went to the data directory and is gone
        page = response.content.decode()
        order = [page.index(name) for name in ["Big Shop GmbH", "PayCo Ltd", "Streamly Inc.", "Brand SE"]]
        self.assertEqual(order, sorted(order))
        self.assertIn("Imported 10 messages", page)
        self.assertIn("Pursue all 4 with account evidence", page)
        self.assertIn("2 senders to assign", page)

    def test_upload_is_streamed_into_the_data_directory(self):
        with mock.patch.object(importer.os, "link", wraps=os.link) as link:
            self.upload()
        source, target = link.call_args.args
        self.assertTrue(Path(source).is_relative_to(self.data_dir))  # Django's own copy, not in /tmp
        self.assertTrue(Path(target).is_relative_to(self.data_dir))
        self.assertEqual(self.leftover_files(), [])

    def test_a_file_without_messages_gets_a_hint(self):
        upload = SimpleUploadedFile("takeout.zip", b"PK\x03\x04 not an mbox")
        response = self.client.post(self.url("import/"), {"file": upload}, follow=True)
        self.assertContains(response, "found no messages")
        self.assertEqual(self.leftover_files(), [])

    def test_upload_requires_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.operator)
        response = client.post(self.url("import/"), {"file": fixture_upload()})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ImportRun.objects.exists())

    def test_upload_in_the_background(self):
        with (
            mock.patch.object(importer, "RUN_IN_BACKGROUND", True),
            mock.patch.object(importer.threading, "Thread") as thread,
        ):
            response = self.client.post(self.url("import/"), {"file": fixture_upload()}, follow=True)
        thread.return_value.start.assert_called_once()
        self.assertContains(response, "The import has started")
        self.assertContains(response, "still running")
        path = thread.call_args.kwargs["args"][1]
        self.assertTrue(path.is_file())  # kept for the thread, inside the data directory
        self.assertTrue(path.is_relative_to(self.data_dir))

    def test_pursue_calls_open_case(self):
        self.upload()
        discovery = Discovery.objects.get(organization__slug="payco")
        open_case = mock.Mock()
        with fake_cases_module(open_case):
            response = self.client.post(self.url(f"discoveries/{discovery.pk}/pursue/"), follow=True)
        open_case.assert_called_once_with(self.subject, discovery.organization)
        self.assertContains(response, "Case opened for PayCo Ltd")
        self.assertContains(response, "already a Case")
        discovery.refresh_from_db()
        self.assertEqual(discovery.status, "pursued")

    def test_pursue_error_is_shown(self):
        self.upload()
        discovery = Discovery.objects.get(organization__slug="payco")
        with fake_cases_module(mock.Mock(side_effect=ValueError("no confirmed contact"))):
            response = self.client.post(self.url(f"discoveries/{discovery.pk}/pursue/"), follow=True)
        self.assertContains(response, "PayCo Ltd: no confirmed contact")
        discovery.refresh_from_db()
        self.assertEqual(discovery.status, "new")

    def test_pursue_all(self):
        self.upload()
        open_case = mock.Mock()
        with fake_cases_module(open_case):
            response = self.client.post(self.url("discoveries/pursue-all/"), follow=True)
        self.assertEqual(open_case.call_count, 4)
        self.assertContains(response, "4 Cases opened")

    def test_ignore_and_unignore(self):
        self.upload()
        discovery = Discovery.objects.get(organization__slug="brand")
        self.client.post(self.url(f"discoveries/{discovery.pk}/ignore/"))
        discovery.refresh_from_db()
        self.assertEqual(discovery.status, "ignored")
        self.assertContains(self.client.get(self.url("discoveries/")), "Un-ignore")
        self.client.post(self.url(f"discoveries/{discovery.pk}/unignore/"))
        discovery.refresh_from_db()
        self.assertEqual(discovery.status, "new")

    def test_other_subjects_discoveries_are_out_of_reach(self):
        self.upload()
        other = make_subject("Sam")
        discovery = Discovery.objects.get(organization__slug="brand")
        response = self.client.post(f"/mail/subjects/{other.pk}/discoveries/{discovery.pk}/ignore/")
        self.assertEqual(response.status_code, 404)

    def test_unassigned_senders_assign_and_ignore(self):
        self.upload()
        page = self.client.get(self.url("unassigned/"))
        self.assertContains(page, "The Daily Unknown")
        self.assertContains(page, "shared domain")
        sender = UnassignedSender.objects.get(domain="unknownnews.example")
        search = self.client.get(self.url(f"unassigned/{sender.pk}/assign/"), {"q": "brand"})
        self.assertContains(search, "Brand SE")
        response = self.client.post(self.url(f"unassigned/{sender.pk}/assign/"), {"organization": "brand"}, follow=True)
        self.assertContains(response, "assigned to Brand SE")
        self.assertEqual(lookup.by_domain("unknownnews.example").slug, "brand")
        podcast = UnassignedSender.objects.get(domain="beehiiv.com")
        self.client.post(self.url(f"unassigned/{podcast.pk}/ignore/"))
        podcast.refresh_from_db()
        self.assertEqual(podcast.status, "ignored")
        self.client.post(self.url(f"unassigned/{podcast.pk}/unignore/"))
        podcast.refresh_from_db()
        self.assertEqual(podcast.status, "open")

    def test_assign_by_creating_a_local_organization(self):
        self.upload()
        sender = UnassignedSender.objects.get(domain="unknownnews.example")
        self.client.post(self.url(f"unassigned/{sender.pk}/assign/"), {"create_stub": "1"})
        stub = lookup.by_domain("unknownnews.example")
        self.assertEqual(stub.quality, "local")
        self.assertEqual(Discovery.objects.get(organization=stub).email_count, 1)

    def test_assign_to_an_unknown_organization(self):
        self.upload()
        sender = UnassignedSender.objects.get(domain="unknownnews.example")
        response = self.client.post(self.url(f"unassigned/{sender.pk}/assign/"), {"organization": "nope"}, follow=True)
        self.assertContains(response, "does not exist")
        self.assertEqual(Organization.objects.filter(quality="local").count(), 1)
