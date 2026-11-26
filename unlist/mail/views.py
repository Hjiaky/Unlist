# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST

from unlist import crypto
from unlist.mail import imap, importer, jobs, live, providers, scanner, services
from unlist.mail.forms import ConnectionForm, MboxUploadForm
from unlist.mail.models import Discovery, Evidence, ImportRun, MailboxConnection, UnassignedSender
from unlist.mail.uploads import DataDirUploadHandler
from unlist.organizations import lookup
from unlist.organizations import services as organization_services
from unlist.organizations.models import Domain, Organization
from unlist.subjects.models import Mailbox, Subject

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


YES_NO = {"yes": True, "no": False}


@login_required
def discoveries(request, pk):
    """The Organizations found in the Subject's mail, filtered by evidence and Broker (yes/no)."""
    subject = get_object_or_404(Subject, pk=pk)
    with_case = services.case_organization_ids(subject)
    found = subject.discoveries.select_related("organization")
    evidence = request.GET.get("evidence", "")
    broker = request.GET.get("broker", "")
    if evidence in Evidence.values:
        found = found.filter(evidence=evidence)
    else:
        evidence = ""
    if broker in YES_NO:
        found = found.filter(organization__broker=YES_NO[broker])
    else:
        broker = ""
    rows = []
    for discovery in found.annotate(rank=EVIDENCE_RANK).order_by("rank", "-last_seen", "organization__name"):
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
        "evidence_choices": [(kind, Evidence(kind).label) for kind in scanner.EVIDENCE_ORDER],
        "selected_evidence": evidence,
        "selected_broker": broker,
        "filtered": bool(evidence or broker),
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


# Live connections -----------------------------------------------------------------------


def _mailbox(pk, mailbox_pk):
    return get_object_or_404(Mailbox.objects.select_related("subject"), pk=mailbox_pk, subject=pk)


def _connection(pk, mailbox_pk):
    return get_object_or_404(
        MailboxConnection.objects.select_related("mailbox__subject"), mailbox=mailbox_pk, mailbox__subject=pk
    )


@login_required
def connections(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    by_mailbox = {item.mailbox_id: item for item in MailboxConnection.objects.filter(mailbox__subject=subject)}
    rows = [{"mailbox": mailbox, "connection": by_mailbox.get(mailbox.pk)} for mailbox in subject.mailboxes.all()]
    return render(request, "mail/connections.html", {"subject": subject, "rows": rows})


@login_required
def connect(request, pk, mailbox_pk):
    mailbox = _mailbox(pk, mailbox_pk)
    existing = MailboxConnection.objects.filter(mailbox=mailbox).first()
    preset = providers.get(request.GET.get("provider"))
    if preset is None and existing is None:
        preset = providers.for_address(mailbox.email)
    has_password = existing is not None and bool(existing.password_encrypted)
    results = []
    if request.method == "POST":
        form = ConnectionForm(request.POST, has_password=has_password)
        if form.is_valid():
            settings = form.settings()
            password = form.cleaned_data["password"]
            if request.POST.get("action") == "test":
                probe = MailboxConnection(mailbox=mailbox, **settings)
                if not password:
                    probe.password_encrypted = existing.password_encrypted
                results = live.test_connection(probe, password or None)
            else:
                try:
                    live.save_connection(mailbox, settings, password)
                except crypto.MissingKey as error:
                    messages.error(request, str(error))
                else:
                    messages.success(request, f"{mailbox.email} is connected. Test the connection, then scan it.")
                    return redirect("mail:connection", pk=pk, mailbox_pk=mailbox.pk)
    else:
        initial = ConnectionForm.initial_for(None if request.GET.get("provider") else existing, preset, mailbox.email)
        form = ConnectionForm(initial=initial, has_password=has_password)
    hosts = (form.data.get("imap_host", ""), form.data.get("smtp_host", "")) if form.is_bound else ()
    context = {
        "subject": mailbox.subject,
        "mailbox": mailbox,
        "connection": existing,
        "form": form,
        "preset": preset,
        "presets": list(providers.presets().values()),
        "results": results,
        "microsoft": providers.looks_like_microsoft(mailbox.email, *hosts),
    }
    return render(request, "mail/connect.html", context)


@login_required
def connection(request, pk, mailbox_pk):
    mailbox = _mailbox(pk, mailbox_pk)
    item = MailboxConnection.objects.filter(mailbox=mailbox).first()
    if item is None:
        return redirect("mail:connect", pk=pk, mailbox_pk=mailbox.pk)
    context = {
        "subject": mailbox.subject,
        "mailbox": mailbox,
        "connection": item,
        "run": mailbox.import_runs.filter(source=ImportRun.Source.IMAP).first(),
        "running": imap.is_running(item),
        "rescan_hours": jobs.RESCAN_HOURS,
    }
    return render(request, "mail/connection.html", context)


@login_required
@require_POST
def test_connection(request, pk, mailbox_pk):
    item = _connection(pk, mailbox_pk)
    for _, ok, message in live.test_connection(item):
        (messages.success if ok else messages.error)(request, message)
    return redirect("mail:connection", pk=pk, mailbox_pk=mailbox_pk)


@login_required
@require_POST
def scan_now(request, pk, mailbox_pk):
    item = _connection(pk, mailbox_pk)
    importer.clean_up_stale()  # a scan cut off by a restart must not block a new one
    if imap.is_running(item):
        messages.info(request, "A scan of this mailbox is already running.")
        return redirect("mail:connection", pk=pk, mailbox_pk=mailbox_pk)
    run = imap.start_scan(item)
    if run.failure:
        messages.error(request, run.failure)
    elif run.finished_at is None:
        messages.info(request, "The scan has started. A first scan of a large mailbox takes a while: reload to see it.")
    else:
        messages.success(request, f"Scanned {run.total} new message{'s' if run.total != 1 else ''}.")
    return redirect("mail:connection", pk=pk, mailbox_pk=mailbox_pk)


@login_required
@require_POST
def scheduled_rescans(request, pk, mailbox_pk):
    item = _connection(pk, mailbox_pk)
    item.scheduled_rescans = request.POST.get("enabled") == "1"
    item.save(update_fields=["scheduled_rescans"])
    if item.scheduled_rescans:
        messages.success(request, f"Scheduled re-scans are on: at most every {jobs.RESCAN_HOURS} hours.")
    else:
        messages.success(request, "Scheduled re-scans are off. Scan with the button when you want.")
    return redirect("mail:connection", pk=pk, mailbox_pk=mailbox_pk)


@login_required
@require_POST
def disconnect(request, pk, mailbox_pk):
    item = _connection(pk, mailbox_pk)
    email_address = item.mailbox.email
    live.disconnect(item)
    messages.success(request, f"{email_address} is disconnected and import-only again. Its app password is deleted.")
    return redirect("mail:connections", pk=pk)
