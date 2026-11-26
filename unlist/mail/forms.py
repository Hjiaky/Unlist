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


_LABEL = r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
HOST_PATTERN = rf"^(?=.{{1,253}}$){_LABEL}(\.{_LABEL})*$"
SMTP_CHOICES = [("465", "465, SSL/TLS"), ("587", "587, STARTTLS")]


class ConnectionForm(forms.Form):
    """Settings of a live connection. The password may stay empty to keep the stored one."""

    imap_host = forms.RegexField(regex=HOST_PATTERN, max_length=253, label="IMAP server")
    imap_port = forms.IntegerField(min_value=1, max_value=65535, initial=993, label="IMAP port (always TLS)")
    smtp_host = forms.RegexField(regex=HOST_PATTERN, max_length=253, label="SMTP server")
    smtp = forms.ChoiceField(choices=SMTP_CHOICES, initial="465", label="SMTP port and security")
    username = forms.CharField(max_length=320, label="User name", help_text="Usually the full email address.")
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        required=False,
        strip=False,
        max_length=500,
        label="App password",
    )

    def __init__(self, *args, has_password=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_password = has_password
        if has_password:
            self.fields["password"].help_text = "Leave empty to keep the stored app password."

    def clean_imap_host(self):
        return self.cleaned_data["imap_host"].lower()

    def clean_smtp_host(self):
        return self.cleaned_data["smtp_host"].lower()

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if not password and not self.has_password:
            raise forms.ValidationError("Enter the app password.")
        return password

    def settings(self):
        """The cleaned values as MailboxConnection fields (without the password)."""
        from unlist.mail.models import MailboxConnection

        data = self.cleaned_data
        security = MailboxConnection.Security.SSL if data["smtp"] == "465" else MailboxConnection.Security.STARTTLS
        return {
            "imap_host": data["imap_host"],
            "imap_port": data["imap_port"],
            "smtp_host": data["smtp_host"],
            "smtp_port": int(data["smtp"]),
            "smtp_security": security,
            "username": data["username"].strip(),
        }

    @staticmethod
    def initial_for(connection=None, preset=None, address=""):
        if connection is not None:
            return {
                "imap_host": connection.imap_host,
                "imap_port": connection.imap_port,
                "smtp_host": connection.smtp_host,
                "smtp": "587" if connection.smtp_port == 587 else "465",
                "username": connection.username,
            }
        initial = {"imap_port": 993, "smtp": "465", "username": address}
        if preset is not None:
            initial.update(
                imap_host=preset["imap_host"],
                imap_port=preset["imap_port"],
                smtp_host=preset["smtp_host"],
                smtp=str(preset["smtp_port"]),
            )
        return initial
