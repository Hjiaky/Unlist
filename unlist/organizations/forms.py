# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from urllib.parse import urlsplit

from django import forms

from unlist.organizations.merge import OVERRIDABLE
from unlist.organizations.services import OverrideError, parse_override


class OverrideForm(forms.Form):
    field = forms.ChoiceField(choices=[(name, name) for name in OVERRIDABLE])
    value = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Lists and domains: one per line. Yes/no fields: yes or no. Empty clears the value.",
    )
    note = forms.CharField(max_length=500, required=False)

    def clean(self):
        cleaned = super().clean()
        if "field" in cleaned:
            try:
                cleaned["parsed"] = parse_override(cleaned["field"], cleaned.get("value", ""))
            except OverrideError as error:
                self.add_error("value", str(error))
        return cleaned


class AddListForm(forms.Form):
    url = forms.URLField(max_length=500, label="List URL")

    def clean_url(self):
        url = self.cleaned_data["url"]
        if urlsplit(url).scheme not in ("http", "https"):
            raise forms.ValidationError("Enter an http or https address.")
        return url
