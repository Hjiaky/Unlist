# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from urllib.parse import urlsplit

from django import forms

from unlist.llm import endpoint
from unlist.llm.jobs import SORTABLE
from unlist.mail.models import Evidence

DETECT, LOCAL, REMOTE = "detect", "local", "remote"


class SettingsForm(forms.Form):
    enabled = forms.BooleanField(required=False, label="Use the LLM")
    base_url = forms.CharField(
        max_length=500,
        required=False,
        label="Endpoint address",
        help_text="OpenAI-compatible base address, for example http://localhost:11434/v1 for Ollama "
        "or http://localhost:8080/v1 for llama.cpp's server.",
    )
    model = forms.CharField(max_length=200, required=False, label="Model name", help_text="For example llama3.1.")
    api_key = forms.CharField(
        required=False,
        label="API key",
        widget=forms.PasswordInput(render_value=False),
        help_text="Optional; local models need none. Leave empty to keep the stored key. Stored encrypted.",
    )
    forget_api_key = forms.BooleanField(required=False, label="Forget the stored API key")
    location = forms.ChoiceField(
        choices=[
            (DETECT, "Detect from the address"),
            (LOCAL, "Local: a model you run yourself (this machine or your own network)"),
            (REMOTE, "Remote: someone else's service"),
        ],
        widget=forms.RadioSelect,
        label="Local or remote",
    )

    def __init__(self, *args, settings=None, **kwargs):
        if settings is not None and "initial" not in kwargs:
            location = DETECT if settings.is_remote is None else (REMOTE if settings.is_remote else LOCAL)
            kwargs["initial"] = {
                "enabled": settings.enabled,
                "base_url": settings.base_url,
                "model": settings.model,
                "location": location,
            }
        super().__init__(*args, **kwargs)

    def clean_base_url(self):
        url = self.cleaned_data["base_url"].strip()
        if url and (urlsplit(url).scheme not in ("http", "https") or not endpoint.host_of(url)):
            raise forms.ValidationError("Enter an http:// or https:// address.")
        return url

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("enabled"):
            if not cleaned.get("base_url"):
                self.add_error("base_url", "Enter the endpoint address to use the LLM.")
            if not cleaned.get("model", "").strip():
                self.add_error("model", "Enter the model name to use the LLM.")
        return cleaned

    def apply(self, settings):
        """Copy the cleaned values onto ``settings`` and save. A new host needs the notice accepted again."""
        data = self.cleaned_data
        old_host = settings.host
        settings.enabled = data["enabled"]
        settings.base_url = data["base_url"]
        settings.model = data["model"].strip()
        settings.is_remote = {DETECT: None, LOCAL: False, REMOTE: True}[data["location"]]
        if data["forget_api_key"]:
            settings.set_api_key("")
        elif data["api_key"]:
            settings.set_api_key(data["api_key"].strip())
        if settings.host != old_host:
            settings.remote_notice_accepted_at = None
        settings.save()
        return settings


class EvidenceForm(forms.Form):
    evidence = forms.ChoiceField(choices=[(kind, Evidence(kind).label) for kind in SORTABLE])


class DraftProposalForm(forms.Form):
    subject_line = forms.CharField(max_length=500, widget=forms.TextInput(attrs={"size": 80}))
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 24, "cols": 80}))


class ContactUrlForm(forms.Form):
    url = forms.CharField(max_length=1000, label="Privacy-policy address", help_text="The page's https:// address.")

    def clean_url(self):
        url = self.cleaned_data["url"].strip()
        if urlsplit(url).scheme not in ("http", "https") or not endpoint.host_of(url):
            raise forms.ValidationError("Enter an http:// or https:// address.")
        return url


class ContactProposalForm(forms.Form):
    email = forms.CharField(max_length=300, required=False, label="Email address")
    address = forms.CharField(
        max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 4}), label="Postal address"
    )
    webform = forms.CharField(max_length=1000, required=False, label="Web form")
    url = forms.CharField(max_length=1000, widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(name, "").strip() for name in ("email", "address", "webform")):
            raise forms.ValidationError("Keep at least one contact, or go back without saving.")
        return cleaned
