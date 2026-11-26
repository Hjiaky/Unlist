# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.core.management.base import BaseCommand

from unlist.breaches import catalogue


class Command(BaseCommand):
    help = (
        "Load the Have I Been Pwned breach catalogue bundled with this release (CC BY 4.0). "
        "Reads a local file only; does nothing when it is already loaded."
    )

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Reload even if nothing changed.")

    def handle(self, *args, force=False, **options):
        count = catalogue.load_bundled(force=force)
        self.stdout.write("Breach catalogue already up to date." if count is None else f"{count} breaches loaded.")
