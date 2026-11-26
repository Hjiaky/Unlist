# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Where an instance keeps its state.

Everything lives in one data directory (the SQLite file, stored attachments, Django's
signing secret). The encryption key for stored credentials lives apart from it, so a
backup of the data directory never contains the key (spec section 14).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("UNLIST_DATA_DIR", BASE_DIR / "data"))
KEY_FILE = Path(os.environ.get("UNLIST_KEY_FILE", BASE_DIR / "key" / "unlist.key"))
