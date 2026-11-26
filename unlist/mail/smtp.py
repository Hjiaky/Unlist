# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Sending approved drafts over SMTP from a live mailbox (spec section 6).

``send_draft`` is registered in ``unlist.cases.sending.live_senders`` from ``MailConfig.ready()``.
``services.approve`` is its only caller, right after the Operator approved a draft. It checks
again that the draft is an approved email draft and that the mailbox it is sent from is live
with a connection; anything else is refused and handed over to the Subject.

The sent message is not appended to the Sent folder (Unlist never writes to the mailbox). The
evidence is what Unlist already keeps: the draft (recipient, subject line, body, approval time,
Message-ID) and the Case's "sent" event with the Message-ID. ``sending.eml_bytes(draft)``
rebuilds exactly the message that was sent.
"""

import logging
import smtplib
import ssl

from unlist.mail.imap import ConnectionProblem, network_problem, stored_password

log = logging.getLogger("unlist.mail")

TIMEOUT = 60

AUTH_FAILED = (
    "The provider refused the user name and app password for sending. Check the app password, or "
    "disconnect so that drafts are handed over for the Subject to send. Outlook.com and Microsoft 365 "
    "generally require OAuth, which Unlist does not use."
)


def open_smtp(connection, password=None):
    """Connect with TLS (SSL/TLS or STARTTLS, certificate verified) and log in. Raises ConnectionProblem."""
    from unlist.mail.models import MailboxConnection

    host, port = connection.smtp_host, connection.smtp_port
    password = stored_password(connection) if password is None else password
    context = ssl.create_default_context()
    try:
        if connection.smtp_security == MailboxConnection.Security.SSL:
            client = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=context)
        else:
            client = smtplib.SMTP(host, port, timeout=TIMEOUT)
            try:
                client.starttls(context=context)
            except BaseException:
                close(client)
                raise
    except (OSError, smtplib.SMTPException) as error:
        raise ConnectionProblem(network_problem(error, "SMTP", host, port)) from error
    try:
        client.login(connection.username, password)
    except smtplib.SMTPAuthenticationError as error:
        close(client)
        raise ConnectionProblem(AUTH_FAILED) from error
    except (OSError, smtplib.SMTPException) as error:
        close(client)
        raise ConnectionProblem(network_problem(error, "SMTP", host, port)) from error
    return client


def close(client):
    try:
        client.quit()
    except Exception:  # already disconnected
        try:
            client.close()
        except Exception:
            log.debug("SMTP close failed", exc_info=True)


def test_login(connection, password=None):
    """Log in and out again, nothing else. Raises ConnectionProblem."""
    close(open_smtp(connection, password))


def live_connection(draft):
    """The connection an approved email draft may be sent through, or None."""
    from unlist.cases import sending
    from unlist.cases.models import Draft
    from unlist.mail.models import MailboxConnection
    from unlist.subjects.models import Mailbox

    if draft.channel != Draft.Channel.EMAIL or draft.status != Draft.Status.APPROVED or draft.approved_at is None:
        return None
    mailbox = sending.mailbox_for(draft)
    if mailbox is None or mailbox.mode != Mailbox.Mode.LIVE:
        return None
    connection = MailboxConnection.objects.filter(mailbox=mailbox).first()
    if connection is None or not connection.smtp_host or not connection.password_encrypted:
        return None
    return connection


def send_draft(draft) -> bool:
    """A ``live_senders`` entry: send an approved email draft over SMTP. True if it was sent.

    Returns False (so the draft is handed over) for anything that is not an approved email
    draft from a live mailbox with a connection, and on any SMTP problem, which is kept on the
    connection for the Operator.
    """
    from unlist.cases import sending

    connection = live_connection(draft)
    if connection is None:
        return False
    message = sending.build_message(draft)
    try:
        client = open_smtp(connection)
        try:
            client.send_message(message, from_addr=draft.sender, to_addrs=[draft.recipient])
        finally:
            close(client)
    except ConnectionProblem as error:
        connection.record_error(f"Sending {draft.case.reference} failed: {error}")
        return False
    except (OSError, smtplib.SMTPException) as error:
        host, port = connection.smtp_host, connection.smtp_port
        connection.record_error(f"Sending {draft.case.reference} failed: {network_problem(error, 'SMTP', host, port)}")
        return False
    return True
