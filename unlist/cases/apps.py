# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.apps import AppConfig


class CasesConfig(AppConfig):
    name = "unlist.cases"
    label = "cases"

    def ready(self):
        from unlist.cases import hooks, jobs, rechecks  # noqa: F401  (jobs and rechecks register scheduler jobs)

        hooks.register()
