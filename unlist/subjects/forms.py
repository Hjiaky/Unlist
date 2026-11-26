# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django import forms
from django.utils import timezone

from unlist.subjects.countries import COUNTRIES
from unlist.subjects.models import Consent, IdentifyingDetail, Mailbox, Subject


class SubjectForm(forms.ModelForm):
    country = forms.ChoiceField(choices=[("", "Choose a country")] + list(COUNTRIES))
    email = forms.EmailField(label="Email address")

    class Meta:
        model = Subject
        fields = ["name", "country", "year_of_birth", "parental_responsibility"]
        labels = {"year_of_birth": "Year of birth (optional)", "parental_responsibility": "Parental responsibility"}

    field_order = ["name", "country", "email", "year_of_birth", "parental_responsibility"]

    def clean_year_of_birth(self):
        year = self.cleaned_data["year_of_birth"]
        if year is not None and not 1900 <= year <= timezone.localdate().year:
            raise forms.ValidationError("Enter a plausible year of birth.")
        return year

    def save(self, commit=True):
        subject = super().save(commit)
        if commit:
            Mailbox.objects.create(subject=subject, email=self.cleaned_data["email"])
        return subject


class MailboxForm(forms.ModelForm):
    class Meta:
        model = Mailbox
        fields = ["email"]
        labels = {"email": "Email address"}

    def __init__(self, *args, subject, **kwargs):
        super().__init__(*args, **kwargs)
        self.subject = subject

    def clean_email(self):
        email = self.cleaned_data["email"]
        if self.subject.mailboxes.filter(email__iexact=email).exists():
            raise forms.ValidationError("This address is already listed.")
        return email

    def save(self, commit=True):
        self.instance.subject = self.subject
        return super().save(commit)


class IdentifyingDetailForm(forms.ModelForm):
    class Meta:
        model = IdentifyingDetail
        fields = ["kind", "value", "organization_label"]
        labels = {"organization_label": "Organization (optional)"}

    def __init__(self, *args, subject, **kwargs):
        super().__init__(*args, **kwargs)
        self.subject = subject

    def save(self, commit=True):
        self.instance.subject = self.subject
        return super().save(commit)


class ConsentForm(forms.Form):
    given_by = forms.ChoiceField(label="Who agreed", choices=Consent.GivenBy.choices)
    confirm = forms.BooleanField(
        label="I confirm that this person agreed to the scope above.",
        error_messages={"required": "Confirm that consent was given."},
    )

    def __init__(self, *args, subject, **kwargs):
        super().__init__(*args, **kwargs)
        self.subject = subject
        if not subject.is_child:
            self.fields["given_by"].choices = [(Consent.GivenBy.SUBJECT.value, Consent.GivenBy.SUBJECT.label)]
