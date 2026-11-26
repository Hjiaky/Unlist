# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The optional LLM endpoint (spec section 12): one row of settings, off by default."""

from django.db import models
from django.utils import timezone

from unlist.llm import endpoint


class LlmSettings(models.Model):
    """The one OpenAI-compatible endpoint. Unusable until enabled, and, if remote, until the notice is accepted."""

    enabled = models.BooleanField(default=False)
    base_url = models.CharField(
        max_length=500, blank=True, help_text="For example http://localhost:11434/v1 (Ollama on this machine)."
    )
    model = models.CharField(max_length=200, blank=True, help_text="The model name the endpoint knows, e.g. llama3.1.")
    api_key_encrypted = models.TextField(blank=True, help_text="Optional, encrypted with the instance key.")
    is_remote = models.BooleanField(
        null=True, blank=True, help_text="Set by the Operator; empty means: detect from the address."
    )
    remote_notice_accepted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM settings"
        verbose_name_plural = "LLM settings"

    def __str__(self):
        return f"LLM endpoint {self.base_url or '(none)'}"

    @classmethod
    def load(cls) -> "LlmSettings":
        """The single row; an unsaved, switched-off one until the Operator first saves the settings."""
        return cls.objects.filter(pk=1).first() or cls(pk=1)

    @property
    def host(self) -> str:
        return endpoint.host_of(self.base_url)

    @property
    def detected_remote(self) -> bool:
        return not endpoint.is_local_url(self.base_url)

    @property
    def remote(self) -> bool:
        """The Operator's choice if made, else what the address looks like."""
        return self.detected_remote if self.is_remote is None else self.is_remote

    @property
    def needs_notice(self) -> bool:
        return self.remote and self.remote_notice_accepted_at is None

    @property
    def usable(self) -> bool:
        """Whether any job may contact the endpoint now."""
        return bool(self.enabled and self.base_url and self.model and not self.needs_notice)

    @property
    def source_label(self) -> str:
        """How every suggestion from this endpoint is marked in the UI."""
        if self.remote:
            return f"Suggested by {self.host or 'a remote endpoint'} — a remote, nonfree service"
        return "Suggested by the local model"

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key_encrypted)

    def set_api_key(self, key: str) -> None:
        from unlist import crypto

        self.api_key_encrypted = crypto.encrypt(key) if key else ""

    def api_key(self) -> str:
        """The key, or "". Raises ``crypto.MissingKey`` or ``crypto.WrongKey``."""
        from unlist import crypto

        return crypto.decrypt(self.api_key_encrypted) if self.api_key_encrypted else ""

    def accept_notice(self) -> None:
        self.remote_notice_accepted_at = timezone.now()
        self.save()
