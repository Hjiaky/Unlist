# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.apps import AppConfig


class MailConfig(AppConfig):
    name = "unlist.mail"
    label = "mail"

    def ready(self):
        from unlist.mail import hooks, jobs  # noqa: F401  (jobs registers itself with the scheduler)

        hooks.register()
