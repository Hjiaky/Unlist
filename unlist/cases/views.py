# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from unlist.cases import complaints, lifecycle, sending, services, storage
from unlist.cases.forms import DraftEditForm, MarkSentForm, OpenCaseForm, OutcomeForm, RecheckForm
from unlist.cases.lifecycle import Action, State
from unlist.cases.models import Attachment, Case, Draft
from unlist.organizations.models import Organization
from unlist.subjects.consent import ConsentRequired
from unlist.subjects.models import Subject

ERRORS = (services.CaseError, ConsentRequired)
SEARCH_LIMIT = 50

# Case-level buttons and the service each one calls.
ACTION_SERVICES = {
    Action.PREPARE_REQUEST: services.prepare_request,
    Action.REQUEST_REMOVAL: services.request_removal,
    Action.KEEP_LISTING: services.keep_listing,
    Action.SEND_DETAILS: services.send_details,
    Action.PUSH_BACK: services.push_back,
    Action.FIX_CONTACT: services.fix_contact,
    Action.SEND_REMINDER: services.send_reminder,
    Action.DRAFT_COMPLAINT: services.draft_complaint,
    Action.COMPLAINT_LODGED: complaints.mark_lodged,  # keeps the lodged text; checks the UK first step
    Action.ACCEPT_REFUSAL: services.accept_refusal,
    Action.ASK_RECONSIDER: services.ask_reconsider,
    Action.REOPEN: services.reopen,
    Action.STOP: services.stop,
}


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@login_required
def case_list(request):
    cases = Case.objects.select_related("subject", "organization")
    subject_id = _int_or_none(request.GET.get("subject"))
    state = request.GET.get("state", "")
    if subject_id:
        cases = cases.filter(subject_id=subject_id)
    if state in {member.value for member in State}:
        cases = cases.filter(state=state)
    else:
        state = ""
    context = {
        "cases": cases,
        "subjects": Subject.objects.all(),
        "states": Case.STATE_CHOICES,
        "selected_subject": subject_id,
        "selected_state": state,
    }
    return render(request, "cases/list.html", context)


@login_required
def case_new(request):
    if request.method == "POST":
        form = OpenCaseForm(request.POST)
        if form.is_valid():
            try:
                case = services.open_case(
                    form.cleaned_data["subject"],
                    form.cleaned_data["organization"],
                    direct_removal=form.cleaned_data["direct_removal"],
                )
            except services.CaseExists as error:
                messages.error(request, str(error))
                return redirect("cases:detail", pk=error.case.pk)
            except ERRORS as error:
                messages.error(request, str(error))
            else:
                messages.success(request, f"Case {case.reference} opened. Its first draft waits for approval.")
                return redirect("cases:detail", pk=case.pk)
        else:
            messages.error(request, "Choose a Subject and an Organization.")
    subject_id = _int_or_none(request.GET.get("subject") or request.POST.get("subject"))
    query = (request.GET.get("q") or "").strip()
    organizations = []
    if query:
        organizations = list(
            Organization.objects.filter(obsolete=False)
            .filter(Q(name__icontains=query) | Q(slug__icontains=query) | Q(domains__icontains=query))
            .order_by("name")[:SEARCH_LIMIT]
        )
    context = {
        "subjects": Subject.objects.all(),
        "selected_subject": subject_id,
        "query": query,
        "organizations": organizations,
        "limit": SEARCH_LIMIT,
    }
    return render(request, "cases/new.html", context)


def _draft_view(draft):
    """What the detail page shows for one draft: hand-over links and the approve button's wording."""
    view = {"draft": draft}
    if draft.status == Draft.Status.AWAITING_APPROVAL:
        if sending.will_send(draft):
            view["approve_label"] = f"Approve and send to {draft.recipient} (Unlist sends it)"
        elif draft.channel == Draft.Channel.EMAIL:
            view["approve_label"] = f"Approve and hand over to the Subject, to send to {draft.recipient}"
        elif draft.channel == Draft.Channel.WEBFORM:
            view["approve_label"] = f"Approve and hand over to the Subject, to submit at {draft.recipient}"
        else:
            view["approve_label"] = "Approve and hand over to the Subject, to post to the address shown"
    if draft.status == Draft.Status.HANDED_OVER and draft.channel == Draft.Channel.EMAIL:
        view["mailto"] = sending.mailto_link(draft)
    return view


@login_required
def case_detail(request, pk):
    case = get_object_or_404(Case.objects.select_related("subject", "organization"), pk=pk)
    deadline = services.case_deadline(case)
    actions = [(action.value, lifecycle.ACTION_LABELS[action]) for action in services.available_actions(case)]
    context = {
        "case": case,
        "events": case.events.all(),
        "drafts": [_draft_view(draft) for draft in case.drafts.order_by("-created_at", "-id")],
        "attachments": case.attachments.all(),
        "actions": actions,
        "can_record_outcome": bool(services.available_outcomes(case)),
        "deadline": deadline,
        "deadline_shown": deadline is not None and case.state in lifecycle.CLOCK_STATES,
        "mark_sent_form": MarkSentForm(),
        "recheck_form": RecheckForm(initial={"recheck_override": case.recheck_override}),
        "recheck_intervals": services.recheck_intervals(case),
    }
    return render(request, "cases/detail.html", context)


