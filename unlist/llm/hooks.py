# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""What the LLM app plugs into other apps' hooks. Registered from ``LlmConfig.ready()``."""

import sqlite3

from unlist.backup import hooks as backup_hooks
from unlist.backup import service as backup_service
from unlist.cases import replies
from unlist.llm import jobs


def api_key_tokens():
    """``backup.hooks.stored_secrets``: the stored (encrypted) LLM API key, if any.

    Reads the database file in the data directory directly (read-only), so a restore checks
    exactly what it restored, whatever database the running process has open.
    """
    database = backup_service.database_path()
    if not database.is_file():
        return []
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT api_key_encrypted FROM llm_llmsettings WHERE api_key_encrypted != ''"
        ).fetchall()
    except sqlite3.OperationalError:
        return []  # no settings table (yet)
    finally:
        connection.close()
    return [token for (token,) in rows]


def register() -> None:
    for registry, hook in (
        (backup_hooks.stored_secrets, api_key_tokens),
        (replies.suggesters, jobs.suggest_reply_outcome),
    ):
        if hook not in registry:
            registry.append(hook)
