# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django import forms


class MboxUploadForm(forms.Form):
    file = forms.FileField(label="mbox file")
    mailbox = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Email address it came from",
        empty_label="(not recorded)",
        help_text="Optional. Which of the Subject's addresses this export is from.",
    )

    def __init__(self, *args, subject, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mailbox"].queryset = subject.mailboxes.all()
