# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from unlist.breaches import catalogue, matching
from unlist.breaches.models import Breach, BreachAssignment, BreachCatalogue
from unlist.organizations.models import Organization
from unlist.subjects.models import Subject

PAGE_SIZE = 50
SEARCH_LIMIT = 20


@login_required
def index(request):
    context = {
        "catalogue": BreachCatalogue.objects.filter(pk=1).first(),
        "subjects": Subject.objects.all(),
        "assignments": BreachAssignment.objects.count(),
    }
    return render(request, "breaches/index.html", context)


@login_required
@require_POST
def update(request):
    try:
        count = catalogue.fetch_catalogue()
    except catalogue.CatalogueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Breach list updated from Have I Been Pwned: {count} breaches.")
    return redirect("breaches:index")


@login_required
def subject_breaches(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    context = {
        "subject": subject,
        "rows": matching.rows_for_subject(subject),
        "catalogue": BreachCatalogue.objects.filter(pk=1).first(),
        "not_a_claim": matching.NOT_A_CLAIM,
    }
    return render(request, "breaches/subject.html", context)


@login_required
def assign_list(request):
    """Breaches without a domain, which no Organization can claim by domain, with their hand assignments."""
    query = request.GET.get("q", "").strip()
    breaches = matching.usable_breaches().filter(domain="")
    if query:
        breaches = breaches.filter(Q(title__icontains=query) | Q(name__icontains=query))
    page = Paginator(breaches, PAGE_SIZE).get_page(request.GET.get("page"))
    assigned = {
        a.breach_name: a.organization
        for a in BreachAssignment.objects.filter(breach_name__in=[b.name for b in page]).select_related("organization")
    }
    for breach in page:
        breach.assigned_to = assigned.get(breach.name)
    return render(request, "breaches/assign_list.html", {"page": page, "query": query})


@login_required
def assign_detail(request, name):
    breach = get_object_or_404(Breach, name=name)
    if request.method == "POST":
        organization = Organization.objects.filter(slug=request.POST.get("organization", ""), obsolete=False).first()
        if breach.excluded:
            messages.error(request, "Spam lists, malware and fabricated breaches are never matched.")
        elif organization is None:
            messages.error(request, "Choose an Organization.")
        else:
            BreachAssignment.objects.update_or_create(breach_name=breach.name, defaults={"organization": organization})
            messages.success(request, f"{breach.title} is now assigned to {organization.name}.")
            return redirect("breaches:assign", name=breach.name)
    query = request.GET.get("q", "").strip()
    organizations = []
    if query:
        organizations = list(
            Organization.objects.filter(obsolete=False)
            .filter(Q(name__icontains=query) | Q(slug__icontains=query) | Q(domains__icontains=query))
            .order_by("name")[:SEARCH_LIMIT]
        )
    context = {
        "breach": breach,
        "assignment": BreachAssignment.objects.filter(breach_name=breach.name).select_related("organization").first(),
        "query": query,
        "organizations": organizations,
        "limit": SEARCH_LIMIT,
    }
    return render(request, "breaches/assign.html", context)


@login_required
@require_POST
def assign_remove(request, name):
    BreachAssignment.objects.filter(breach_name=name).delete()
    messages.success(request, "Assignment removed.")
    return redirect("breaches:assign", name=name)
