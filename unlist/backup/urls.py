# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from unlist.backup import views

app_name = "backup"
urlpatterns = [
    path("", views.overview, name="overview"),
    path("download/", views.download, name="download"),
]
