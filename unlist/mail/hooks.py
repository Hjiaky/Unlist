# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""What the mail app plugs into other apps' hooks. Registered from ``MailConfig.ready()``."""

import sqlite3

from unlist.backup import hooks as backup_hooks
from unlist.backup import service as backup_service
from unlist.cases import sending
from unlist.mail import smtp


def connection_passwords():
    """``backup.hooks.stored_secrets``: every stored (encrypted) mailbox app password.

    Reads the database file in the data directory directly (read-only), so a restore checks
    exactly what it restored, whatever database the running process has open.
    """
    database = backup_service.database_path()
    if not database.is_file():
        return []
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT password_encrypted FROM mail_mailboxconnection WHERE password_encrypted != ''"
        ).fetchall()
    except sqlite3.OperationalError:
        return []  # no connections table (yet)
    finally:
        connection.close()
    return [token for (token,) in rows]


def register() -> None:
    for registry, hook in (
        (backup_hooks.stored_secrets, connection_passwords),
        (sending.live_senders, smtp.send_draft),
    ):
        if hook not in registry:
            registry.append(hook)
