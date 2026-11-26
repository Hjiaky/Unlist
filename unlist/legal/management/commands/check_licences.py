# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.core.management.base import BaseCommand, CommandError

from unlist.legal import licence_check


class Command(BaseCommand):
    help = (
        "Release check: compare the installed runtime packages (those reachable from requirements.txt) "
        "with unlist/legal/licences.json and THIRD-PARTY-NOTICES. Exits non-zero on any gap."
    )

    def handle(self, *args, **options):
        problems, report = licence_check.run()
        for line in report:
            self.stdout.write(line)
        if problems:
            raise CommandError("Licence check failed:\n  " + "\n  ".join(problems))
        self.stdout.write(self.style.SUCCESS(f"{len(report)} runtime packages: licences allowed and noticed."))
