# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Attachment files: ``<DATA_DIR>/attachments/<subject_id>/<case_id>/<id>-<name>``.

Files are plain files in the data directory (Tao rule 3), so a backup of that directory holds
them. The database row keeps the path relative to the data directory, the size and the SHA-256,
so a restore can check every file (``integrity_check``).
"""

import hashlib
import re
import secrets
import shutil
import sqlite3
from pathlib import Path

from unlist import paths

ATTACHMENTS = "attachments"
DB_NAME = "unlist.sqlite3"  # as in settings.DATABASES and unlist.backup.service
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _data_dir() -> Path:
    return Path(paths.DATA_DIR)


def subject_folder(subject_id: int, data_dir: Path | None = None) -> Path:
    return (data_dir or _data_dir()) / ATTACHMENTS / str(int(subject_id))


def safe_name(name: str) -> str:
    """A file name without folders or odd characters, never empty, at most 100 characters."""
    name = Path((name or "").replace("\\", "/")).name
    name = _UNSAFE.sub("_", name).strip("._") or "file"
    return name[-100:]


def store_attachment(case, name: str, chunks, *, content_type: str = "", event=None):
    """Write ``chunks`` (an iterable of bytes, or bytes) to the Case's folder and record it."""
    from unlist.cases.models import Attachment

    if isinstance(chunks, bytes | bytearray):
        chunks = [bytes(chunks)]
    relative = Path(ATTACHMENTS) / str(case.subject_id) / str(case.id) / f"{secrets.token_hex(4)}-{safe_name(name)}"
    target = _data_dir() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with open(target, "xb") as handle:
        for chunk in chunks:
            digest.update(chunk)
            size += len(chunk)
            handle.write(chunk)
    return Attachment.objects.create(
        case=case,
        event=event,
        original_name=(name or "file")[:255],
        stored_path=relative.as_posix(),
        sha256=digest.hexdigest(),
        size=size,
        content_type=(content_type or "")[:200],
    )


def store_upload(case, uploaded_file, *, event=None):
    """Store a Django ``UploadedFile``."""
    return store_attachment(
        case, uploaded_file.name, uploaded_file.chunks(), content_type=uploaded_file.content_type or "", event=event
    )


def attachment_path(attachment, data_dir: Path | None = None) -> Path:
    return (data_dir or _data_dir()) / attachment.stored_path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def delete_subject_attachments(subject) -> None:
    """``subjects.deletion.before_delete`` hook: remove the Subject's whole attachment folder."""
    shutil.rmtree(subject_folder(subject.pk), ignore_errors=True)


def attachment_problems(rows, data_dir: Path) -> list[str]:
    """One sentence per attachment whose file is missing or changed.

    ``rows`` are ``(original_name, stored_path, sha256, case_reference)`` tuples.
    """
    problems = []
    for original_name, stored_path, sha256, reference in rows:
        path = Path(data_dir) / stored_path
        label = f'Attachment "{original_name}" of Case {reference}'
        if not path.is_file():
            problems.append(f"{label} is missing from {ATTACHMENTS}/ ({stored_path}).")
        elif file_sha256(path) != sha256:
            problems.append(f"{label} has changed: its SHA-256 no longer matches ({stored_path}).")
    return problems


def integrity_check(data_dir: Path) -> list[str]:
    """``backup.hooks.integrity_checks`` hook: every Attachment file exists and matches its hash.

    Reads the restored database file in ``data_dir`` directly (read-only), so it checks exactly
    what was restored, whatever database the running process has open.
    """
    database = Path(data_dir) / DB_NAME
    if not database.is_file():
        return []  # the restore's own checks report a missing database
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT a.original_name, a.stored_path, a.sha256, c.reference "
            "FROM cases_attachment a JOIN cases_case c ON c.id = a.case_id ORDER BY a.id"
        ).fetchall()
    except sqlite3.OperationalError:
        return []  # no Cases tables (yet): nothing to check
    finally:
        connection.close()
    return attachment_problems(rows, data_dir)
