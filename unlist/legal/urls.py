# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from . import views

app_name = "legal"
urlpatterns = [
    path("", views.about, name="about"),
    path("licence/", views.licence, name="licence"),
    path("notices/", views.notices, name="notices"),
    path("javascript/", views.javascript, name="javascript"),
]
