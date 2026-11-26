# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django import forms
from django.utils import timezone

from unlist.cases import lifecycle, replies, services
from unlist.cases.models import Case, validate_recheck_override
from unlist.cases.storage import MAX_UPLOAD_BYTES
from unlist.organizations.models import Organization
from unlist.subjects.models import Subject

ID_WARNING = (
    "Never upload an ID document (passport, identity card, driving licence) or a message with one attached: "
    "Unlist does not store them. If the Subject sends ID, they attach it from their own device."
)


class DateInput(forms.DateInput):
    input_type = "date"


def _not_in_future(day):
    if day > timezone.localdate():
        raise forms.ValidationError("The date cannot be in the future.")
    return day


def _check_size(upload):
    if upload and upload.size > MAX_UPLOAD_BYTES:
        raise forms.ValidationError(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    return upload


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
        help_text=f"Kept as evidence. {ID_WARNING}",
    )

    def __init__(self, *args, outcomes=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["outcome"].choices = [(o.value, lifecycle.OUTCOME_LABELS[o]) for o in outcomes]
        self.fields["occurred_on"].initial = timezone.localdate()

    def clean_occurred_on(self):
        return _not_in_future(self.cleaned_data["occurred_on"])

    def clean_file(self):
        return _check_size(self.cleaned_data.get("file"))


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


class ReplyUploadForm(forms.Form):
    """An ``.eml`` of the Organization's reply, uploaded on the Case page (import-only mode)."""

    eml = forms.FileField(
        label="Upload a reply (.eml)", help_text=f"The Organization's email, saved as .eml. {ID_WARNING}"
    )

    def clean_eml(self):
        upload = _check_size(self.cleaned_data.get("eml"))
        data = b"".join(upload.chunks())
        message = replies.parse_bytes(data)
        if not (message.get("From") or message.get("Subject")):
            raise forms.ValidationError("This does not look like an email (.eml) file.")
        self.raw = data
        return message


class ReplyConfirmForm(forms.Form):
    """The Operator's decision on one reply: the suggested outcome is pre-selected, never applied."""

    outcome = forms.ChoiceField(label="What the reply says")
    occurred_on = forms.DateField(label="Arrived on", widget=DateInput)
    suppression_confirmed = forms.BooleanField(
        required=False, label="The Broker confirmed it keeps a Suppression Record", help_text="For a removal."
    )
    exception = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Exception cited",
        help_text="For a refusal: the reason or legal duty the Organization names.",
    )
    with_reasons = forms.BooleanField(required=False, label="The extension notice gives reasons")
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Note")

    def __init__(self, *args, reply, **kwargs):
        super().__init__(*args, **kwargs)
        outcomes = services.available_outcomes(reply.case) if reply.case else []
        choices = [(o.value, lifecycle.OUTCOME_LABELS[o]) for o in outcomes]
        choices.append((replies.ATTACH_ONLY, "Keep it on the Case, no outcome (for example an acknowledgement)"))
        self.fields["outcome"].choices = choices
        values = {value for value, _label in choices}
        self.fields["outcome"].initial = (
            reply.suggested_outcome if reply.suggested_outcome in values else replies.ATTACH_ONLY
        )
        self.fields["occurred_on"].initial = reply.received_on
        self.fields["exception"].initial = reply.suggested_exception
        self.fields["suppression_confirmed"].initial = bool(reply.suggested_suppression)
        self.fields["with_reasons"].initial = bool(reply.suggested_with_reasons)

    def clean_occurred_on(self):
        return _not_in_future(self.cleaned_data["occurred_on"])

    def outcome_details(self) -> dict:
        data = self.cleaned_data
        details = {"note": data["note"]} if data["note"] else {}
        outcome = data["outcome"]
        if outcome == lifecycle.Action.REMOVED:
            details["suppression_confirmed"] = data["suppression_confirmed"]
        elif outcome == lifecycle.Action.REFUSED:
            details["exception"] = data["exception"]
        elif outcome == lifecycle.Action.EXTENSION_ANNOUNCED:
            details["with_reasons"] = data["with_reasons"]
        return details


class AssignReplyForm(forms.Form):
    case = forms.ModelChoiceField(queryset=Case.objects.none(), label="Case")

    def __init__(self, *args, reply, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["case"].queryset = Case.objects.filter(subject_id=reply.subject_id).select_related("organization")
        self.fields["case"].label_from_instance = lambda case: f"{case.reference}: {case.organization.name}"
