# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path, register_converter

from unlist.llm import views


class LeftoverKind:
    regex = "discovery|sender"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(LeftoverKind, "leftover")

app_name = "llm"
urlpatterns = [
    path("", views.settings_page, name="settings"),
    path("accept-notice/", views.accept_notice, name="accept_notice"),
    path("sort/<leftover:kind>/<int:pk>/", views.sort_leftover, name="sort"),
    path("sort/<leftover:kind>/<int:pk>/apply/", views.apply_evidence, name="apply_evidence"),
    path("drafts/<int:pk>/adapt/", views.adapt_draft, name="adapt_draft"),
    path("drafts/<int:pk>/accept/", views.accept_draft, name="accept_draft"),
    path("organizations/<slug:slug>/contact/", views.find_contact, name="find_contact"),
    path("organizations/<slug:slug>/contact/confirm/", views.confirm_contact, name="confirm_contact"),
]
