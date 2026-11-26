# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Live IMAP scans against an in-process fake server (no network)."""

import datetime
import email.message
import os
import ssl
import sys
import types
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from unlist import crypto
from unlist.cases.models import Case, Draft
from unlist.mail import imap, live
from unlist.mail.models import Discovery, ImportRun, MailboxConnection
from unlist.mail.tests.fake_mail import FakeIMAPServer, FakeSMTP, Folder
from unlist.mail.tests.helpers import DataDirMixin, load_organizations, make_subject
from unlist.organizations.models import Organization
from unlist.subjects.models import Mailbox

PASSWORD = "app-password"
SETTINGS = {
    "imap_host": "imap.example.org",
    "imap_port": 993,
    "smtp_host": "smtp.example.org",
    "smtp_port": 465,
    "smtp_security": "ssl",
    "username": "alex@example.org",
}


def message(
    n, sender="newsletter@bigshop.de", subject="Neue Herbstmode", date="Wed, 01 Oct 2025 09:00:00 +0000", extra=""
):
    domain = sender.rpartition("@")[2]
    text = (
        f"Authentication-Results: mx.example.org; dkim=pass header.i=@{domain}; dmarc=pass header.from={domain}\n"
        f'From: "Sender" <{sender}>\n'
        "To: alex@example.org\n"
        f"Subject: {subject}\n"
        f"Date: {date}\n"
        f"Message-ID: <m{n}@{domain}>\n"
        f"List-Unsubscribe: <https://{domain}/u>\n"
        f"{extra}"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        f"BODYSECRET {n}\n"
    )
    return text.replace("\n", "\r\n").encode()


class KeyMixin:
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"UNLIST_KEY": crypto.generate_key()})
        patcher.start()
        self.addCleanup(patcher.stop)
        crypto.reset_cache()
        self.addCleanup(crypto.reset_cache)


class ScanTestCase(KeyMixin, DataDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        load_organizations()
        self.subject = make_subject()
        self.mailbox = self.subject.mailboxes.get()
        self.connection = live.save_connection(self.mailbox, SETTINGS, PASSWORD)
        self.inbox = Folder(uidvalidity=7, messages={1: message(1), 2: message(2, "info@pay.example", "Your receipt")})
        self.server = FakeIMAPServer({"INBOX": self.inbox})
        patcher = mock.patch.object(imap, "reply_ingester", return_value=None)
        self.reply_ingester = patcher.start()
        self.addCleanup(patcher.stop)

    def scan(self):
        with self.server.installed():
            run = imap.scan_connection(self.connection)
        self.connection.refresh_from_db()
        return run

    def fetches(self):
        return [command for command in self.server.commands if command.startswith("UID FETCH")]


class ReadOnlyHeaderScanTests(ScanTestCase):
    def test_examines_and_fetches_headers_only_with_peek(self):
        run = self.scan()

        self.assertEqual(run.failure, "")
        self.assertEqual((run.source, run.total, run.authenticated), (ImportRun.Source.IMAP, 2, 2))
        self.assertIn('EXAMINE "INBOX"', self.server.commands)
        self.assertFalse([c for c in self.server.commands if c.startswith("SELECT")])
        self.assertEqual(
            self.fetches(),
            [
                "UID FETCH 1:2 (BODY.PEEK[HEADER.FIELDS (From Sender Reply-To Date Subject Message-ID In-Reply-To "
                "References List-Id List-Unsubscribe List-Unsubscribe-Post Precedence Auto-Submitted "
                "Authentication-Results Content-Type X-Gmail-Labels)])"
            ],
        )
        self.assertEqual(self.server.seen, set())  # nothing marked read
        self.assertEqual(self.server.commands[-1], "LOGOUT")
        organizations = set(Discovery.objects.values_list("organization__slug", flat=True))
        self.assertEqual(organizations, {"bigshop", "payco"})
        self.assertNotIn("BODYSECRET", str(list(Discovery.objects.values())))

    def test_tls_with_certificate_verification(self):
        with self.server.installed() as factory:
            imap.scan_connection(self.connection)
        args, kwargs = factory.call_args
        self.assertEqual(args, ("imap.example.org", 993))
        context = kwargs["ssl_context"]
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_prefers_the_all_mail_folder(self):
        all_mail = Folder(uidvalidity=3, messages={10: message(1), 11: message(3)}, special_use="\\All")
        self.server.folders["[Gmail]/All Mail"] = all_mail
        run = self.scan()
        self.assertIn('EXAMINE "[Gmail]/All Mail"', self.server.commands)
        self.assertNotIn('EXAMINE "INBOX"', self.server.commands)
        self.assertEqual(run.total, 2)
        self.assertEqual(
            (self.connection.folder, self.connection.uidvalidity, self.connection.last_uid), ("[Gmail]/All Mail", 3, 11)
        )

    def test_all_mail_folder_from_list_lines(self):
        client = mock.Mock()
        client.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"', b'(\\All \\HasNoChildren) "/" "[Google Mail]/Alle Nachrichten"'],
        )
        self.assertEqual(imap.choose_folder(client), "[Google Mail]/Alle Nachrichten")
        client.list.return_value = ("OK", [(b'(\\All) "/" {8}', b"All Mail")])
        self.assertEqual(imap.choose_folder(client), "All Mail")
        client.list.return_value = ("OK", [b'(\\HasNoChildren) "/" INBOX'])
        self.assertEqual(imap.choose_folder(client), "INBOX")


