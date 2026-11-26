# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from unlist.organizations import loading, services
from unlist.organizations.forms import AddListForm, OverrideForm
from unlist.organizations.merge import DOMAINS, FIELDS
from unlist.organizations.models import Domain, LocalOverride, Organization, OrganizationList, PendingContactChange

PAGE_SIZE = 50


def _display(value):
    if value is None or value == "" or value == []:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return ", ".join(value)
    if isinstance(value, list) and all(isinstance(v, dict) and "desc" in v for v in value):  # required-elements
        return ", ".join(f"{v['desc']}{' (optional)' if v.get('optional') else ''}" for v in value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


@login_required
def organization_list(request):
    query = request.GET.get("q", "").strip()
    organizations = Organization.objects.filter(obsolete=False)
    if query:
        organizations = organizations.filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(pk__in=Domain.objects.filter(domain__icontains=query.lower()).values("organization_id"))
        )
    page = Paginator(organizations, PAGE_SIZE).get_page(request.GET.get("page"))
    pending = PendingContactChange.objects.count()
    return render(request, "organizations/list.html", {"page": page, "query": query, "pending": pending})


@login_required
def organization_detail(request, slug):
    organization = get_object_or_404(Organization, slug=slug)
    if organization.obsolete and organization.redirect_to:
        messages.info(request, f"{organization.name} ({slug}) is obsolete; showing the record it moved to.")
        return redirect("organizations:detail", slug=organization.redirect_to)
    rows = []
    for name, (attribute, _) in FIELDS.items():
        conflicts = organization.conflicts.get(name, [])
        rows.append(
            {
                "field": name,
                "value": _display(getattr(organization, attribute)),
                "source": organization.field_sources.get(name, ""),
                "conflicts": [(list_name, _display(value)) for list_name, value in conflicts],
            }
        )
    rows.insert(
        1,
        {
            "field": DOMAINS,
            "value": _display(organization.domains),
            "source": organization.field_sources.get(DOMAINS, ""),
            "conflicts": [],
        },
    )
    domain_conflicts = (
        Domain.objects.filter(domain__in=organization.domains)
        .exclude(organization=organization)
        .select_related("organization")
        .order_by("domain")
    )
    overrides = LocalOverride.objects.filter(organization_slug=organization.slug)
    form = OverrideForm()
    return render(
        request,
        "organizations/detail.html",
        {
            "organization": organization,
            "rows": rows,
            "domain_conflicts": domain_conflicts,
            "overrides": overrides,
            "form": form,
            "pending": PendingContactChange.objects.filter(organization=organization).first(),
            "cases": organization.cases.count(),
        },
    )


@login_required
@require_POST
def add_override(request, slug):
    organization = get_object_or_404(Organization, slug=slug)
    form = OverrideForm(request.POST)
    if form.is_valid():
        services.set_override(
            organization.slug, form.cleaned_data["field"], form.cleaned_data["parsed"], form.cleaned_data["note"]
        )
        messages.success(request, f"Local override for {form.cleaned_data['field']} saved.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect("organizations:detail", slug=organization.slug)


@login_required
@require_POST
def delete_override(request, slug, pk):
    override = get_object_or_404(LocalOverride, pk=pk, organization_slug=slug)
    services.delete_override(override)
    messages.success(request, f"Local override for {override.field} removed.")
    return redirect("organizations:detail", slug=slug)


@login_required
def export_contribution(request, slug):
    organization = get_object_or_404(Organization, slug=slug)
    record = services.contribution(organization)
    response = HttpResponse(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", content_type="application/json; charset=utf-8"
    )
    response["Content-Disposition"] = f'attachment; filename="{organization.slug}.json"'
    return response


@login_required
def lists(request):
    return render(
        request,
        "organizations/lists.html",
        {"lists": OrganizationList.objects.order_by("position", "id"), "form": AddListForm()},
    )


@login_required
@require_POST
def add_list(request):
    form = AddListForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("organizations:lists")
    if OrganizationList.objects.filter(url=form.cleaned_data["url"]).exists():
        messages.error(request, "That list is already subscribed.")
        return redirect("organizations:lists")
    organization_list = services.add_list(form.cleaned_data["url"])
    if organization_list.last_error:
        messages.error(request, f"Added, but it could not be loaded: {organization_list.last_error}")
    else:
        messages.success(request, f"Added {organization_list.name}.")
    return redirect("organizations:lists")


@login_required
@require_POST
def remove_list(request, pk):
    organization_list = get_object_or_404(OrganizationList, pk=pk, bundled=False)
    services.remove_list(organization_list)
    messages.success(request, f"Removed {organization_list.name}.")
    return redirect("organizations:lists")


@login_required
@require_POST
def move_list(request, pk):
    organization_list = get_object_or_404(OrganizationList, pk=pk)
    services.move_list(organization_list, "up" if request.POST.get("direction") == "up" else "down")
    return redirect("organizations:lists")


@login_required
@require_POST
def toggle_list(request, pk):
    organization_list = get_object_or_404(OrganizationList, pk=pk)
    services.set_list_enabled(organization_list, not organization_list.enabled)
    return redirect("organizations:lists")


@login_required
@require_POST
def update_lists(request):
    results = loading.update_lists()
    failed = [pk for pk, ok in results.items() if not ok]
    if not results:
        messages.info(request, "No subscribed lists to update. Bundled lists change only with a new Unlist release.")
    elif failed:
        messages.error(
            request, f"{len(failed)} of {len(results)} lists could not be updated; their previous version is kept."
        )
    else:
        messages.success(request, f"Updated {len(results)} lists.")
    return redirect("organizations:lists")


@login_required
def pending_changes(request):
    changes = PendingContactChange.objects.select_related("organization")
    return render(request, "organizations/pending.html", {"changes": changes})


@login_required
@require_POST
def decide_change(request, pk):
    change = get_object_or_404(PendingContactChange, pk=pk)
    name = change.organization.name
    if request.POST.get("decision") == "accept":
        services.accept_contact_change(change)
        messages.success(request, f"New contact for {name} accepted.")
    else:
        services.reject_contact_change(change)
        messages.success(request, f"Kept the old contact for {name} as a local override.")
    return redirect("organizations:pending")
