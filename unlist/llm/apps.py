# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.apps import AppConfig


class LlmConfig(AppConfig):
    name = "unlist.llm"
    label = "llm"
    verbose_name = "Optional LLM"

    def ready(self):
        from unlist.llm import hooks

        hooks.register()
