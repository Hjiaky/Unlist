# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Backup and restore of an Unlist data directory (spec section 14).

An archive holds exactly: `unlist.sqlite3` (a consistent online copy), `attachments/`,
`django_secret` and `manifest.json`. The encryption key is never part of it, and nothing
outside the data directory is ever read.
"""

import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from unlist import paths

DB_NAME = "unlist.sqlite3"
SECRET_NAME = "django_secret"
ATTACHMENTS = "attachments"
BACKUPS = "backups"
MANIFEST = "manifest.json"
ARCHIVE_RE = re.compile(r"^unlist-backup-(\d{8}-\d{6})(?:-(\d+))?\.tar\.gz$")

# Tables that exist in an instance that was only migrated, or that hold no household data.
BOOKKEEPING_TABLES = {"django_migrations", "django_content_type", "auth_permission", "django_session"}

# Data every instance loads on start from files shipped with the release (the entrypoint runs
# load_bundled_lists and load_breaches before any command). Not the Operator's data: a restore
# replaces it with the archived database anyway. Local overrides, pending contact changes and
# hand-made breach assignments are the Operator's own and still make an instance non-empty.
BUNDLED_DATA_TABLES = {
    "organizations_organizationlist",
    "organizations_listrecord",
    "organizations_organization",
    "organizations_domain",
    "organizations_supervisoryauthority",
    "breaches_breach",
    "breaches_breachcatalogue",
}


class BackupError(Exception):
    """Something the Operator can read and act on; never a traceback."""


def data_dir() -> Path:
    return Path(paths.DATA_DIR)


def database_path() -> Path:
    return data_dir() / DB_NAME


def backups_dir() -> Path:
    return data_dir() / BACKUPS


def unlist_version() -> str:
    try:
        with open(paths.BASE_DIR / "pyproject.toml", "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------- backup


def _copy_database(source: Path, target: Path):
    """Consistent copy while other connections keep reading and writing (SQLite online backup)."""
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=20)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")  # one self-contained file, no -wal sidecar
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()


def _applied_migrations(db_copy: Path) -> dict[str, list[str]]:
    con = sqlite3.connect(db_copy)
    try:
        rows = con.execute("SELECT app, name FROM django_migrations ORDER BY app, id").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        con.close()
    applied: dict[str, list[str]] = {}
    for app, name in rows:
        applied.setdefault(app, []).append(name)
    return applied


def _attachment_files(base: Path):
    """Regular files below `base`, never following symlinks, as (path, archive name)."""
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            full = Path(dirpath) / name
            if full.is_file() and not full.is_symlink():
                yield full, f"{ATTACHMENTS}/{full.relative_to(base).as_posix()}"


def _unique_archive_path(output: Path, now: datetime) -> Path:
    stamp = now.strftime("%Y%m%d-%H%M%S")
    path = output / f"unlist-backup-{stamp}.tar.gz"
    n = 1
    while path.exists():
        n += 1
        path = output / f"unlist-backup-{stamp}-{n}.tar.gz"
    return path


def create_backup(output: Path | None = None, now: datetime | None = None) -> Path:
    """Write one archive and return its path (mode 0600). Unlist can keep running meanwhile."""
    root, db = data_dir(), database_path()
    if not db.exists():
        raise BackupError(f"No database at {db}: nothing to back up.")
    now = now or datetime.now(UTC)
    output = Path(output) if output else backups_dir()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)

    with tempfile.TemporaryDirectory(dir=output, prefix=".backup-") as tmp:
        db_copy = Path(tmp) / DB_NAME
        _copy_database(db, db_copy)
        sources: list[tuple[Path, str]] = [(db_copy, DB_NAME)]
        if (root / SECRET_NAME).is_file():
            sources.append((root / SECRET_NAME, SECRET_NAME))
        sources.extend(_attachment_files(root / ATTACHMENTS))

        manifest = {
            "unlist_version": unlist_version(),
            "created_at": now.isoformat(timespec="seconds"),
            "migrations": _applied_migrations(db_copy),
            "files": [{"path": name, "sha256": sha256_of(src), "size": src.stat().st_size} for src, name in sources],
        }
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")

        final = _unique_archive_path(output, now)
        partial = final.with_name(final.name + ".partial")
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w:gz") as tar:
                info = tarfile.TarInfo(MANIFEST)
                info.size, info.mtime, info.mode = len(manifest_bytes), int(now.timestamp()), 0o600
                tar.addfile(info, io.BytesIO(manifest_bytes))
                for src, name in sources:
                    info = tar.gettarinfo(str(src), arcname=name)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mode = 0o600
                    with open(src, "rb") as f:
                        tar.addfile(info, f)
            os.replace(partial, final)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
    os.chmod(final, 0o600)
    return final


def last_backup() -> tuple[datetime, Path] | None:
    """Newest archive in the backups folder, dated by its file name. No table needed."""
    folder = backups_dir()
    if not folder.is_dir():
        return None
    found = []
    for path in folder.iterdir():
        match = ARCHIVE_RE.match(path.name)
        if match and path.is_file():
            found.append((datetime.strptime(match[1], "%Y%m%d-%H%M%S").replace(tzinfo=UTC), int(match[2] or 1), path))
    if not found:
        return None
    when, _, path = max(found, key=lambda item: item[:2])
    return when, path


# ---------------------------------------------------------------- restore


def _safe_name(name: str) -> str:
    """Return `name` if it can only land inside the data directory as an expected file."""
    pure = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or pure.is_absolute()
        or any(part in ("", ".", "..") for part in name.split("/"))
        or re.match(r"^[A-Za-z]:", name)
    ):
        raise BackupError(f"The archive is unsafe: it contains the path {name!r}.")
    if not (name in (DB_NAME, SECRET_NAME) or (pure.parts[0] == ATTACHMENTS and len(pure.parts) > 1)):
        raise BackupError(f"The archive is unsafe: it contains the unexpected path {name!r}.")
    return name


def read_manifest(archive: Path) -> dict:
    """Open the archive, check its members and every file's SHA-256. Writes nothing."""
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = {}
            for member in tar.getmembers():
                name = member.name
                if member.isdir():
                    if name.rstrip("/") != ATTACHMENTS:
                        _safe_name(name.rstrip("/"))
                    continue
                if not member.isreg():
                    raise BackupError(f"The archive is unsafe: {name!r} is a link or special file.")
                if name != MANIFEST:
                    _safe_name(name)
                if name in members:
                    raise BackupError(f"The archive lists {name!r} twice.")
                members[name] = member
            if MANIFEST not in members:
                raise BackupError("This is not an Unlist backup: manifest.json is missing.")
            try:
                manifest = json.load(tar.extractfile(members[MANIFEST]))
                listed = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
            except (ValueError, KeyError, TypeError):
                raise BackupError("The backup's manifest.json is unreadable.") from None
            for name in listed:
                _safe_name(name)
            if DB_NAME not in listed:
                raise BackupError("The backup holds no database.")
            if set(listed) != set(members) - {MANIFEST}:
                raise BackupError("The archive's files do not match its manifest.")
            for name, expected in listed.items():
                digest = hashlib.sha256()
                f = tar.extractfile(members[name])
                for chunk in iter(lambda f=f: f.read(1 << 20), b""):
                    digest.update(chunk)
                if digest.hexdigest() != expected:
                    raise BackupError(f"Checksum mismatch for {name}: the archive is damaged or was changed.")
            return manifest
    except (tarfile.TarError, OSError, EOFError) as error:
        raise BackupError(f"Cannot read {archive} as an Unlist backup ({error}).") from None