@login_required
@require_POST
def case_action(request, pk, action):
    case = get_object_or_404(Case, pk=pk)
    try:
        service = ACTION_SERVICES[Action(action)]
    except (ValueError, KeyError):
        raise Http404("Unknown action") from None
    try:
        service(case)
    except ERRORS as error:
        messages.error(request, str(error))
    return redirect("cases:detail", pk=pk)


@login_required
def case_outcome(request, pk):
    case = get_object_or_404(Case.objects.select_related("subject", "organization"), pk=pk)
    outcomes = services.available_outcomes(case)
    if not outcomes:
        messages.error(request, "No answer from the Organization can be recorded in this state.")
        return redirect("cases:detail", pk=pk)
    form = OutcomeForm(request.POST or None, request.FILES or None, outcomes=outcomes)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        details = {}
        if data["note"]:
            details["note"] = data["note"]
        outcome = Action(data["outcome"])
        if outcome is Action.REMOVED:
            details["suppression_confirmed"] = data["suppression_confirmed"]
        if outcome is Action.REFUSED:
            details["exception"] = data["exception"]
        if outcome is Action.EXTENSION_ANNOUNCED:
            details["with_reasons"] = data["with_reasons"]
        try:
            event = services.record_outcome(case, outcome, on=data["occurred_on"], **details)
        except ERRORS as error:
            messages.error(request, str(error))
        else:
            if data["file"]:
                storage.store_upload(case, data["file"], event=event)
            return redirect("cases:detail", pk=pk)
    return render(request, "cases/outcome.html", {"case": case, "form": form})


@login_required
@require_POST
def case_recheck(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = RecheckForm(request.POST)
    if form.is_valid():
        services.set_recheck_override(case, form.cleaned_data["recheck_override"])
    else:
        messages.error(request, " ".join(form.errors.get("recheck_override", ["Invalid value."])))
    return redirect("cases:detail", pk=pk)


def _draft(pk):
    return get_object_or_404(Draft.objects.select_related("case", "case__subject", "case__organization"), pk=pk)


@login_required
@require_POST
def draft_approve(request, pk):
    draft = _draft(pk)
    try:
        services.approve(draft)
    except ERRORS as error:
        messages.error(request, str(error))
    return redirect("cases:detail", pk=draft.case_id)


@login_required
@require_POST
def draft_discard(request, pk):
    draft = _draft(pk)
    try:
        services.discard(draft)
    except ERRORS as error:
        messages.error(request, str(error))
    return redirect("cases:detail", pk=draft.case_id)


@login_required
@require_POST
def draft_sent(request, pk):
    draft = _draft(pk)
    form = MarkSentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter the day it was sent.")
        return redirect("cases:detail", pk=draft.case_id)
    try:
        services.mark_sent(draft, on=form.cleaned_data["sent_on"])
    except ERRORS as error:
        messages.error(request, str(error))
    return redirect("cases:detail", pk=draft.case_id)


@login_required
def draft_edit(request, pk):
    draft = _draft(pk)
    if draft.status != Draft.Status.AWAITING_APPROVAL:
        messages.error(request, "Only a draft awaiting approval can be changed.")
        return redirect("cases:detail", pk=draft.case_id)
    form = DraftEditForm(request.POST or None, initial={"subject_line": draft.subject_line, "body": draft.body})
    if request.method == "POST" and form.is_valid():
        try:
            services.edit_draft(draft, subject_line=form.cleaned_data["subject_line"], body=form.cleaned_data["body"])
        except ERRORS as error:
            messages.error(request, str(error))
        else:
            return redirect("cases:detail", pk=draft.case_id)
    return render(request, "cases/draft_edit.html", {"draft": draft, "case": draft.case, "form": form})


def _handed_over(draft):
    if draft.status not in (Draft.Status.HANDED_OVER, Draft.Status.SENT):
        raise Http404("Only an approved draft can be downloaded.")


@login_required
def draft_eml(request, pk):
    draft = _draft(pk)
    _handed_over(draft)
    response = HttpResponse(sending.eml_bytes(draft), content_type="message/rfc822")
    response["Content-Disposition"] = f'attachment; filename="{sending.eml_filename(draft)}"'
    return response


@login_required
def draft_letter(request, pk):
    draft = _draft(pk)
    _handed_over(draft)
    context = {"draft": draft, "case": draft.case, "today": timezone.localdate()}
    return render(request, "cases/letter.html", context)


@login_required
def attachment_download(request, pk):
    attachment = get_object_or_404(Attachment.objects.select_related("case"), pk=pk)
    path = storage.attachment_path(attachment)
    if not path.is_file():
        raise Http404("The file is missing.")
    return FileResponse(
        open(path, "rb"),  # FileResponse closes it
        as_attachment=True,
        filename=attachment.original_name,
        content_type="application/octet-stream",
    )
