# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from unlist.backup import service


class Command(BaseCommand):
    help = "Write one backup archive of this instance (database, attachments, signing secret). Unlist can keep running."

    def add_arguments(self, parser):
        parser.add_argument("--output", metavar="DIR", help="Folder for the archive (default: DATA_DIR/backups).")

    def handle(self, *args, **options):
        try:
            archive = service.create_backup(Path(options["output"]) if options["output"] else None)
        except service.BackupError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(str(archive))
        self.stderr.write(
            "This archive holds the household's data and replies: store it encrypted and private.\n"
            "The encryption key is NOT inside it: keep the key file separately."
        )