def instance_problems(root: Path, db: Path) -> list[str]:
    """Why this instance is not empty. Empty means: no Operator account, no row in any table
    except Django's own bookkeeping (migrations, content types, permissions, sessions), and
    no file in `attachments/`. Bundled data loaded on every start does not count. A missing
    database file counts as empty."""
    problems = []
    if db.exists():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                if table.startswith("sqlite_") or table in BOOKKEEPING_TABLES or table in BUNDLED_DATA_TABLES:
                    continue
                if con.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone():
                    problems.append(f"table {table} already holds data")
        except sqlite3.DatabaseError as error:
            problems.append(f"the database cannot be read ({error})")
        finally:
            con.close()
    if any(_attachment_files(root / ATTACHMENTS)):
        problems.append("the attachments folder already holds files")
    return problems


def restore_backup(archive: Path) -> dict:
    """Restore into the (empty) instance. Returns the manifest. Raises BackupError and writes
    nothing unless the archive verifies and the instance is empty."""
    root, db = data_dir(), database_path()
    problems = instance_problems(root, db)
    if problems:
        raise BackupError(
            "Restore only works into an empty instance, and this one is not empty: "
            + "; ".join(problems)
            + ". Start a fresh instance (new data directory) and restore there."
        )
    manifest = read_manifest(Path(archive))

    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=root, prefix=".restore-"))
    try:
        with tarfile.open(archive, "r:gz") as tar:
            for entry in manifest["files"]:
                name = entry["path"]
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                src = tar.extractfile(name)
                with open(target, "wb") as out:
                    for chunk in iter(lambda src=src: src.read(1 << 20), b""):
                        digest.update(chunk)
                        out.write(chunk)
                if digest.hexdigest() != entry["sha256"]:
                    raise BackupError(f"Checksum mismatch for {name} while writing.")
        for sidecar in (db, Path(f"{db}-wal"), Path(f"{db}-shm")):
            sidecar.unlink(missing_ok=True)
        os.replace(staging / DB_NAME, db)
        if (staging / SECRET_NAME).exists():
            os.replace(staging / SECRET_NAME, root / SECRET_NAME)
            os.chmod(root / SECRET_NAME, 0o600)
        if (staging / ATTACHMENTS).exists():
            for src, name in _attachment_files(staging / ATTACHMENTS):
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.replace(src, dest)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    (root / ATTACHMENTS).mkdir(exist_ok=True)
    return manifest


def check_restored(manifest: dict) -> list[str]:
    """Every file the manifest lists must exist in the data directory after restore.
    The database is excluded from the hash check because migrations legitimately change it."""
    root = data_dir()
    problems = []
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.is_file():
            problems.append(f"{entry['path']} is missing after restore.")
        elif entry["path"] != DB_NAME and sha256_of(path) != entry["sha256"]:
            problems.append(f"{entry['path']} differs from the backup.")
    return problems
