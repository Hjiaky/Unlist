# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""First-start preparation, run by the container entrypoint before Django starts.

Creates the data directory, Django's signing secret and, if none was supplied, the
encryption key for stored credentials. A fresh instance therefore needs no configuration
at all (Tao rule 2). Nothing here touches the network.
"""

import os
import secrets
import sys

from unlist.paths import DATA_DIR, KEY_FILE


def _write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)


def ensure_state():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "attachments").mkdir(exist_ok=True)

    secret = DATA_DIR / "django_secret"
    if not secret.exists():
        _write_private(secret, secrets.token_urlsafe(50))

    if not os.environ.get("UNLIST_KEY") and not KEY_FILE.exists():
        from unlist.crypto import generate_key

        _write_private(KEY_FILE, generate_key())
        print(
            f"Unlist: generated a new encryption key at {KEY_FILE}.\n"
            "        It protects stored mailbox passwords. It is kept outside the data\n"
            "        directory so backups do not contain it: keep your own copy somewhere safe.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    ensure_state()
