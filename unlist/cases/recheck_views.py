# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The early re-check action on the Case page (ticket #51)."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from unlist.cases import rechecks, services
from unlist.cases.models import Case
from unlist.subjects.consent import ConsentRequired


class EarlyRecheckForm(forms.Form):
    reason = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Why re-check early",
        help_text="Recorded on the Case. For example: new mail from the Organization since its last answer.",
    )


@login_required
@require_POST
def early_recheck(request, pk):
    case = get_object_or_404(Case.objects.select_related("subject", "organization"), pk=pk)
    form = EarlyRecheckForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Say why the re-check should come early.")
        return redirect("cases:detail", pk=pk)
    try:
        rechecks.early_recheck(case, form.cleaned_data["reason"])
    except (services.CaseError, ConsentRequired) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Early re-check prepared: a fresh Access Request waits for approval.")
    return redirect("cases:detail", pk=pk)
