# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.apps import AppConfig


class StatsConfig(AppConfig):
    name = "unlist.stats"
    label = "stats"

    def ready(self):
        from unlist.stats import jobs  # noqa: F401  (jobs registers itself with the scheduler)
