# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The settings page and the pages where the Operator sees, edits and applies a suggestion.

A job runs only on a click (except the reply job, which runs as replies come in). Its result is
shown, never applied: applying is a second, separate button.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from unlist import crypto
from unlist.cases import services as case_services
from unlist.cases.models import Draft
from unlist.llm import fetch, jobs
from unlist.llm.forms import ContactProposalForm, ContactUrlForm, DraftProposalForm, EvidenceForm, SettingsForm
from unlist.llm.models import LlmSettings
from unlist.mail import scanner
from unlist.mail.models import Discovery, Evidence, UnassignedSender
from unlist.organizations import merge
from unlist.organizations import services as organization_services
from unlist.organizations.models import Organization

NO_ANSWER = "No suggestion: the LLM gave no usable answer (the log says why). Nothing changed."
OFF = "The LLM is not switched on. Set it up on the LLM page, or carry on without it."


def _require_usable(request, settings):
    if settings.usable:
        return True
    messages.error(request, OFF)
    return False


@login_required
def settings_page(request):
    settings = LlmSettings.load()
    form = SettingsForm(request.POST or None, settings=settings)
    if request.method == "POST" and form.is_valid():
        try:
            form.apply(settings)
        except crypto.MissingKey as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "LLM settings saved.")
            return redirect("llm:settings")
    context = {"settings": settings, "form": form, "sends": jobs.SENDS, "common": jobs.COMMON}
    return render(request, "llm/settings.html", context)


@login_required
@require_POST
def accept_notice(request):
    settings = LlmSettings.load()
    if settings.pk is None or not settings.base_url or not settings.remote:
        messages.error(request, "There is no remote endpoint to accept.")
    else:
        settings.accept_notice()
        messages.success(request, f"Notice accepted for {settings.host}.")
    return redirect("llm:settings")


# --- 1. Discovery leftovers ------------------------------------------------------------------


def _leftover(kind, pk):
    model = {"discovery": Discovery, "sender": UnassignedSender}[kind]
    return get_object_or_404(model.objects.select_related("subject"), pk=pk)


def _back_to_mail(item):
    page = "mail:discoveries" if isinstance(item, Discovery) else "mail:unassigned"
    return redirect(page, pk=item.subject_id)


@login_required
@require_POST
def sort_leftover(request, kind, pk):
    item = _leftover(kind, pk)
    settings = LlmSettings.load()
    if not _require_usable(request, settings):
        return _back_to_mail(item)
    if item.evidence != scanner.NONE:
        messages.info(request, "The rules have already sorted this sender.")
        return _back_to_mail(item)
    suggestion = jobs.sort_leftover(item, settings)
    if suggestion is None:
        messages.info(request, NO_ANSWER)
        return _back_to_mail(item)
    context = {
        "item": item,
        "kind": kind,
        "subject": item.subject,
        "suggestion": suggestion,
        "label": Evidence(suggestion.evidence).label,
        "applicable": suggestion.evidence in jobs.SORTABLE,
    }
    return render(request, "llm/sort.html", context)


@login_required
@require_POST
def apply_evidence(request, kind, pk):
    item = _leftover(kind, pk)
    form = EvidenceForm(request.POST)
    if not form.is_valid():
        messages.error(request, "That is not an evidence kind the LLM may suggest.")
    elif type(item).objects.filter(pk=item.pk, evidence=scanner.NONE).update(evidence=form.cleaned_data["evidence"]):
        messages.success(request, f"Evidence for {item} set to “{Evidence(form.cleaned_data['evidence']).label}”.")
    else:
        messages.info(request, "The rules have sorted this sender in the meantime; nothing changed.")
    return _back_to_mail(item)


# --- 2. Drafts in another language -----------------------------------------------------------


def _draft(pk):
    return get_object_or_404(Draft.objects.select_related("case__subject", "case__organization"), pk=pk)


@login_required
@require_POST
def adapt_draft(request, pk):
    draft = _draft(pk)
    settings = LlmSettings.load()
    if not _require_usable(request, settings):
        return redirect("cases:detail", pk=draft.case_id)
    if jobs.adapt_target(draft) is None:
        messages.info(request, "This draft is already in the Organization's language, or no longer awaits approval.")
        return redirect("cases:detail", pk=draft.case_id)
    proposal = jobs.adapt_draft(draft, settings)
    if proposal is None:
        messages.info(request, NO_ANSWER)
        return redirect("cases:detail", pk=draft.case_id)
    form = DraftProposalForm(initial={"subject_line": proposal.subject_line, "body": proposal.body})
    context = {"draft": draft, "case": draft.case, "proposal": proposal, "form": form}
    return render(request, "llm/adapt.html", context)


@login_required
@require_POST
def accept_draft(request, pk):
    draft = _draft(pk)
    form = DraftProposalForm(request.POST)
    if form.is_valid():
        try:
            case_services.edit_draft(
                draft, subject_line=form.cleaned_data["subject_line"], body=form.cleaned_data["body"]
            )
        except case_services.CaseError as error:
            messages.error(request, str(error))
            context = {"draft": draft, "case": draft.case, "proposal": None, "form": form}
            return render(request, "llm/adapt.html", context)
        messages.success(request, "The draft now holds the adapted text. It still waits for your approval.")
    else:
        messages.error(request, "The adapted text was incomplete; the draft is unchanged.")
    return redirect("cases:detail", pk=draft.case_id)


# --- 4. Privacy contact ----------------------------------------------------------------------


@login_required
def find_contact(request, slug):
    organization = get_object_or_404(Organization, slug=slug)
    settings = LlmSettings.load()
    if not _require_usable(request, settings):
        return redirect("organizations:detail", slug=slug)
    form = ContactUrlForm(request.POST or None, initial={"url": organization.web or ""})
    proposal_form = proposal = None
    if request.method == "POST" and form.is_valid():
        try:
            proposal = jobs.find_privacy_contact(form.cleaned_data["url"], settings)
        except fetch.FetchError as error:
            messages.error(request, str(error))
        else:
            if proposal is None:
                messages.info(request, "No contact found: " + NO_ANSWER)
            else:
                proposal_form = ContactProposalForm(
                    initial={
                        "email": proposal.email,
                        "address": proposal.address,
                        "webform": proposal.webform,
                        "url": proposal.url,
                    }
                )
    context = {"organization": organization, "form": form, "proposal": proposal, "proposal_form": proposal_form}
    return render(request, "llm/contact.html", context)


@login_required
@require_POST
def confirm_contact(request, slug):
    organization = get_object_or_404(Organization, slug=slug)
    form = ContactProposalForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("llm:find_contact", slug=slug)
    values = {}
    try:
        for field in merge.CONTACT_FIELDS:
            text = form.cleaned_data[field].strip()
            if text:
                values[field] = organization_services.parse_override(field, text)
    except organization_services.OverrideError as error:
        messages.error(request, f"{field}: {error}")
        return redirect("llm:find_contact", slug=slug)
    note = f"found with the LLM in {form.cleaned_data['url']}"[:500]
    for field, value in values.items():
        organization_services.set_override(organization.slug, field, value, note)
    messages.success(request, f"Contact saved as a local override ({', '.join(values)}) and confirmed.")
    return redirect("organizations:detail", slug=slug)
