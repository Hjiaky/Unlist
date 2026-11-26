# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from unlist.cases import lifecycle, replies, sending, services, storage
from unlist.cases.forms import (
    AssignReplyForm,
    AuthorityLetterForm,
    DetailsChoiceForm,
    DraftEditForm,
    MarkSentForm,
    OpenCaseForm,
    OutcomeForm,
    PortalForm,
    RecheckForm,
    ReplyConfirmForm,
    ReplyUploadForm,
    SendIdForm,
)
from unlist.cases.lifecycle import Action, State
from unlist.cases.models import Attachment, Case, CaseEvent, Draft, Reply
from unlist.organizations.models import Organization
from unlist.subjects.consent import ConsentRequired
from unlist.subjects.models import Subject

ERRORS = (services.CaseError, ConsentRequired)
SEARCH_LIMIT = 50

# Case-level buttons and the service each one calls. Sending details and sending ID have their
# own pages (the Operator picks the details; the Subject's ID decision is explained first).
ACTION_SERVICES = {
    Action.PREPARE_REQUEST: services.prepare_request,
    Action.REQUEST_REMOVAL: services.request_removal,
    Action.KEEP_LISTING: services.keep_listing,
    Action.PUSH_BACK: services.push_back,
    Action.FIX_CONTACT: services.fix_contact,
    Action.SEND_REMINDER: services.send_reminder,
    Action.DRAFT_COMPLAINT: services.draft_complaint,
    Action.COMPLAINT_LODGED: services.complaint_lodged,
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
    pages = {Action.SEND_DETAILS: "cases:details", Action.SEND_ID: "cases:send_id"}
    actions = [
        (action.value, lifecycle.ACTION_LABELS[action], reverse(pages[action], args=[pk]) if action in pages else "")
        for action in services.available_actions(case)
    ]
    asked, pushed_back = services.demands(case)
    context = {
        "case": case,
        "events": case.events.all(),
        "drafts": [_draft_view(draft) for draft in case.drafts.order_by("-created_at", "-id")],
        "attachments": case.attachments.all(),
        "replies": case.replies.all(),
        "upload_form": ReplyUploadForm(),
        "asked": asked if case.state == State.PAUSED else None,
        "persistent_demand": case.state == State.PAUSED and pushed_back and asked == lifecycle.ASKED_ID_OR_DETAILS,
        "portal_form": PortalForm() if case.state in services.PORTAL_STATES else None,
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


# --- Replies (#49) -----------------------------------------------------------------------


def _back(request, reply):
    """Back to the Case page when the form came from there, else to the review queue."""
    if request.POST.get("next") == "case" and reply.case_id:
        return redirect("cases:detail", pk=reply.case_id)
    return redirect(f"{reverse('cases:replies')}#reply-{reply.pk}")


@login_required
def reply_queue(request):
    """Replies to confirm, nearest deadline first, and the unmatched queue."""
    to_confirm = (
        Reply.objects.filter(status=Reply.Status.TO_CONFIRM, case__isnull=False)
        .select_related("case", "case__organization", "subject", "raw_attachment")
        .prefetch_related("attachments")
        .order_by(F("case__due_date").asc(nulls_last=True), "-received_at", "-id")
    )
    unmatched = (
        Reply.objects.filter(status=Reply.Status.TO_CONFIRM, case__isnull=True)
        .select_related("subject")
        .order_by("-received_at", "-id")
    )
    context = {
        "to_confirm": [
            {
                "reply": reply,
                "form": ReplyConfirmForm(reply=reply, prefix=f"r{reply.pk}"),
                "files": replies.reply_attachments(reply),
            }
            for reply in to_confirm
        ],
        "unmatched": [
            {"reply": reply, "form": AssignReplyForm(reply=reply, prefix=f"r{reply.pk}")} for reply in unmatched
        ],
    }
    return render(request, "cases/replies.html", context)


def _reply(pk):
    return get_object_or_404(Reply.objects.select_related("case", "case__organization", "subject"), pk=pk)


@login_required
@require_POST
def reply_confirm(request, pk):
    reply = _reply(pk)
    if reply.case is None:
        messages.error(request, "Assign the reply to a Case first.")
        return _back(request, reply)
    form = ReplyConfirmForm(request.POST, reply=reply, prefix=f"r{reply.pk}")
    if not form.is_valid():
        errors = "; ".join(f"{name}: {' '.join(errs)}" for name, errs in form.errors.items())
        messages.error(request, f"Not recorded. {errors}")
        return _back(request, reply)
    data = form.cleaned_data
    try:
        replies.confirm(reply, data["outcome"], on=data["occurred_on"], **form.outcome_details())
    except ERRORS as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Recorded on Case {reply.case.reference}.")
    return _back(request, reply)


@login_required
@require_POST
def reply_dismiss(request, pk):
    reply = _reply(pk)
    try:
        replies.dismiss(reply)
    except ERRORS as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Reply dismissed. Its text and files were deleted.")
    if request.POST.get("next") == "case" and reply.case_id:
        return redirect("cases:detail", pk=reply.case_id)
    return redirect("cases:replies")


@login_required
@require_POST
def reply_assign(request, pk):
    reply = _reply(pk)
    form = AssignReplyForm(request.POST, reply=reply, prefix=f"r{reply.pk}")
    if not form.is_valid():
        messages.error(request, "Choose a Case of this Subject.")
        return redirect("cases:replies")
    try:
        replies.assign(reply, form.cleaned_data["case"])
    except ERRORS as error:
        messages.error(request, str(error))
        return redirect("cases:replies")
    messages.success(request, f"Reply assigned to Case {reply.case.reference}.")
    return redirect(f"{reverse('cases:replies')}#reply-{reply.pk}")


UPLOAD_REASONS = {
    "own": "Not taken in: it was sent from the Subject's own address. Only the Organization's replies are kept.",
    "duplicate": "Not taken in: this message was taken in before.",
}


@login_required
@require_POST
def case_reply_upload(request, pk):
    case = get_object_or_404(Case.objects.select_related("subject", "organization"), pk=pk)
    form = ReplyUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, " ".join(form.errors.get("eml", ["Choose an .eml file."])))
        return redirect("cases:detail", pk=pk)
    try:
        result = replies.ingest(case.subject, form.cleaned_data["eml"], source="upload", raw=form.raw, case=case)
    except ERRORS as error:
        messages.error(request, str(error))
        return redirect("cases:detail", pk=pk)
    if result.reply is None:
        messages.error(request, UPLOAD_REASONS.get(result.reason, f"Not taken in ({result.reason})."))
    elif result.reply.status == Reply.Status.AUTO_RECORDED:
        messages.success(request, f"Reply taken in and recorded: {result.reply.get_kind_display()}.")
    else:
        messages.success(request, "Reply taken in. Confirm what it says under Replies.")
    return redirect("cases:detail", pk=pk)


# --- ID and details demands (#50) --------------------------------------------------------


def _case(pk):
    return get_object_or_404(Case.objects.select_related("subject", "organization"), pk=pk)


def _unavailable(request, case, action):
    """A redirect with the reason when ``action`` is not possible for the Case now, else None."""
    if action in services.available_actions(case):
        return None
    messages.error(request, lifecycle.transition(services.case_state(case), action).error or "Not possible now.")
    return redirect("cases:detail", pk=case.pk)


@login_required
def case_details(request, pk):
    """Pick exactly which of the Subject's identifying details the details reply gives."""
    case = _case(pk)
    if blocked := _unavailable(request, case, Action.SEND_DETAILS):
        return blocked
    form = DetailsChoiceForm(request.POST if request.method == "POST" else None, case=case)
    if request.method == "POST" and form.is_valid():
        try:
            services.send_chosen_details(case, form.cleaned_data["details"])
        except ERRORS as error:
            messages.error(request, str(error))
        else:
            return redirect("cases:detail", pk=pk)
    return render(request, "cases/details.html", {"case": case, "form": form})


@login_required
def case_send_id(request, pk):
    """The Subject sends ID anyway: explain the hand-over, then draft the reply. Nothing is uploaded."""
    case = _case(pk)
    if blocked := _unavailable(request, case, Action.SEND_ID):
        return blocked
    form = SendIdForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            services.send_id(case)
        except ERRORS as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Reply drafted. After approval the Subject attaches their ID and sends it.")
            return redirect("cases:detail", pk=pk)
    return render(request, "cases/send_id.html", {"case": case, "form": form})


@login_required
@require_POST
def case_portal(request, pk):
    case = _case(pk)
    form = PortalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter the link to the Organization's portal or web form.")
        return redirect("cases:detail", pk=pk)
    try:
        services.hand_over_to_portal(case, form.cleaned_data["url"])
    except ERRORS as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Handed over to the Subject: they use the Organization's portal.")
    return redirect("cases:detail", pk=pk)


@login_required
def case_authority_letter(request, pk):
    """Write a fresh, dated letter of authority for this Case's Organization."""
    case = _case(pk)
    name = request.user.get_full_name() or request.user.get_username()
    form = AuthorityLetterForm(request.POST if request.method == "POST" else None, initial={"operator_name": name})
    if request.method == "POST" and form.is_valid():
        try:
            event = services.authority_letter(case, form.cleaned_data["operator_name"])
        except ERRORS as error:
            messages.error(request, str(error))
        else:
            return redirect("cases:authority_letter_show", pk=event.pk)
    return render(request, "cases/authority_letter_form.html", {"case": case, "form": form})


@login_required
def authority_letter_show(request, pk):
    event = get_object_or_404(
        CaseEvent.objects.select_related("case", "case__subject", "case__organization"),
        pk=pk,
        kind=CaseEvent.Kind.AUTHORITY_LETTER,
    )
    return render(request, "cases/authority_letter.html", {"event": event, "case": event.case})
