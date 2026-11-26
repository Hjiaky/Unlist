# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from unlist.breaches import views

app_name = "breaches"
urlpatterns = [
    path("", views.index, name="index"),
    path("update/", views.update, name="update"),
    path("subjects/<int:pk>/", views.subject_breaches, name="subject"),
    path("assign/", views.assign_list, name="assign_list"),
    path("assign/<str:name>/", views.assign_detail, name="assign"),
    path("assign/<str:name>/remove/", views.assign_remove, name="assign_remove"),
]
