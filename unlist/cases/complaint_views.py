# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The Complaint page (ticket #52): the text to paste, the evidence bundle, the authority's channel.

Unlist never submits a Complaint. The page prints cleanly (``complaints.css``), so the browser can
print it or save it as PDF; there is no PDF library.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from unlist.cases import complaints, services
from unlist.cases.forms import DateInput
from unlist.cases.models import Case
from unlist.cases.storage import MAX_UPLOAD_BYTES
from unlist.subjects.consent import ConsentRequired

ERRORS = (services.CaseError, ConsentRequired)


class DayForm(forms.Form):
    on = forms.DateField(label="On", widget=DateInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["on"].initial = timezone.localdate()


class AnswerForm(DayForm):
    file = forms.FileField(required=False, label="The answer (.eml) or another file", help_text="Kept as evidence.")

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        if upload and upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        return upload


def _case(pk):
    return get_object_or_404(Case.objects.select_related("subject", "organization"), pk=pk)


@login_required
def complaint(request, pk):
    case = _case(pk)
    if case.state not in complaints.COMPLAINT_STATES:
        try:
            complaints.check_allowed(case)
        except services.IllegalStep as error:
            messages.error(request, str(error))
        else:
            messages.error(request, "Draft the Complaint first (“Draft a Complaint” on the Case page).")
        return redirect("cases:detail", pk=pk)
    context = {"case": case, "day_form": DayForm(), "answer_form": AnswerForm()}
    lodged = complaints.lodged_complaint(case)
    if lodged is not None:
        context["lodged"] = lodged
        context["lodged_text"] = lodged.details.get("complaint")
    progress = complaints.progress(case)
    context["progress"] = progress
    if lodged is not None:
        return render(request, "cases/complaint.html", context)
    try:
        if progress.stage == complaints.Stage.UK_ORGANIZATION:
            letter = complaints.uk_letter(case)
            context["uk_letter"] = letter
            if letter.channel == "email":
                context["uk_mailto"] = complaints.uk_letter_mailto(letter)
        if progress.authority_ready:
            context["complaint"] = complaints.build_complaint(case)
    except ERRORS as error:
        messages.error(request, str(error))
    return render(request, "cases/complaint.html", context)


@login_required
@require_POST
def complaint_authority(request, pk):
    case = _case(pk)
    try:
        complaints.choose_authority(case, request.POST.get("authority", ""))
    except ERRORS as error:
        messages.error(request, str(error))
    return redirect("cases:complaint", pk=pk)


@login_required
@require_POST
def complaint_uk(request, pk, step):
    case = _case(pk)
    try:
        if step == "skip":
            complaints.skip_uk_step(case)
        elif step in ("sent", "answered"):
            form = AnswerForm(request.POST, request.FILES)
            if not form.is_valid():
                messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
                return redirect("cases:complaint", pk=pk)
            if step == "sent":
                complaints.uk_letter_sent(case, on=form.cleaned_data["on"])
            else:
                complaints.uk_letter_answered(case, on=form.cleaned_data["on"], upload=form.cleaned_data["file"])
        else:
            messages.error(request, "Unknown step.")
    except ERRORS as error:
        messages.error(request, str(error))
    return redirect("cases:complaint", pk=pk)


@login_required
def complaint_uk_eml(request, pk):
    case = _case(pk)
    try:
        data = complaints.uk_letter_eml(case)
    except ERRORS as error:
        messages.error(request, str(error))
        return redirect("cases:complaint", pk=pk)
    response = HttpResponse(data, content_type="message/rfc822")
    response["Content-Disposition"] = f'attachment; filename="{case.reference}-uk-complaint-to-organization.eml"'
    return response


@login_required
def complaint_evidence(request, pk):
    case = _case(pk)
    try:
        data = complaints.evidence_zip(complaints.build_complaint(case))
    except ERRORS as error:
        messages.error(request, str(error))
        return redirect("cases:detail", pk=pk)
    response = HttpResponse(data, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{complaints.evidence_filename(case)}"'
    return response


@login_required
@require_POST
def complaint_lodged(request, pk):
    case = _case(pk)
    form = DayForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter the day the Complaint was lodged.")
        return redirect("cases:complaint", pk=pk)
    try:
        complaints.mark_lodged(case, on=form.cleaned_data["on"])
    except ERRORS as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Marked as lodged. The Supervisory Authority takes it from here.")
    return redirect("cases:complaint", pk=pk)
