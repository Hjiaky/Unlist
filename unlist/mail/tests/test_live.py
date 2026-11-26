# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""SMTP sending of approved drafts, stored passwords, and the connection pages (no network)."""

import shutil
import smtplib
import sqlite3
import ssl
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection as db
from django.test import TestCase

from unlist import crypto
from unlist.backup import hooks as backup_hooks
from unlist.cases import sending, services
from unlist.cases.models import Draft
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject
from unlist.mail import hooks, imap, live, smtp
from unlist.mail.models import ImportRun, MailboxConnection
from unlist.mail.tests.fake_mail import FakeIMAPServer, FakeSMTP, Folder
from unlist.mail.tests.helpers import DataDirMixin
from unlist.mail.tests.test_imap import PASSWORD, SETTINGS, KeyMixin, message
from unlist.subjects.models import Mailbox


class SmtpSenderTests(KeyMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.subject = make_subject()
        self.mailbox = self.subject.mailboxes.get()
        self.connection = live.save_connection(self.mailbox, SETTINGS, PASSWORD)
        self.case = services.open_case(self.subject, make_organization(), on=DAY0)
        self.draft = self.case.pending_draft
        fake = FakeSMTP.installed()
        fake.__enter__()
        self.addCleanup(fake.__exit__, None, None, None)

    def test_registered_as_live_sender(self):
        self.assertIn(smtp.send_draft, sending.live_senders)
        self.assertTrue(sending.will_send(self.draft))

    def test_approval_sends_the_draft_over_smtp_ssl(self):
        services.approve(self.draft, on=DAY0)

        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Draft.Status.SENT)
        (server,) = FakeSMTP.instances
        self.assertEqual((server.host, server.port, server.ssl), ("smtp.example.org", 465, True))
        self.assertEqual(server.context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(server.context.check_hostname)
        self.assertEqual(server.calls, ["LOGIN alex@example.org", "SEND", "QUIT"])
        self.assertEqual(server.password, PASSWORD)
        sent, from_addr, to_addrs = server.sent[0]
        self.assertEqual((from_addr, to_addrs), ("alex@example.org", ["privacy@acme.example"]))
        self.assertEqual(sent["Message-ID"], self.draft.message_id)
        self.assertEqual(bytes(sent), sending.eml_bytes(self.draft))  # the draft rebuilds the sent message
        event = self.case.events.filter(kind="sent").get()
        self.assertEqual(event.details["message_id"], self.draft.message_id)

    def test_starttls_on_587(self):
        self.connection.smtp_port, self.connection.smtp_security = 587, MailboxConnection.Security.STARTTLS
        self.connection.save()
        services.approve(self.draft, on=DAY0)
        (server,) = FakeSMTP.instances
        self.assertEqual((server.port, server.ssl), (587, False))
        self.assertEqual(server.calls[:2], ["STARTTLS", "LOGIN alex@example.org"])
        self.assertEqual(server.starttls_context.verify_mode, ssl.CERT_REQUIRED)

    def test_refuses_a_draft_that_was_not_approved(self):
        self.assertEqual(self.draft.status, Draft.Status.AWAITING_APPROVAL)
        self.assertFalse(smtp.send_draft(self.draft))
        self.draft.status = Draft.Status.APPROVED  # approved status without an approval time
        self.assertFalse(smtp.send_draft(self.draft))
        for status in (Draft.Status.HANDED_OVER, Draft.Status.SENT, Draft.Status.DISCARDED):
            self.draft.status = status
            self.assertFalse(smtp.send_draft(self.draft))
        self.assertEqual(FakeSMTP.instances, [])

    def approved(self):
        self.draft.status = Draft.Status.APPROVED
        self.draft.approved_at = self.draft.created_at
        self.draft.message_id = "<x@example.org>"
        return self.draft

    def test_refuses_other_channels_and_mailboxes(self):
        draft = self.approved()
        draft.channel = Draft.Channel.WEBFORM
        self.assertFalse(smtp.send_draft(draft))
        draft.channel = Draft.Channel.EMAIL
        draft.sender = "someone-else@example.org"
        self.assertFalse(smtp.send_draft(draft))
        draft.sender = "alex@example.org"
        Mailbox.objects.filter(pk=self.mailbox.pk).update(mode=Mailbox.Mode.IMPORT)
        self.assertFalse(smtp.send_draft(draft))
        Mailbox.objects.filter(pk=self.mailbox.pk).update(mode=Mailbox.Mode.LIVE)
        self.connection.delete()
        self.assertFalse(smtp.send_draft(draft))
        self.assertEqual(FakeSMTP.instances, [])

    def test_a_failure_hands_the_draft_over_and_is_kept_for_the_operator(self):
        FakeSMTP.fail_send = smtplib.SMTPRecipientsRefused({"privacy@acme.example": (550, b"No such user")})
        services.approve(self.draft, on=DAY0)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Draft.Status.HANDED_OVER)
        self.connection.refresh_from_db()
        self.assertIn(f"Sending {self.case.reference} failed", self.connection.last_error)

    def test_unreachable_server_returns_false(self):
        with mock.patch("smtplib.SMTP_SSL", side_effect=TimeoutError()):
            self.assertFalse(smtp.send_draft(self.approved()))
        self.connection.refresh_from_db()
        self.assertIn("did not answer in time", self.connection.last_error)

    def test_refused_password_returns_false_and_explains(self):
        FakeSMTP.fail_login = True
        self.assertFalse(smtp.send_draft(self.approved()))
        self.connection.refresh_from_db()
        self.assertIn("Outlook.com and Microsoft 365 generally require OAuth", self.connection.last_error)
        self.assertEqual(FakeSMTP.instances[0].calls, ["LOGIN alex@example.org", "QUIT"])

    def test_unreadable_password_returns_false(self):
        crypto.reset_cache()
        with mock.patch.dict("os.environ", {"UNLIST_KEY": crypto.generate_key()}):
            self.assertFalse(smtp.send_draft(self.approved()))
        self.connection.refresh_from_db()
        self.assertIn("cannot be read", self.connection.last_error)


