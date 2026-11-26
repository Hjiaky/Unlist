# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from unlist.stats import views

app_name = "stats"
urlpatterns = [
    path("", views.index, name="index"),
]
