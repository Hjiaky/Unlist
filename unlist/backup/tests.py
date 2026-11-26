# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Django's test database is in memory, so backup and restore are tested against small
standalone SQLite files in temporary data directories: `unlist.paths.DATA_DIR` is patched
and everything in `unlist.backup.service` derives its paths from it at call time."""

import io
import os
import sqlite3
import stat
import tarfile
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from unlist import crypto, paths
from unlist.backup import hooks, service
from unlist.backup.management.commands import restore as restore_command

ATTACHMENTS = {
    "attachments/1/reply.eml": b"From: a@example.org\n\nHello\n",
    "attachments/2/deep/scan.bin": bytes(range(256)) * 40,
}


@contextmanager
def data_dir_at(path):
    with mock.patch.object(paths, "DATA_DIR", Path(path)):
        yield Path(path)


def make_instance(root, rows=(("Ada",), ("Grace",)), attachments=ATTACHMENTS):
    """A data directory with a real WAL-mode SQLite file, as Unlist keeps it."""
    root = Path(root)
    (root / "attachments").mkdir(parents=True, exist_ok=True)
    (root / "django_secret").write_text("signing-secret")
    for name, content in attachments.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(content)
    con = sqlite3.connect(root / service.DB_NAME)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE django_migrations (id INTEGER PRIMARY KEY, app TEXT, name TEXT, applied TEXT)")
    con.execute("INSERT INTO django_migrations (app, name, applied) VALUES ('core', '0001_initial', 'now')")
    con.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT)")
    con.executemany("INSERT INTO people (name) VALUES (?)", rows)
    con.commit()
    return con  # left open: Unlist keeps running during a backup


def rows_of(root):
    con = sqlite3.connect(Path(root) / service.DB_NAME)
    try:
        return con.execute("SELECT id, name FROM people ORDER BY id").fetchall()
    finally:
        con.close()


def attachment_files(root):
    base = Path(root)
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in (base / "attachments").rglob("*") if p.is_file()}


def rewrite_archive(source, target, edit):
    """Copy an archive, letting `edit(members: dict[name, bytes])` change its files."""
    with tarfile.open(source) as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isreg()}
    edit(members)
    with tarfile.open(target, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return target


class TempDirTestCase(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.source = self.tmp / "source"
        self.target = self.tmp / "target"


class BackupRestoreTests(TempDirTestCase):
    def backup_source(self, **kwargs):
        self.live = make_instance(self.source)
        self.addCleanup(self.live.close)
        with data_dir_at(self.source):
            return service.create_backup(**kwargs)

    def test_round_trip_gives_identical_rows_and_attachments(self):
        archive = self.backup_source()
        self.live.execute("INSERT INTO people (name) VALUES ('later')")  # after the backup
        self.live.commit()
        with data_dir_at(self.target):
            manifest = service.restore_backup(archive)
            self.assertEqual(service.check_restored(manifest), [])
        self.assertEqual(rows_of(self.target), [(1, "Ada"), (2, "Grace")])
        self.assertEqual(attachment_files(self.target), ATTACHMENTS)
        self.assertEqual((self.target / "django_secret").read_text(), "signing-secret")
        self.assertFalse((self.target / "unlist.sqlite3-wal").exists())

    def test_manifest_contents(self):
        archive = self.backup_source(now=datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC))
        self.assertEqual(archive.name, "unlist-backup-20260304-050607.tar.gz")
        with data_dir_at(self.source):
            manifest = service.read_manifest(archive)
        self.assertEqual(manifest["created_at"], "2026-03-04T05:06:07+00:00")
        self.assertEqual(manifest["migrations"], {"core": ["0001_initial"]})
        self.assertTrue(manifest["unlist_version"])
        self.assertEqual(
            {f["path"] for f in manifest["files"]},
            {"unlist.sqlite3", "django_secret", *ATTACHMENTS},
        )
        for entry in manifest["files"]:
            self.assertEqual(len(entry["sha256"]), 64)

    def test_archive_is_private_and_defaults_to_the_backups_folder(self):
        archive = self.backup_source()
        self.assertEqual(archive.parent, self.source / "backups")
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in archive.parent.iterdir()], [archive.name])  # no temp leftovers

    def test_output_option_and_earlier_backups_are_not_included(self):
        self.backup_source()
        elsewhere = self.tmp / "elsewhere"
        with data_dir_at(self.source):
            second = service.create_backup(output=elsewhere)
        self.assertEqual(second.parent, elsewhere)
        with tarfile.open(second) as tar:
            self.assertFalse([n for n in tar.getnames() if "backup" in n.replace("manifest", "")])

    def test_two_backups_in_one_second_do_not_overwrite_each_other(self):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        first = self.backup_source(now=now)
        with data_dir_at(self.source):
            second = service.create_backup(now=now)
            self.assertNotEqual(first, second)
            self.assertEqual(service.last_backup()[1], second)

    def test_key_file_is_never_in_the_archive(self):
        key = crypto.generate_key()
        (self.source / "attachments").mkdir(parents=True)
        key_file = self.tmp / "key" / "unlist.key"
        key_file.parent.mkdir()
        key_file.write_text(key)
        with mock.patch.object(paths, "KEY_FILE", key_file), mock.patch.dict(os.environ, {"UNLIST_KEY": key}):
            archive = self.backup_source()
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                self.assertNotIn("key", member.name.lower().replace("keep", ""))
                if member.isreg():
                    self.assertNotIn(key.encode(), tar.extractfile(member).read())

    def test_symlinks_in_attachments_are_not_followed(self):
        self.backup_source()
        (self.tmp / "outside.txt").write_text("outside")
        os.symlink(self.tmp / "outside.txt", self.source / "attachments" / "link")
        with data_dir_at(self.source):
            archive = service.create_backup()
        with tarfile.open(archive) as tar:
            self.assertNotIn("attachments/link", tar.getnames())

    def test_backup_while_the_database_is_being_written(self):
        archive_holder = {}
        self.live = make_instance(self.source)
        self.addCleanup(self.live.close)
        self.live.execute("BEGIN")
        self.live.execute("INSERT INTO people (name) VALUES ('uncommitted')")
        with data_dir_at(self.source):
            archive_holder["a"] = service.create_backup()
        self.live.rollback()
        with data_dir_at(self.target):
            service.restore_backup(archive_holder["a"])
        self.assertEqual([name for _, name in rows_of(self.target)], ["Ada", "Grace"])  # consistent snapshot


class RestoreRefusalTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.live = make_instance(self.source)
        self.addCleanup(self.live.close)
        with data_dir_at(self.source):
            self.archive = service.create_backup()

    def assert_untouched(self):
        self.assertFalse((self.target / "django_secret").exists() and (self.target / "attachments").exists())

    def test_refuses_a_database_with_rows(self):
        make_instance(self.target, rows=(("Existing",),), attachments={}).close()
        with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "not empty.*people"):
            service.restore_backup(self.archive)
        self.assertEqual(rows_of(self.target), [(1, "Existing")])

    def test_refuses_an_operator_account(self):
        (self.target).mkdir()
        con = sqlite3.connect(self.target / service.DB_NAME)
        con.execute("CREATE TABLE auth_user (id INTEGER PRIMARY KEY, username TEXT)")
        con.execute("INSERT INTO auth_user (username) VALUES ('operator')")
        con.commit()
        con.close()
        with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "auth_user"):
            service.restore_backup(self.archive)

    def test_refuses_existing_attachments(self):
        (self.target / "attachments").mkdir(parents=True)
        (self.target / "attachments" / "x").write_bytes(b"x")
        with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "attachments"):
            service.restore_backup(self.archive)

    def test_a_migrated_but_empty_instance_is_empty(self):
        self.target.mkdir()
        con = sqlite3.connect(self.target / service.DB_NAME)
        con.execute("CREATE TABLE django_migrations (id INTEGER PRIMARY KEY, app TEXT)")
        con.execute("INSERT INTO django_migrations (app) VALUES ('core')")
        con.execute("CREATE TABLE django_content_type (id INTEGER PRIMARY KEY, app_label TEXT)")
        con.execute("INSERT INTO django_content_type (app_label) VALUES ('auth')")
        con.execute("CREATE TABLE auth_user (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()
        (self.target / "attachments").mkdir()
        with data_dir_at(self.target):
            service.restore_backup(self.archive)
        self.assertEqual(len(rows_of(self.target)), 2)

    def test_tampered_archive_is_rejected_before_anything_is_written(self):
        tampered = rewrite_archive(
            self.archive,
            self.tmp / "tampered.tar.gz",
            lambda members: members.update({"attachments/1/reply.eml": b"changed"}),
        )
        with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "Checksum mismatch"):
            service.restore_backup(tampered)
        self.assertFalse(self.target.exists())

    def test_extra_file_not_in_the_manifest_is_rejected(self):
        extra = rewrite_archive(self.archive, self.tmp / "extra.tar.gz", lambda m: m.update({"attachments/evil": b"x"}))
        with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "manifest"):
            service.restore_backup(extra)
        self.assertFalse(self.target.exists())

    def test_path_traversal_members_are_rejected(self):
        for bad in ["../escape.txt", "/etc/escape.txt", "attachments/../../escape.txt", "other/file"]:
            archive = rewrite_archive(self.archive, self.tmp / "bad.tar.gz", lambda m, bad=bad: m.update({bad: b"x"}))
            with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "unsafe"):
                service.restore_backup(archive)
            self.assertFalse(self.target.exists())
            self.assertFalse((self.tmp / "escape.txt").exists())

    def test_traversal_listed_only_in_the_manifest_is_rejected(self):
        import json

        def edit(members):
            manifest = json.loads(members["manifest.json"])
            manifest["files"].append({"path": "../escape.txt", "sha256": "0" * 64, "size": 0})
            members["manifest.json"] = json.dumps(manifest).encode()

        archive = rewrite_archive(self.archive, self.tmp / "bad.tar.gz", edit)
        with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "unsafe"):
            service.restore_backup(archive)

    def test_symlink_and_device_members_are_rejected(self):
        for kind in (tarfile.SYMTYPE, tarfile.CHRTYPE):
            path = self.tmp / "special.tar.gz"
            with tarfile.open(path, "w:gz") as tar:
                info = tarfile.TarInfo("attachments/x")
                info.type = kind
                info.linkname = "/etc/passwd"
                tar.addfile(info)
            with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "link or special"):
                service.restore_backup(path)

    def test_a_file_that_is_not_a_backup(self):
        junk = self.tmp / "junk.tar.gz"
        junk.write_bytes(b"not an archive")
        with data_dir_at(self.target), self.assertRaisesRegex(service.BackupError, "Cannot read"):
            service.restore_backup(junk)


class RestoreCommandTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.live = make_instance(self.source)
        self.addCleanup(self.live.close)
        with data_dir_at(self.source):
            self.archive = service.create_backup()
        patcher = mock.patch.object(restore_command, "run_migrations")
        self.migrate = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(crypto.reset_cache)

    def run_restore(self, archive=None):
        out, err = io.StringIO(), io.StringIO()
        with data_dir_at(self.target):
            call_command("restore", str(archive or self.archive), stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_restore_migrates_and_reports_a_missing_key(self):
        env = {k: v for k, v in os.environ.items() if k != "UNLIST_KEY"}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(crypto, "KEY_FILE", self.tmp / "none.key"),
        ):
            crypto.reset_cache()
            out, _ = self.run_restore()
        self.migrate.assert_called_once()
        self.assertIn("must be entered again", out)
        self.assertEqual(rows_of(self.target), [(1, "Ada"), (2, "Grace")])

    def test_restore_reports_a_key_that_does_not_match(self):
        with mock.patch.dict(os.environ, {"UNLIST_KEY": crypto.generate_key()}):
            crypto.reset_cache()
            token = crypto.encrypt("secret")
        crypto.reset_cache()
        source = mock.Mock(return_value=[token])
        with (
            mock.patch.dict(os.environ, {"UNLIST_KEY": crypto.generate_key()}),
            mock.patch.object(hooks, "stored_secrets", [source]),
        ):
            out, _ = self.run_restore()
        self.assertIn("does not match", out)
        self.assertIn("entered again", out)

    def test_restore_with_the_right_key_says_nothing_about_credentials(self):
        key = crypto.generate_key()
        with mock.patch.dict(os.environ, {"UNLIST_KEY": key}):
            crypto.reset_cache()
            token = crypto.encrypt("secret")
            with mock.patch.object(hooks, "stored_secrets", [lambda: [token]]):
                out, _ = self.run_restore()
        self.assertNotIn("entered again", out)

    def test_integrity_hooks_are_called_and_problems_reported(self):
        check = mock.Mock(return_value=["Attachment 7 is missing."])
        with mock.patch.object(hooks, "integrity_checks", [check]), self.assertRaises(CommandError):
            out, err = io.StringIO(), io.StringIO()
            with data_dir_at(self.target), mock.patch.dict(os.environ, {"UNLIST_KEY": crypto.generate_key()}):
                crypto.reset_cache()
                call_command("restore", str(self.archive), stdout=out, stderr=err)
        check.assert_called_once_with(self.target)

    def test_restore_command_refuses_a_non_empty_instance(self):
        make_instance(self.target, attachments={}).close()
        with self.assertRaisesRegex(CommandError, "not empty"):
            self.run_restore()
        self.migrate.assert_not_called()


class BackupCommandTests(TempDirTestCase):
    def test_backup_command_writes_to_output(self):
        live = make_instance(self.source)
        self.addCleanup(live.close)
        out = io.StringIO()
        with data_dir_at(self.source):
            call_command("backup", output=str(self.tmp / "out"), stdout=out, stderr=io.StringIO())
        written = Path(out.getvalue().strip())
        self.assertEqual(written.parent, self.tmp / "out")
        self.assertTrue(tarfile.is_tarfile(written))

    def test_backup_command_without_a_database(self):
        self.source.mkdir()
        with data_dir_at(self.source), self.assertRaisesRegex(CommandError, "nothing to back up"):
            call_command("backup", stdout=io.StringIO(), stderr=io.StringIO())


class BackupViewTests(TempDirTestCase, TestCase):
    def setUp(self):
        TempDirTestCase.setUp(self)
        self.live = make_instance(self.source)
        self.addCleanup(self.live.close)
        patcher = mock.patch.object(paths, "DATA_DIR", self.source)
        patcher.start()
        self.addCleanup(patcher.stop)
        get_user_model().objects.create_user("operator", password="a long enough passphrase")

    def login(self):
        self.client.login(username="operator", password="a long enough passphrase")

    def test_pages_require_login(self):
        self.assertEqual(self.client.get("/backup/").status_code, 302)
        self.assertEqual(self.client.post("/backup/download/").status_code, 302)
        self.assertFalse((self.source / "backups").exists())

    def test_page_shows_last_backup_and_the_key_warning(self):
        self.login()
        page = self.client.get("/backup/").content.decode()
        self.assertIn("No backup has been made", page)
        self.assertIn("Download backup", page)
        self.assertIn("encryption key is not inside", page)
        self.assertNotIn("style=", page)
        self.assertNotRegex(page, r"<script(?![^>]*\bsrc=)")
        service.create_backup(now=datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC))
        self.assertIn("6 May 2026, 07:08", self.client.get("/backup/").content.decode())

    def test_download_returns_an_archive_and_keeps_a_copy(self):
        self.login()
        response = self.client.post("/backup/download/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        body = b"".join(response.streaming_content)
        kept = list((self.source / "backups").glob("unlist-backup-*.tar.gz"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_bytes(), body)
        with tarfile.open(fileobj=io.BytesIO(body)) as tar:
            self.assertIn("manifest.json", tar.getnames())

    def test_download_needs_post(self):
        self.login()
        self.assertEqual(self.client.get("/backup/download/").status_code, 405)
