# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from unlist import crypto
from unlist.backup import hooks, service


def run_migrations():
    """An archive from an older release has an older schema."""
    connections.close_all()
    call_command("migrate", interactive=False, verbosity=0)


class Command(BaseCommand):
    help = "Restore a backup archive into an empty instance (new data directory), then migrate and check it."

    def add_arguments(self, parser):
        parser.add_argument("archive", help="A file written by `manage.py backup`.")

    def handle(self, *args, **options):
        archive = Path(options["archive"])
        connections.close_all()
        try:
            manifest = service.restore_backup(archive)
        except service.BackupError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"Restored {len(manifest['files'])} files from {archive.name}.")

        run_migrations()
        self.stdout.write("Database is up to date.")

        problems = service.check_restored(manifest)
        for check in hooks.integrity_checks:
            problems.extend(check(service.data_dir()))
        for problem in problems:
            self.stderr.write(f"Problem: {problem}")

        self.report_key()
        self.stdout.write("Restart Unlist so it picks up the restored signing secret.")
        if problems:
            raise CommandError("The restore finished, but the checks above found problems.")

    def report_key(self):
        reenter = "Mailbox and LLM credentials must be entered again in the settings."
        try:
            crypto.reset_cache()
            crypto._fernet()
            tokens = [token for source in hooks.stored_secrets for token in source()]
            for token in tokens:
                crypto.decrypt(token)
        except crypto.MissingKey:
            self.stdout.write(
                "No encryption key is available, so stored credentials cannot be read. "
                f"Set UNLIST_KEY or provide the key file you kept. Without it: {reenter}"
            )
        except crypto.WrongKey:
            self.stdout.write(f"The encryption key here does not match the one used for this backup. {reenter}")
