# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Building test messages and a temporary data directory for reply tests."""

import email
import email.policy
import shutil
import tempfile
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path
from unittest import mock

from unlist import paths

ARRIVED = datetime(2025, 3, 10, 12, 0, tzinfo=UTC)  # a week after helpers.DAY0


def make_message(
    *,
    sender="Privacy Team <privacy@acme.example>",
    subject="Your request",
    body="Thank you for your message.",
    html=None,
    date=ARRIVED,
    message_id=None,
    in_reply_to=None,
    references=None,
    authenticated_for=None,
    headers=None,
    attachments=(),
):
    """A message as an mbox import would hand it over (compat32 policy)."""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = "alex@example.org"
    message["Subject"] = subject
    message["Date"] = format_datetime(date)
    message["Message-ID"] = message_id or make_msgid(domain="mail.acme.example")
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    if authenticated_for:
        message["Authentication-Results"] = f"mx.example.org; dkim=pass header.d={authenticated_for}; dmarc=pass"
    for name, value in (headers or {}).items():
        message[name] = value
    if html is not None and body is None:
        message.set_content(html, subtype="html")
    else:
        message.set_content(body)
        if html is not None:
            message.add_alternative(html, subtype="html")
    for name, data, content_type in attachments:
        maintype, subtype = content_type.split("/")
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return email.message_from_bytes(bytes(message), policy=email.policy.compat32)


def delivery_report(original_message_id, original_subject="Access request [Ref U-XXXX]", action="failed"):
    """A delivery status notification (RFC 3464) returning one of the Subject's messages."""
    raw = f"""From: Mail Delivery System <MAILER-DAEMON@mail.example.org>
To: alex@example.org
Subject: Undelivered Mail Returned to Sender
Date: {format_datetime(ARRIVED)}
Message-ID: <dsn-{action}@mail.example.org>
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset=utf-8

This is the mail system. Your message could not be delivered to privacy@acme.example.

--BOUNDARY
Content-Type: message/delivery-status

Reporting-MTA: dns; mail.example.org

Final-Recipient: rfc822; privacy@acme.example
Action: {action}
Status: 5.1.1

--BOUNDARY
Content-Type: message/rfc822

From: Alex Example <alex@example.org>
To: privacy@acme.example
Subject: {original_subject}
Message-ID: {original_message_id}

The request text.

--BOUNDARY--
"""
    return email.message_from_bytes(raw.encode(), policy=email.policy.compat32)


class DataDirMixin:
    """Points the data directory at a temporary directory for the test."""

    def setUp(self):
        super().setUp()
        self.data_dir = Path(tempfile.mkdtemp())
        patcher = mock.patch.object(paths, "DATA_DIR", self.data_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.data_dir, True)

    def stored_files(self):
        return sorted(path for path in self.data_dir.rglob("*") if path.is_file())
