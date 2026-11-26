# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import email
import mailbox
import os
from unittest import mock

from django.apps import apps
from django.test import TestCase

from unlist.mail import importer, scanner, services
from unlist.mail.models import Discovery, ImportRun, SeenMessage, UnassignedSender
from unlist.mail.tests.helpers import (
    BODY_MARKER,
    FIXTURES,
    DataDirMixin,
    fake_cases_module,
    fixture_upload,
    load_organizations,
    make_subject,
)
from unlist.organizations import lookup
from unlist.organizations.models import Domain, LocalOverride, Organization

LATER_ORDER = b"""From 1789000000000000011@xxx Wed Oct 01 09:00:00 +0000 2025
Authentication-Results: mx.google.com; dkim=pass header.i=@bigshop.de; dmarc=pass header.from=bigshop.de
From: "Big Shop" <newsletter@bigshop.de>
Subject: Neue Herbstmode
Date: Wed, 01 Oct 2025 09:00:00 +0000
Message-ID: <nl-oct@bigshop.de>
List-Unsubscribe: <https://bigshop.de/u>
Content-Type: text/plain; charset=utf-8

BODYSECRET-K

"""


class ImportTests(DataDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        load_organizations()
        self.subject = make_subject()

    def import_fixture(self, **kwargs):
        return importer.import_mbox(self.subject, fixture_upload(**kwargs), background=False)

    def discovery(self, slug):
        return Discovery.objects.get(subject=self.subject, organization__slug=slug)

    def test_counts(self):
        run = self.import_fixture()
        self.assertEqual(run.failure, "")
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.filename, "discovery.mbox")
        self.assertEqual(
            (run.total, run.authenticated, run.personal_skipped, run.unauthenticated_skipped, run.spam_skipped),
            (10, 7, 1, 1, 1),
        )
        self.assertEqual((run.duplicates, run.errors), (0, 0))

    def test_grades_and_mappings(self):
        self.import_fixture()
        found = {
            d.organization.slug: (d.evidence, d.email_count, d.strongest_subject, d.status)
            for d in Discovery.objects.filter(subject=self.subject).select_related("organization")
        }
        stub = Organization.objects.get(quality="local")
        self.assertEqual(
            found,
            {
                "bigshop": (scanner.ORDER_MARKUP, 1, "Ihre Bestellbestätigung Nr. 12345", "new"),
                "payco": (scanner.TRANSACTION, 1, "Your receipt from PayCo #8812", "new"),
                "brand": (scanner.BULK, 1, "Our autumn collection is here", "new"),
                "streamly": (scanner.ACCOUNT, 1, "Reset your password", "new"),
                stub.slug: (scanner.TRANSACTION, 1, "Order confirmation #A-77", "new"),
            },
        )
        bigshop = self.discovery("bigshop")
        self.assertEqual(bigshop.first_seen.isoformat(), "2025-03-03T09:15:00+00:00")
        self.assertEqual(bigshop.first_seen, bigshop.last_seen)

    def test_stub_for_an_unknown_domain_with_transaction_evidence(self):
        self.import_fixture()
        stub = lookup.by_domain("tinystore.example")
        self.assertEqual(stub.quality, "local")
        self.assertEqual(stub.domains, ["tinystore.example"])
        self.assertFalse(stub.contact_confirmed)
        self.assertIsNone(lookup.by_domain("unknownnews.example"))  # bulk only: no stub
        self.assertEqual(Organization.objects.filter(quality="local").count(), 1)

    def test_skipped_mail_leaves_no_trace(self):
        self.import_fixture()
        self.assertFalse(Organization.objects.filter(domains__icontains="spammy").exists())
        self.assertFalse(UnassignedSender.objects.filter(domain__in=["gmail.com", "spammy.example"]).exists())
        self.assertEqual(self.discovery("bigshop").email_count, 1)  # the unauthenticated look-alike is not counted

    def test_unassigned_senders(self):
        self.import_fixture()
        senders = {
            (s.domain, s.display_name): (s.ambiguous, s.evidence, s.email_count, s.status)
            for s in UnassignedSender.objects.filter(subject=self.subject)
        }
        self.assertEqual(
            senders,
            {
                ("unknownnews.example", "The Daily Unknown"): (False, scanner.BULK, 1, "open"),
                ("beehiiv.com", "Cool Podcast"): (True, scanner.BULK, 1, "open"),
            },
        )

    def test_no_body_text_is_stored_anywhere(self):
        self.import_fixture()
        models = list(apps.get_app_config("mail").get_models()) + [Organization, LocalOverride, Domain]
        checked = 0
        for model in models:
            for row in model.objects.all():
                for field in model._meta.concrete_fields:
                    value = field.value_from_object(row)
                    self.assertNotIn(BODY_MARKER, str(value), f"{model.__name__}.{field.name}")
                    self.assertNotIn("Musterstra", str(value), f"{model.__name__}.{field.name}")
                    checked += 1
        self.assertGreater(checked, 50)
        self.assertEqual(self.leftover_files(), [])  # the upload is deleted after the scan

    def test_reimport_counts_nothing_twice_and_keeps_ignored(self):
        self.import_fixture()
        services.ignore(self.discovery("bigshop"))
        run = self.import_fixture()
        self.assertEqual((run.authenticated, run.duplicates), (7, 7))
        self.assertEqual(self.discovery("payco").email_count, 1)

        # A later export: the old messages plus a new newsletter from Big Shop.
        run = self.import_fixture(extra=LATER_ORDER)
        self.assertEqual((run.total, run.duplicates), (11, 7))
        bigshop = self.discovery("bigshop")
        self.assertEqual(bigshop.email_count, 2)
        self.assertEqual(bigshop.status, Discovery.Status.IGNORED)
        self.assertEqual(bigshop.evidence, scanner.ORDER_MARKUP)  # the strongest evidence stays
        self.assertEqual(bigshop.strongest_subject, "Ihre Bestellbestätigung Nr. 12345")
        self.assertEqual(bigshop.first_seen.isoformat(), "2025-03-03T09:15:00+00:00")
        self.assertEqual(bigshop.last_seen.isoformat(), "2025-10-01T09:00:00+00:00")
        self.assertEqual(Discovery.objects.filter(subject=self.subject).count(), 5)
        self.assertEqual(ImportRun.objects.filter(subject=self.subject).count(), 3)

    def test_ignored_sender_stays_ignored(self):
        self.import_fixture()
        sender = UnassignedSender.objects.get(domain="unknownnews.example")
        services.ignore_sender(sender)
        SeenMessage.objects.all().delete()  # so the same mail counts again
        self.import_fixture()
        sender.refresh_from_db()
        self.assertEqual((sender.status, sender.email_count), ("ignored", 2))

    def test_scan_messages_takes_any_iterable(self):
        """The entry point a live IMAP scan reuses: headers only, no ImportRun given."""
        headers = (
            b"Authentication-Results: mx.example.net; dmarc=pass header.from=pay.example\r\n"
            b"From: PayCo <noreply@pay.example>\r\nSubject: Invoice 7\r\nMessage-ID: <i7@pay.example>\r\n"
            b"Date: Tue, 01 Apr 2025 12:00:00 +0000\r\n\r\n"
        )
        run = importer.scan_messages(self.subject, [email.message_from_bytes(headers), None])
        self.assertEqual((run.total, run.authenticated, run.errors), (2, 1, 1))
        self.assertEqual(self.discovery("payco").evidence, scanner.TRANSACTION)

    def test_a_broken_file_records_the_failure_and_is_deleted(self):
        with mock.patch.object(importer, "scan_messages", side_effect=RuntimeError("disk on fire")):
            run = self.import_fixture()
        self.assertIn("disk on fire", run.failure)
        self.assertIsNone(run.finished_at)
        self.assertEqual(self.leftover_files(), [])

    def test_mboxo_quoting_is_handled_by_the_standard_library(self):
        box = mailbox.mbox(FIXTURES / "discovery.mbox", create=False)
        self.assertEqual(len(box), 10)
        self.assertIn(b">From the PayCo team", box.get_bytes(1))

    def test_stale_runs_are_marked_and_uploads_removed(self):
        old = ImportRun.objects.create(subject=self.subject)
        ImportRun.objects.filter(pk=old.pk).update(started_at=old.started_at - importer.STALE_AFTER * 2)
        importer.import_dir().mkdir(parents=True)
        leftover = importer.import_dir() / "old.mbox"
        leftover.write_bytes(b"x")
        stamp = old.started_at.timestamp() - importer.STALE_AFTER.total_seconds() * 2
        os.utime(leftover, (stamp, stamp))
        importer.clean_up_stale()
        old.refresh_from_db()
        self.assertIn("interrupted", old.failure)
        self.assertFalse(leftover.exists())


