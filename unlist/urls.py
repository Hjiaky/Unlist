# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.urls import include, path, re_path

from unlist.core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("setup/", views.setup, name="setup"),
    path("login/", views.ThrottledLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("subjects/", include("unlist.subjects.urls")),
    path("organizations/", include("unlist.organizations.urls")),
    path("cases/", include("unlist.cases.urls")),
    path("mail/", include("unlist.mail.urls")),
    path("breaches/", include("unlist.breaches.urls")),
    path("statistics/", include("unlist.stats.urls")),
    path("llm/", include("unlist.llm.urls")),
    path("about/", include("unlist.legal.urls")),
    path("backup/", include("unlist.backup.urls")),
]

if not settings.DEBUG:
    # One household, one process: Django serves its own few static files rather than
    # adding a separate static-file server or package (Tao rules 1 and 7).
    urlpatterns.append(re_path(r"^static/(?P<path>.*)$", views.static_file))
