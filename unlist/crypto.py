# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Encryption of stored secrets (mailbox app passwords, an LLM key).

Only secrets are encrypted; everything else stays readable in the SQLite file (Tao rule 3).
The key comes from UNLIST_KEY or the key file, never from the data directory, so a copied
database or backup alone does not reveal the secrets (spec section 14).
"""

import os
from functools import cache

from cryptography.fernet import Fernet, InvalidToken

from unlist.paths import KEY_FILE


class MissingKey(RuntimeError):
    """No encryption key is available; stored credentials cannot be read or written."""


class WrongKey(RuntimeError):
    """A stored secret was encrypted with a different key."""


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


@cache
def _fernet() -> Fernet:
    key = os.environ.get("UNLIST_KEY")
    if not key:
        try:
            key = KEY_FILE.read_text().strip()
        except FileNotFoundError:
            raise MissingKey(
                f"No encryption key: set UNLIST_KEY or provide {KEY_FILE}. "
                "Mailbox and LLM credentials must be entered again once a key is set."
            ) from None
    return Fernet(key.encode("ascii"))


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise WrongKey("This secret was stored with a different encryption key.") from None


def reset_cache():
    """For tests and after the key changes."""
    _fernet.cache_clear()
