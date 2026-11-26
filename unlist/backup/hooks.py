# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Places where later apps plug into restore.

Append a function to a list from the app's `AppConfig.ready()`.

* `integrity_checks`: `check(data_dir: Path) -> list[str]`. Called after a restore and its
  migrations, with the data directory. Return one plain sentence per problem found, for
  example an attachment that a row refers to but that is missing from `attachments/`.
* `stored_secrets`: `source() -> Iterable[str]`. Yield the encrypted tokens (as stored by
  `unlist.crypto.encrypt`) of mailbox and LLM credentials, so restore can tell whether the
  encryption key on this machine still opens them.
"""

from collections.abc import Callable, Iterable
from pathlib import Path

integrity_checks: list[Callable[[Path], list[str]]] = []
stored_secrets: list[Callable[[], Iterable[str]]] = []
