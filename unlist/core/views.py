# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.static import serve

from unlist.cases import services as case_services
from unlist.cases.lifecycle import State
from unlist.cases.models import Case, Draft
from unlist.core import household
from unlist.core.middleware import operator_exists
from unlist.core.models import LoginFailure
from unlist.subjects.consent import ConsentRequired
from unlist.subjects.models import Subject


def client_address(request) -> str:
    """The client's address. Behind the Operator's reverse proxy, the last hop it appended."""
    if settings.BEHIND_PROXY:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _recent_failures(address):
    since = timezone.now() - timedelta(seconds=settings.LOGIN_FAILURE_WINDOW_SECONDS)
    return LoginFailure.objects.filter(address=address, at__gte=since)


class ThrottledLoginView(LoginView):
    template_name = "unlist/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if _recent_failures(client_address(request)).count() >= settings.LOGIN_MAX_FAILURES:
            minutes = settings.LOGIN_FAILURE_WINDOW_SECONDS // 60
            return render(request, "unlist/login_blocked.html", {"minutes": minutes}, status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        LoginFailure.objects.create(address=client_address(self.request))
        # Keep the table small: drop anything older than the window.
        cutoff = timezone.now() - timedelta(seconds=settings.LOGIN_FAILURE_WINDOW_SECONDS)
        LoginFailure.objects.filter(at__lt=cutoff).delete()
        return super().form_invalid(form)

    def form_valid(self, form):
        _recent_failures(client_address(self.request)).delete()
        return super().form_valid(form)


class OperatorCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)


def setup(request):
    """First run: create the one Operator account. Gone once it exists."""
    if operator_exists():
        return redirect("login")
    form = OperatorCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if operator_exists():  # someone else finished setup first
                return redirect("login")
            user = form.save()
        login(request, user)
        # First run (spec section 13): add a Subject, record consent, import mail, see what was found.
        return redirect("subjects:add")
    return render(request, "unlist/setup.html", {"form": form})


@login_required
def home(request):
    """ "Needs you": what waits for the Operator across the household, as a table or a board."""
    view, remember = household.chosen_view(request)
    context = {"view": view, "first_run": household.first_run(), **household.needs_you()}
    context["reply_total"] = len(context["replies"]) + len(context["unmatched"])
    context["empty"] = not any(
        context[key] for key in ("drafts", "replies", "unmatched", "attention", "contact_changes", "finds")
    )
    if view == "board":
        replies_for = household.reply_case_ids()
        cases = Case.objects.select_related("subject", "organization").order_by("subject__name", "organization__name")
        found = household.new_discoveries()
        context["columns"] = household.board(
            household.case_rows(cases, replies_for, context["drafts"]),
            found,
            found_total=len(found),
            more_urls={
                "resting": reverse("cases:list") + f"?state={State.RESTING.value}",
                "closed": reverse("cases:list") + f"?state={State.CLOSED.value}",
            },
        )
    response = render(request, "unlist/home.html", context)
    return household.remember_view(response, view) if remember else response


def _selected_drafts(request):
    ids = []
    for value in request.POST.getlist("draft"):
        try:
            ids.append(int(value))
        except ValueError:
            continue
    drafts = Draft.objects.filter(pk__in=ids).select_related("case", "case__subject", "case__organization")
    return list(drafts.order_by("case__subject__name", "case__organization__name", "id"))


@login_required
@require_POST
def approve_batch(request):
    """Approve several drafts: one summary screen listing every recipient, then approve each.

    The first POST (the drafts ticked on "Needs you") shows the summary; the second, with
    ``confirm``, approves each draft through ``cases.services.approve``. A draft that cannot be
    approved is reported by itself and does not stop the others.
    """
    drafts = _selected_drafts(request)
    if not drafts:
        messages.error(request, "Tick the drafts to approve first.")
        return redirect("home")
    if request.POST.get("confirm") != "yes":
        items = [{"draft": draft, **household.delivery(draft)} for draft in drafts]
        return render(request, "unlist/approve_summary.html", {"items": items})
    for draft in drafts:
        try:
            case_services.approve(draft)
        except (case_services.CaseError, ConsentRequired) as error:
            messages.error(request, f"{draft.case.reference} ({draft.case.organization.name}): not approved. {error}")
        else:
            draft.refresh_from_db()
            how = "sent by Unlist" if draft.status == Draft.Status.SENT else "handed over to the Subject"
            messages.success(request, f"{draft.case.reference}: approved, {how} (to {draft.recipient}).")
    return redirect("home")


@login_required
def settings_page(request):
    """Settings: links to the few things that can be set. Each lives on its own page."""
    return render(request, "unlist/settings.html", {"subjects": Subject.objects.prefetch_related("mailboxes")})


@require_GET
def static_file(request, path):
    response = serve(request, path, document_root=settings.STATIC_ROOT)
    response["Cache-Control"] = "public, max-age=86400"
    return response
