# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST

from unlist.mail import importer, scanner, services
from unlist.mail.forms import MboxUploadForm
from unlist.mail.models import Discovery, UnassignedSender
from unlist.mail.uploads import DataDirUploadHandler
from unlist.organizations import lookup
from unlist.organizations import services as organization_services
from unlist.organizations.models import Domain, Organization
from unlist.subjects.models import Subject

SEARCH_LIMIT = 30
EVIDENCE_RANK = Case(
    *[When(evidence=kind, then=Value(rank)) for rank, kind in enumerate(scanner.EVIDENCE_ORDER)],
    default=Value(len(scanner.EVIDENCE_ORDER)),
    output_field=IntegerField(),
)


@login_required
@csrf_exempt  # the CSRF check runs in _upload, after the upload handler is swapped
def upload(request, pk):
    request.upload_handlers = [DataDirUploadHandler(request)]
    return _upload(request, pk)


@csrf_protect
def _upload(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = MboxUploadForm(request.POST or None, request.FILES or None, subject=subject)
    if request.method == "POST" and form.is_valid():
        run = importer.import_mbox(subject, form.cleaned_data["file"], mailbox=form.cleaned_data["mailbox"])
        if run.failure:
            messages.error(request, run.failure)
        elif run.finished_at is None:
            messages.info(request, "The import has started. Large files take a while: reload to see it finish.")
        else:
            messages.success(request, f"Imported {run.total} messages.")
        return redirect("mail:discoveries", pk=subject.pk)
    return render(request, "mail/upload.html", {"subject": subject, "form": form})


@login_required
def discoveries(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    with_case = services.case_organization_ids(subject)
    rows = []
    for discovery in (
        subject.discoveries.select_related("organization")
        .annotate(rank=EVIDENCE_RANK)
        .order_by("rank", "-last_seen", "organization__name")
    ):
        if discovery.status == Discovery.Status.IGNORED:
            marker = "ignored"
        elif discovery.status == Discovery.Status.PURSUED or discovery.organization_id in with_case:
            marker = "case"
        else:
            marker = "new"
        rows.append({"discovery": discovery, "marker": marker})
    context = {
        "subject": subject,
        "rows": rows,
        "run": subject.import_runs.first(),
        "pursuable": len(services.pursuable_with_account_evidence(subject)),
        "unassigned": subject.unassigned_senders.filter(status=UnassignedSender.Status.OPEN).count(),
    }
    return render(request, "mail/discoveries.html", context)


def _discovery(pk, discovery_pk):
    return get_object_or_404(Discovery.objects.select_related("subject", "organization"), pk=discovery_pk, subject=pk)


@login_required
@require_POST
def pursue(request, pk, discovery_pk):
    discovery = _discovery(pk, discovery_pk)
    try:
        services.pursue(discovery)
    except services.PursueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Case opened for {discovery.organization.name}.")
    return redirect("mail:discoveries", pk=pk)


@login_required
@require_POST
def pursue_all(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    pursued, errors = services.pursue_all_with_account_evidence(subject)
    if pursued:
        messages.success(request, f"{len(pursued)} Case{'s' if len(pursued) != 1 else ''} opened.")
    for error in errors:
        messages.error(request, error)
    if not pursued and not errors:
        messages.info(request, "Nothing to pursue: no new Organization with account evidence.")
    return redirect("mail:discoveries", pk=pk)


@login_required
@require_POST
def ignore(request, pk, discovery_pk):
    services.ignore(_discovery(pk, discovery_pk))
    return redirect("mail:discoveries", pk=pk)


@login_required
@require_POST
def unignore(request, pk, discovery_pk):
    services.unignore(_discovery(pk, discovery_pk))
    return redirect("mail:discoveries", pk=pk)


@login_required
def unassigned(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    senders = subject.unassigned_senders.annotate(rank=EVIDENCE_RANK).order_by("rank", "-last_seen", "domain")
    context = {
        "subject": subject,
        "open": senders.filter(status=UnassignedSender.Status.OPEN),
        "ignored": senders.filter(status=UnassignedSender.Status.IGNORED),
    }
    return render(request, "mail/unassigned.html", context)


def _sender(pk, sender_pk):
    return get_object_or_404(UnassignedSender.objects.select_related("subject"), pk=sender_pk, subject=pk)


@login_required
def assign(request, pk, sender_pk):
    sender = _sender(pk, sender_pk)
    if request.method == "POST":
        try:
            if request.POST.get("create_stub") and not sender.ambiguous:
                organization = organization_services.create_stub(sender.domain)
            else:
                organization = lookup.get(request.POST.get("organization", ""))
        except ValueError as error:
            organization = None
            messages.error(request, str(error))
        else:
            if organization is None:
                messages.error(request, "That Organization does not exist.")
        if organization is None:
            return redirect("mail:assign", pk=pk, sender_pk=sender_pk)
        try:
            services.assign_sender(sender, organization)
        except services.AssignError as error:
            messages.error(request, str(error))
            return redirect("mail:assign", pk=pk, sender_pk=sender_pk)
        messages.success(request, f"{sender} assigned to {organization.name}.")
        return redirect("mail:unassigned", pk=pk)
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        results = Organization.objects.filter(obsolete=False).filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(pk__in=Domain.objects.filter(domain__icontains=query.lower()).values("organization_id"))
        )[:SEARCH_LIMIT]
    context = {"subject": sender.subject, "sender": sender, "query": query, "results": results}
    return render(request, "mail/assign.html", context)


@login_required
@require_POST
def ignore_sender(request, pk, sender_pk):
    services.ignore_sender(_sender(pk, sender_pk))
    return redirect("mail:unassigned", pk=pk)


@login_required
@require_POST
def unignore_sender(request, pk, sender_pk):
    services.unignore_sender(_sender(pk, sender_pk))
    return redirect("mail:unassigned", pk=pk)