class IncrementalScanTests(ScanTestCase):
    def test_only_new_uids_are_fetched(self):
        self.scan()
        self.assertEqual((self.connection.uidvalidity, self.connection.last_uid), (7, 2))
        self.inbox.messages[5] = message(5, "news@brand.example", "Brand news")
        self.server.commands.clear()

        run = self.scan()

        self.assertIn("UID SEARCH UID 3:*", self.server.commands)
        self.assertEqual([command.split()[2] for command in self.fetches()], ["5"])
        self.assertEqual(run.total, 1)
        self.assertEqual(self.connection.last_uid, 5)

    def test_nothing_new_fetches_nothing(self):
        self.scan()
        self.server.commands.clear()
        run = self.scan()  # "UID SEARCH UID 3:*" answers 2, the highest UID: it must be ignored
        self.assertEqual(self.fetches(), [])
        self.assertEqual((run.total, run.failure), (0, ""))
        self.assertEqual(self.connection.last_uid, 2)
        self.assertIsNotNone(self.connection.last_scan_at)

    def test_changed_uidvalidity_rescans_the_folder_without_counting_twice(self):
        self.scan()
        bigshop = Discovery.objects.get(organization__slug="bigshop")
        self.assertEqual(bigshop.email_count, 1)
        self.server.folders["INBOX"] = Folder(
            uidvalidity=8, messages={1: message(2, "info@pay.example"), 2: message(1)}
        )
        self.server.commands.clear()

        run = self.scan()

        self.assertEqual([command.split()[2] for command in self.fetches()], ["1:2"])
        self.assertEqual((run.total, run.duplicates), (2, 2))
        self.assertEqual((self.connection.uidvalidity, self.connection.last_uid), (8, 2))
        bigshop.refresh_from_db()
        self.assertEqual(bigshop.email_count, 1)

    def test_batches_are_split(self):
        self.inbox.messages.update({n: message(n) for n in range(3, 8)})
        with mock.patch.object(imap, "BATCH", 3):
            run = self.scan()
        self.assertEqual([command.split()[2] for command in self.fetches()], ["1:3", "4:6", "7"])
        self.assertEqual(run.total, 7)

    def test_sequence_set(self):
        self.assertEqual(imap.sequence_set([1, 2, 3, 7, 9, 10]), "1:3,7,9:10")
        self.assertEqual(imap.sequence_set([4]), "4")


