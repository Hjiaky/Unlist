# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from unlist.subjects.consent import CONSENT_SCOPE, record_consent, withdraw_consent
from unlist.subjects.deletion import delete_subject
from unlist.subjects.forms import ConsentForm, IdentifyingDetailForm, MailboxForm, SubjectForm
from unlist.subjects.models import Subject


@login_required
def subject_list(request):
    return render(request, "subjects/list.html", {"subjects": Subject.objects.all()})


@login_required
def subject_add(request):
    form = SubjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        subject = form.save()
        return redirect("subjects:detail", pk=subject.pk)
    return render(request, "subjects/add.html", {"form": form})


@login_required
def subject_detail(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    context = {
        "subject": subject,
        "mailboxes": subject.mailboxes.all(),
        "details": subject.details.all(),
        "consent": subject.consents.filter(withdrawn_at__isnull=True).first(),
        "last_withdrawn": subject.consents.filter(withdrawn_at__isnull=False).order_by("-withdrawn_at").first(),
    }
    return render(request, "subjects/detail.html", context)


@login_required
def consent_record(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if subject.has_active_consent():
        return redirect("subjects:detail", pk=pk)
    form = ConsentForm(request.POST or None, subject=subject)
    if request.method == "POST" and form.is_valid():
        record_consent(subject, form.cleaned_data["given_by"])
        return redirect("subjects:detail", pk=pk)
    return render(request, "subjects/consent.html", {"subject": subject, "form": form, "scope": CONSENT_SCOPE})


@login_required
@require_POST
def consent_withdraw(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    withdraw_consent(subject)
    return redirect("subjects:detail", pk=pk)


@login_required
def detail_add(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = IdentifyingDetailForm(request.POST or None, subject=subject)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("subjects:detail", pk=pk)
    return render(request, "subjects/detail_add.html", {"subject": subject, "form": form})


@login_required
@require_POST
def detail_remove(request, pk, detail_pk):
    subject = get_object_or_404(Subject, pk=pk)
    get_object_or_404(subject.details, pk=detail_pk).delete()
    return redirect("subjects:detail", pk=pk)


@login_required
def mailbox_add(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = MailboxForm(request.POST or None, subject=subject)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("subjects:detail", pk=pk)
    return render(request, "subjects/mailbox_add.html", {"subject": subject, "form": form})


@login_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == "POST":
        delete_subject(subject)
        return redirect("subjects:list")
    return render(request, "subjects/delete.html", {"subject": subject})
