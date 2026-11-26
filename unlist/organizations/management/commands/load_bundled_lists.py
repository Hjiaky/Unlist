# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.core.management.base import BaseCommand

from unlist.organizations.loading import load_bundled_lists


class Command(BaseCommand):
    help = (
        "Load the Organization Lists and Supervisory Authorities bundled with this release. "
        "Reads local files only; does nothing when the bundled versions are already loaded."
    )

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Reload even if the versions are unchanged.")

    def handle(self, *args, force=False, **options):
        changed = load_bundled_lists(force=force)
        self.stdout.write("Bundled lists loaded." if changed else "Bundled lists already up to date.")
