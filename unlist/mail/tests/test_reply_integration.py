# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Replies found in a mail import reach the real reply matching (no mocks)."""

import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

from django.test import TestCase

from unlist.cases import services
from unlist.cases.models import Reply
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.mail.importer import scan_mbox_file
from unlist.mail.models import ImportRun


class ImportedRepliesAreMatchedTests(TestCase):
    def test_a_reply_in_a_later_import_is_matched_to_its_case(self):
        subject = make_subject(email="alex@example.org")
        organization = make_organization(email="privacy@acme.example")
        case = services.open_case(subject, organization, on=DAY0)
        draft = send(case, DAY0)

        reply = EmailMessage()
        reply["From"] = "ACME Privacy <privacy@acme.example>"
        reply["To"] = "alex@example.org"
        reply["Subject"] = f"Re: {draft.subject_line}"
        reply["Date"] = "Mon, 10 Mar 2025 10:00:00 +0000"
        reply["Message-ID"] = "<reply-1@acme.example>"
        reply["In-Reply-To"] = draft.message_id
        reply["References"] = draft.message_id
        reply.set_content("We hold no personal data about you.")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.mbox"
            box = mailbox.mbox(path)
            box.add(reply)
            box.flush()
            box.close()
            run = ImportRun.objects.create(subject=subject, filename="export.mbox")
            scan_mbox_file(run, path)

        stored = Reply.objects.get()
        self.assertEqual(stored.case, case)
        self.assertEqual(stored.matched_by, Reply.MatchedBy.IN_REPLY_TO)
        self.assertEqual(stored.suggested_outcome, "nothing_held")
