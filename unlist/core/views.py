# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.static import serve

from unlist.core.middleware import operator_exists
from unlist.core.models import LoginFailure


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
        return redirect("home")
    return render(request, "unlist/setup.html", {"form": form})


@login_required
def home(request):
    return render(request, "unlist/home.html")


@require_GET
def static_file(request, path):
    response = serve(request, path, document_root=settings.STATIC_ROOT)
    response["Cache-Control"] = "public, max-age=86400"
    return response
