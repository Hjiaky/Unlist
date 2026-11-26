# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Connecting and disconnecting a live mailbox, and testing its login."""

from django.db import transaction

from unlist.mail import imap, smtp
from unlist.mail.models import MailboxConnection
from unlist.subjects.models import Mailbox

# Changing one of these means another mailbox: its UIDs mean nothing here any more.
IDENTITY_FIELDS = ("imap_host", "imap_port", "username")


def save_connection(mailbox, settings, password=""):
    """Create or update the mailbox's connection and switch the mailbox to live mode.

    ``password`` may be empty when a connection with a stored password exists. Raises
    ``crypto.MissingKey`` when no encryption key is set up.
    """
    with transaction.atomic():
        connection = MailboxConnection.objects.filter(mailbox=mailbox).first() or MailboxConnection(mailbox=mailbox)
        changed = connection.pk is not None and any(
            getattr(connection, field) != settings[field] for field in IDENTITY_FIELDS
        )
        for field, value in settings.items():
            setattr(connection, field, value)
        if password:
            connection.set_password(password)
        if changed:
            connection.folder, connection.uidvalidity, connection.last_uid = "", None, 0
        connection.last_error = ""
        connection.save()
        if mailbox.mode != Mailbox.Mode.LIVE:
            mailbox.mode = Mailbox.Mode.LIVE
            mailbox.save(update_fields=["mode"])
    return connection


def disconnect(connection):
    """Forget the connection (and its password) and set the mailbox back to import-only."""
    mailbox = connection.mailbox
    with transaction.atomic():
        connection.delete()
        mailbox.mode = Mailbox.Mode.IMPORT
        mailbox.save(update_fields=["mode"])


def test_connection(connection, password=None):
    """Log in to IMAP and SMTP and out again; nothing is read or sent.

    Returns a list of (what, ok, message). A saved connection's ``last_error`` is updated.
    """
    results = []
    for what, check in (("IMAP", imap.test_login), ("SMTP", smtp.test_login)):
        try:
            check(connection, password)
        except imap.ConnectionProblem as error:
            results.append((what, False, str(error)))
        else:
            results.append((what, True, f"{what}: logged in and out."))
    if connection.pk is not None:
        problems = [message for _, ok, message in results if not ok]
        connection.record_error(" ".join(problems))
    return results