class AssignTests(DataDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        load_organizations()
        self.subject = make_subject()
        importer.import_mbox(self.subject, fixture_upload(), background=False)

    def test_assign_an_unknown_domain_stores_a_domain_override(self):
        sender = UnassignedSender.objects.get(domain="unknownnews.example")
        brand = Organization.objects.get(slug="brand")
        services.assign_sender(sender, brand)
        override = LocalOverride.objects.get(organization_slug="brand", field="domains")
        self.assertEqual(override.value, ["brand.example", "unknownnews.example"])
        self.assertEqual(lookup.by_domain("unknownnews.example").slug, "brand")
        discovery = Discovery.objects.get(subject=self.subject, organization=brand)
        self.assertEqual(discovery.email_count, 2)  # the newsletter plus the sender's one email
        sender.refresh_from_db()
        self.assertEqual((sender.status, sender.organization), ("assigned", brand))

    def test_assign_a_shared_domain_sender_without_an_override(self):
        sender = UnassignedSender.objects.get(domain="beehiiv.com")
        streamly = Organization.objects.get(slug="streamly")
        services.assign_sender(sender, streamly)
        self.assertFalse(LocalOverride.objects.filter(organization_slug="streamly").exists())
        self.assertEqual(Discovery.objects.get(subject=self.subject, organization=streamly).email_count, 2)
        # A later import routes that sender's mail to the Organization.
        SeenMessage.objects.all().delete()
        importer.import_mbox(self.subject, fixture_upload(), background=False)
        self.assertEqual(Discovery.objects.get(subject=self.subject, organization=streamly).email_count, 4)


class PursueTests(DataDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        load_organizations()
        self.subject = make_subject()
        importer.import_mbox(self.subject, fixture_upload(), background=False)

    def test_pursue_all_with_account_evidence(self):
        open_case = mock.Mock()
        with fake_cases_module(open_case):
            pursued, errors = services.pursue_all_with_account_evidence(self.subject)
        self.assertEqual(errors, [])
        slugs = sorted(call.args[1].slug for call in open_case.call_args_list)
        stub = Organization.objects.get(quality="local").slug
        self.assertEqual(slugs, sorted(["bigshop", "payco", "streamly", stub]))  # not the newsletter
        self.assertTrue(all(call.args[0] == self.subject for call in open_case.call_args_list))
        self.assertEqual(Discovery.objects.filter(status="pursued").count(), 4)
        self.assertEqual(Discovery.objects.get(organization__slug="brand").status, "new")

    def test_refusals_are_reported_and_change_nothing(self):
        open_case = mock.Mock(side_effect=ValueError("the Subject has no active consent"))
        discovery = Discovery.objects.get(organization__slug="payco")
        with fake_cases_module(open_case), self.assertRaises(services.PursueError) as caught:
            services.pursue(discovery)
        self.assertIn("no active consent", str(caught.exception))
        discovery.refresh_from_db()
        self.assertEqual(discovery.status, "new")

    def test_without_the_cases_app(self):
        discovery = Discovery.objects.get(organization__slug="payco")
        with mock.patch.dict("sys.modules", {"unlist.cases.services": None}):
            with self.assertRaises(services.PursueError):
                services.pursue(discovery)