class FailureTests(ScanTestCase):
    def test_refused_app_password_points_to_file_import(self):
        self.server.password = "something else"
        run = self.scan()
        self.assertIn("file import", run.failure)
        self.assertIn("Outlook.com and Microsoft 365 generally require OAuth for IMAP", run.failure)
        self.assertNotIn("OAuth client", run.failure)
        self.assertEqual(self.connection.last_error, run.failure)
        self.assertFalse([c for c in self.server.commands if c.startswith(("EXAMINE", "UID"))])
        self.assertIsNone(self.connection.last_scan_at)
        self.assertEqual(self.connection.last_uid, 0)

    def test_unreachable_server(self):
        with mock.patch("imaplib.IMAP4_SSL", side_effect=ConnectionRefusedError(111, "Connection refused")):
            run = imap.scan_connection(self.connection)
        self.assertIn("Could not reach the IMAP server imap.example.org:993", run.failure)

    def test_bad_certificate(self):
        error = ssl.SSLCertVerificationError(1, "certificate verify failed")
        error.verify_message = "Hostname mismatch"
        with mock.patch("imaplib.IMAP4_SSL", side_effect=error):
            run = imap.scan_connection(self.connection)
        self.assertIn("could not be verified (Hostname mismatch)", run.failure)

    def test_a_successful_scan_clears_the_last_error(self):
        self.connection.record_error("old problem")
        self.scan()
        self.assertEqual(self.connection.last_error, "")

    def test_test_login_only_logs_in_and_out(self):
        with self.server.installed():
            imap.test_login(self.connection)
        verbs = [c.split()[0] for c in self.server.commands if not c.startswith("CAPABILITY")]
        self.assertEqual(verbs, ["LOGIN", "LOGOUT"])  # imaplib asks for CAPABILITY on its own

    def test_connection_test_reports_imap_and_smtp(self):
        self.server.password = "wrong"
        with self.server.installed(), FakeSMTP.installed():
            results = live.test_connection(self.connection)
        self.assertEqual([(what, ok) for what, ok, _ in results], [("IMAP", False), ("SMTP", True)])
        self.assertEqual(FakeSMTP.instances[0].calls, ["LOGIN alex@example.org", "QUIT"])
        self.connection.refresh_from_db()
        self.assertIn("file import", self.connection.last_error)


class ReplyTests(ScanTestCase):
    def setUp(self):
        super().setUp()
        self.ingest = mock.Mock()
        self.reply_ingester.return_value = self.ingest
        bigshop = Organization.objects.get(slug="bigshop")
        self.case = Case.objects.create(subject=self.subject, organization=bigshop, reference="U-7KQ3", state="waiting")
        Case.objects.filter(pk=self.case.pk).update(created_at=datetime.datetime(2025, 9, 1, tzinfo=datetime.UTC))
        Draft.objects.create(
            case=self.case,
            kind="access_request",
            lang="de",
            recipient="datenschutz@bigshop.de",
            sender="alex@example.org",
            subject_line="Auskunft [Ref U-7KQ3]",
            body="...",
            status=Draft.Status.SENT,
            return_state="found",
            message_id="<request-1@example.org>",
        )
        self.inbox.messages = {
            1: message(1, date="Mon, 03 Mar 2025 09:00:00 +0000"),  # bigshop newsletter before the Case
            2: message(2, "noreply@other.example", "Re: Auskunft", extra="In-Reply-To: <request-1@example.org>\n"),
            3: message(3, "privacy@processor.example", "Ihre Anfrage [Ref U-7KQ3]"),
            4: message(4, "alex@example.org", "Auskunft [Ref U-7KQ3]"),  # the Subject's own sent copy
            5: message(5, "service@bigshop.de", "Ihr Anliegen"),  # bigshop after the Case was opened
            6: message(6, "info@pay.example", "Your receipt"),
        }

    def test_candidate_replies_are_fetched_in_full_and_ingested(self):
        run = self.scan()

        self.assertEqual(run.failure, "")
        self.assertEqual(self.fetches()[-1], "UID FETCH 2:3,5 (BODY.PEEK[])")
        self.assertEqual(self.server.seen, set())
        self.assertEqual(self.ingest.call_count, 3)
        for call, uid in zip(self.ingest.call_args_list, [2, 3, 5], strict=True):
            (subject, parsed), kwargs = call
            self.assertEqual(subject, self.subject)
            self.assertIsInstance(parsed, email.message.EmailMessage)
            self.assertEqual(kwargs, {"source": "imap", "raw": self.inbox.messages[uid]})
            self.assertIn(f"BODYSECRET {uid}", parsed.get_body().get_content())
        self.assertEqual(self.connection.last_uid, 6)

    def test_a_reply_the_cases_app_cannot_read_is_counted_and_skipped(self):
        self.ingest.side_effect = [ValueError("odd"), None, None]
        with self.assertLogs("unlist.mail", "ERROR"):
            run = self.scan()
        self.assertEqual(run.failure, "")
        self.assertEqual(self.ingest.call_count, 3)
        self.assertEqual(run.errors, 1)
        self.assertEqual(self.connection.last_uid, 6)

    def test_closed_case_domain_is_no_candidate_but_references_still_are(self):
        Case.objects.filter(pk=self.case.pk).update(state="closed")
        self.scan()
        self.assertEqual(self.fetches()[-1], "UID FETCH 2:3 (BODY.PEEK[])")

    def test_connection_lost_while_fetching_replies_resumes_next_time(self):
        self.server.fail_fetch_after = 1  # the header fetch works, the full fetch fails
        with self.assertLogs("unlist.mail", "WARNING"):
            run = self.scan()
        self.assertIn("next scan continues", run.failure)
        self.assertEqual(self.connection.last_uid, 1)  # UID 2 was the first reply not ingested
        self.assertEqual(Discovery.objects.count(), 2)  # discovery was recorded
        self.server.fail_fetch_after = None
        self.server.commands.clear()
        run = self.scan()
        self.assertEqual(run.failure, "")
        self.assertEqual(self.ingest.call_count, 3)
        self.assertEqual(run.duplicates, 4)  # UIDs 2, 3, 5 and 6 again; 4 is the Subject's own (personal)

    def test_without_the_replies_module_nothing_is_fetched_in_full(self):
        self.reply_ingester.return_value = None
        run = self.scan()
        self.assertEqual(run.failure, "")
        self.assertFalse([c for c in self.fetches() if "BODY.PEEK[]" in c])


