# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from unlist.organizations import views

app_name = "organizations"
urlpatterns = [
    path("", views.organization_list, name="index"),
    path("o/<slug:slug>/", views.organization_detail, name="detail"),
    path("o/<slug:slug>/override/", views.add_override, name="add_override"),
    path("o/<slug:slug>/override/<int:pk>/delete/", views.delete_override, name="delete_override"),
    path("o/<slug:slug>/export/", views.export_contribution, name="export"),
    path("lists/", views.lists, name="lists"),
    path("lists/add/", views.add_list, name="add_list"),
    path("lists/update/", views.update_lists, name="update_lists"),
    path("lists/<int:pk>/remove/", views.remove_list, name="remove_list"),
    path("lists/<int:pk>/move/", views.move_list, name="move_list"),
    path("lists/<int:pk>/toggle/", views.toggle_list, name="toggle_list"),
    path("pending/", views.pending_changes, name="pending"),
    path("pending/<int:pk>/", views.decide_change, name="decide_change"),
]
