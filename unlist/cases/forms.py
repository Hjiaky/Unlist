# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django import forms
from django.utils import timezone

from unlist.cases import lifecycle
from unlist.cases.models import validate_recheck_override
from unlist.cases.storage import MAX_UPLOAD_BYTES
from unlist.organizations.models import Organization
from unlist.subjects.models import Subject


class DateInput(forms.DateInput):
    input_type = "date"


class OpenCaseForm(forms.Form):
    subject = forms.ModelChoiceField(queryset=Subject.objects.all())
    organization = forms.ModelChoiceField(queryset=Organization.objects.filter(obsolete=False), to_field_name="slug")
    direct_removal = forms.BooleanField(
        required=False,
        label="Request removal directly",
        help_text="Skip the Access Request and ask for removal straight away. By default Unlist asks first.",
    )


class OutcomeForm(forms.Form):
    outcome = forms.ChoiceField(label="What happened")
    occurred_on = forms.DateField(label="On", widget=DateInput, help_text="The day the answer arrived.")
    suppression_confirmed = forms.BooleanField(
        required=False, label="The Broker confirmed it keeps a Suppression Record", help_text="For a removal."
    )
    exception = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Exception cited",
        help_text="For a refusal: the reason or legal duty the Organization names, in its own words.",
    )
    with_reasons = forms.BooleanField(
        required=False, label="The extension notice gives reasons", help_text="For an extension."
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Note")
    file = forms.FileField(
        required=False,
        label="The reply (.eml) or another file",
        help_text="Kept as evidence. Never upload an ID document: Unlist does not store them.",
    )

    def __init__(self, *args, outcomes=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["outcome"].choices = [(o.value, lifecycle.OUTCOME_LABELS[o]) for o in outcomes]
        self.fields["occurred_on"].initial = timezone.localdate()

    def clean_occurred_on(self):
        day = self.cleaned_data["occurred_on"]
        if day > timezone.localdate():
            raise forms.ValidationError("The date cannot be in the future.")
        return day

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        if upload and upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        return upload


class MarkSentForm(forms.Form):
    sent_on = forms.DateField(label="Sent on", widget=DateInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sent_on"].initial = timezone.localdate()


class DraftEditForm(forms.Form):
    subject_line = forms.CharField(max_length=500, label="Subject line")
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 24}))


class RecheckForm(forms.Form):
    recheck_override = forms.CharField(
        required=False,
        max_length=10,
        validators=[validate_recheck_override],
        label="Re-check for this Case",
        help_text='Days between re-checks, "close" to close instead, or empty for the default.',
    )