class ReplyIngesterTests(SimpleTestCase):
    def test_missing_replies_module_means_no_ingestion(self):
        with mock.patch.dict(sys.modules, {"unlist.cases.replies": None}):
            self.assertIsNone(imap.reply_ingester())

    def test_uses_ingest_message_when_present(self):
        module = types.ModuleType("unlist.cases.replies")
        module.ingest_message = mock.Mock()
        with mock.patch.dict(sys.modules, {"unlist.cases.replies": module}):
            self.assertIs(imap.reply_ingester(), module.ingest_message)


class ScheduledRescanTests(ScanTestCase):
    def run_job(self, now):
        from unlist.mail import jobs

        with self.server.installed():
            result = jobs.rescan_live_mailboxes(now)
        self.connection.refresh_from_db()
        return result

    def test_job_is_registered(self):
        from unlist.core import scheduler
        from unlist.mail import jobs

        self.assertIn(jobs.rescan_live_mailboxes, scheduler.JOBS)

    def test_off_by_default(self):
        self.assertFalse(MailboxConnection._meta.get_field("scheduled_rescans").default)
        self.assertIsNone(self.run_job(timezone.now()))
        self.assertEqual(self.server.clients, [])

    def test_opt_in_and_at_most_every_six_hours(self):
        self.connection.scheduled_rescans = True
        self.connection.save()
        start = timezone.now()
        self.assertIn("1 live mailbox(es) re-scanned", self.run_job(start))
        self.assertEqual(len(self.server.clients), 1)
        self.assertIsNone(self.run_job(start + datetime.timedelta(hours=5, minutes=59)))
        self.assertEqual(len(self.server.clients), 1)
        self.assertIsNotNone(self.run_job(start + datetime.timedelta(hours=6)))
        self.assertEqual(len(self.server.clients), 2)

    def test_failing_connection_is_not_retried_sooner(self):
        self.connection.scheduled_rescans = True
        self.connection.save()
        self.server.password = "revoked"
        start = timezone.now()
        self.assertIn("1 failed", self.run_job(start))
        self.assertIsNone(self.run_job(start + datetime.timedelta(hours=1)))
        self.assertEqual(len(self.server.clients), 1)

    def test_import_only_mailbox_is_not_scanned(self):
        self.connection.scheduled_rescans = True
        self.connection.save()
        Mailbox.objects.filter(pk=self.mailbox.pk).update(mode=Mailbox.Mode.IMPORT)
        self.assertIsNone(self.run_job(timezone.now()))
        self.assertEqual(self.server.clients, [])