class StoredPasswordTests(KeyMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.subject = make_subject()
        self.mailbox = self.subject.mailboxes.get()

    def test_password_is_stored_encrypted(self):
        connection = live.save_connection(self.mailbox, SETTINGS, PASSWORD)
        self.assertNotEqual(connection.password_encrypted, PASSWORD)
        self.assertEqual(connection.password(), PASSWORD)
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM mail_mailboxconnection")
            rows = cursor.fetchall()
        self.assertNotIn(PASSWORD, repr(rows))
        self.mailbox.refresh_from_db()
        self.assertEqual(self.mailbox.mode, Mailbox.Mode.LIVE)

    def test_empty_password_keeps_the_stored_one_and_new_server_resets_uids(self):
        connection = live.save_connection(self.mailbox, SETTINGS, PASSWORD)
        connection.folder, connection.uidvalidity, connection.last_uid = "INBOX", 5, 99
        connection.save()
        token = connection.password_encrypted
        live.save_connection(self.mailbox, dict(SETTINGS, smtp_port=587, smtp_security="starttls"), "")
        connection.refresh_from_db()
        self.assertEqual((connection.password_encrypted, connection.last_uid), (token, 99))
        live.save_connection(self.mailbox, dict(SETTINGS, imap_host="imap.other.example"), "")
        connection.refresh_from_db()
        self.assertEqual((connection.folder, connection.uidvalidity, connection.last_uid), ("", None, 0))

    def test_no_key_refuses_to_store(self):
        crypto.reset_cache()
        with (
            mock.patch.dict("os.environ", {"UNLIST_KEY": ""}),
            mock.patch.object(crypto, "KEY_FILE", Path(tempfile.gettempdir()) / "no-such-unlist.key"),
            self.assertRaises(crypto.MissingKey),
        ):
            live.save_connection(self.mailbox, SETTINGS, PASSWORD)
        self.assertFalse(MailboxConnection.objects.exists())

    def test_disconnect_deletes_the_connection_and_makes_the_mailbox_import_only(self):
        connection = live.save_connection(self.mailbox, SETTINGS, PASSWORD)
        live.disconnect(connection)
        self.assertFalse(MailboxConnection.objects.exists())
        self.mailbox.refresh_from_db()
        self.assertEqual(self.mailbox.mode, Mailbox.Mode.IMPORT)

    def test_restore_sees_every_stored_password(self):
        self.assertIn(hooks.connection_passwords, backup_hooks.stored_secrets)
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        database = directory / "unlist.sqlite3"
        with sqlite3.connect(database) as handle:
            handle.execute("CREATE TABLE mail_mailboxconnection (id INTEGER PRIMARY KEY, password_encrypted TEXT)")
            handle.executemany(
                "INSERT INTO mail_mailboxconnection (password_encrypted) VALUES (?)",
                [("token-a",), ("token-b",), ("",)],
            )
        handle.close()
        with mock.patch("unlist.backup.service.database_path", return_value=database):
            self.assertEqual(hooks.connection_passwords(), ["token-a", "token-b"])
        with mock.patch("unlist.backup.service.database_path", return_value=directory / "missing.sqlite3"):
            self.assertEqual(hooks.connection_passwords(), [])


class ConnectionPageTests(KeyMixin, DataDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        operator = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(operator)
        self.subject = make_subject(email="alex@gmail.com")
        self.mailbox = self.subject.mailboxes.get()
        self.base = f"/mail/subjects/{self.subject.pk}/mailboxes/{self.mailbox.pk}/"
        patcher = mock.patch.object(imap, "RUN_IN_BACKGROUND", False)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(imap, "reply_ingester", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def form(self, **values):
        data = {
            "imap_host": "imap.gmail.com",
            "imap_port": "993",
            "smtp_host": "smtp.gmail.com",
            "smtp": "465",
            "username": "alex@gmail.com",
            "password": PASSWORD,
        }
        data.update(values)
        return data

    def connect(self):
        return live.save_connection(self.mailbox, dict(SETTINGS, username="alex@gmail.com"), PASSWORD)

    def test_pages_need_login(self):
        self.client.logout()
        connection = self.connect()
        for path in ["connect/", "connection/"]:
            response = self.client.get(self.base + path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/", response["Location"])
        for path in ["connection/test/", "connection/scan/", "connection/rescans/", "connection/disconnect/"]:
            self.assertEqual(self.client.post(self.base + path).status_code, 302, path)
        self.assertTrue(MailboxConnection.objects.filter(pk=connection.pk).exists())
        response = self.client.get(f"/mail/subjects/{self.subject.pk}/connections/")
        self.assertEqual(response.status_code, 302)

    def test_connect_page_offers_presets_and_explains_app_passwords(self):
        response = self.client.get(self.base + "connect/")
        self.assertContains(response, 'value="imap.gmail.com"')  # preset from the address
        self.assertContains(response, 'value="smtp.gmail.com"')
        self.assertContains(response, "myaccount.google.com/apppasswords")
        self.assertContains(response, "?provider=fastmail")
        self.assertContains(response, "Test connection")
        self.assertContains(response, "mail/mail.css")
        self.assertNotContains(response, "style=")
        self.assertNotContains(response, "<script>")
        response = self.client.get(self.base + "connect/?provider=posteo")
        self.assertContains(response, 'value="posteo.de"')

    def test_microsoft_address_is_warned(self):
        self.mailbox.email = "alex@outlook.com"
        self.mailbox.save()
        response = self.client.get(self.base + "connect/")
        self.assertContains(response, "Outlook.com and Microsoft 365 generally require OAuth for IMAP")

    def test_save_connects_the_mailbox_live_with_an_encrypted_password(self):
        response = self.client.post(self.base + "connect/", self.form(action="save"))
        self.assertRedirects(response, self.base + "connection/")
        connection = MailboxConnection.objects.get()
        self.assertEqual((connection.smtp_port, connection.smtp_security), (465, "ssl"))
        self.assertEqual(connection.password(), PASSWORD)
        self.assertNotIn(PASSWORD, connection.password_encrypted)
        self.mailbox.refresh_from_db()
        self.assertEqual(self.mailbox.mode, Mailbox.Mode.LIVE)
        page = self.client.get(self.base + "connection/")
        self.assertNotContains(page, PASSWORD)
        self.assertContains(page, "Scan now")
        self.assertContains(page, "Off: the mailbox is scanned only")

    def test_test_button_logs_in_and_saves_nothing(self):
        server = FakeIMAPServer({"INBOX": Folder(1)}, username="alex@gmail.com")
        with server.installed(), FakeSMTP.installed():
            response = self.client.post(self.base + "connect/", self.form(action="test", smtp="587"))
        self.assertContains(response, "IMAP: logged in and out.")
        self.assertContains(response, "SMTP: logged in and out.")
        self.assertFalse(MailboxConnection.objects.exists())
        self.assertEqual([c.split()[0] for c in server.commands if c != "CAPABILITY"], ["LOGIN", "LOGOUT"])
        self.assertEqual(FakeSMTP.instances[0].calls, ["STARTTLS", "LOGIN alex@gmail.com", "QUIT"])
        self.assertNotContains(response, PASSWORD)

    def test_test_button_shows_the_refusal(self):
        server = FakeIMAPServer({"INBOX": Folder(1)}, username="alex@gmail.com", password="other")
        with server.installed(), FakeSMTP.installed():
            response = self.client.post(self.base + "connect/", self.form(action="test"))
        self.assertContains(response, "use file import instead")
        self.assertContains(response, "Outlook.com and Microsoft 365 generally require OAuth for IMAP")

    def test_new_connection_needs_a_password(self):
        response = self.client.post(self.base + "connect/", self.form(action="save", password=""))
        self.assertContains(response, "Enter the app password.")
        self.assertFalse(MailboxConnection.objects.exists())

    def test_scan_now(self):
        self.connect()
        server = FakeIMAPServer({"INBOX": Folder(4, {1: message(1)})}, username="alex@gmail.com")
        with server.installed():
            response = self.client.post(self.base + "connection/scan/", follow=True)
        self.assertContains(response, "Scanned 1 new message.")
        run = ImportRun.objects.get()
        self.assertEqual((run.source, run.mailbox, run.filename), ("imap", self.mailbox, "INBOX"))

    def test_scan_now_with_a_refused_password(self):
        self.connect()
        server = FakeIMAPServer({"INBOX": Folder(4)}, password="revoked")
        with server.installed():
            response = self.client.post(self.base + "connection/scan/", follow=True)
        self.assertContains(response, "file import")
        self.assertContains(response, "Last problem:")

    def test_scheduled_rescans_toggle(self):
        connection = self.connect()
        self.client.post(self.base + "connection/rescans/", {"enabled": "1"})
        connection.refresh_from_db()
        self.assertTrue(connection.scheduled_rescans)
        self.client.post(self.base + "connection/rescans/", {"enabled": "0"})
        connection.refresh_from_db()
        self.assertFalse(connection.scheduled_rescans)

    def test_disconnect(self):
        self.connect()
        response = self.client.post(self.base + "connection/disconnect/")
        self.assertRedirects(response, f"/mail/subjects/{self.subject.pk}/connections/")
        self.assertFalse(MailboxConnection.objects.exists())
        self.mailbox.refresh_from_db()
        self.assertEqual(self.mailbox.mode, Mailbox.Mode.IMPORT)

    def test_connections_list_and_status_without_connection(self):
        response = self.client.get(f"/mail/subjects/{self.subject.pk}/connections/")
        self.assertContains(response, "alex@gmail.com")
        self.assertContains(response, self.base + "connect/")
        self.assertContains(response, "Outlook.com and Microsoft 365 generally require OAuth")
        self.assertRedirects(self.client.get(self.base + "connection/"), self.base + "connect/")

    def test_other_subjects_mailbox_is_not_found(self):
        other = make_subject(name="Other", email="other@example.org")
        mailbox = other.mailboxes.get()
        url = f"/mail/subjects/{self.subject.pk}/mailboxes/{mailbox.pk}/connect/"
        self.assertEqual(self.client.get(url).status_code, 404)
