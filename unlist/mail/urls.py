# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from unlist.mail import views

app_name = "mail"
urlpatterns = [
    path("subjects/<int:pk>/import/", views.upload, name="upload"),
    path("subjects/<int:pk>/discoveries/", views.discoveries, name="discoveries"),
    path("subjects/<int:pk>/discoveries/pursue-all/", views.pursue_all, name="pursue_all"),
    path("subjects/<int:pk>/discoveries/<int:discovery_pk>/pursue/", views.pursue, name="pursue"),
    path("subjects/<int:pk>/discoveries/<int:discovery_pk>/ignore/", views.ignore, name="ignore"),
    path("subjects/<int:pk>/discoveries/<int:discovery_pk>/unignore/", views.unignore, name="unignore"),
    path("subjects/<int:pk>/unassigned/", views.unassigned, name="unassigned"),
    path("subjects/<int:pk>/unassigned/<int:sender_pk>/assign/", views.assign, name="assign"),
    path("subjects/<int:pk>/unassigned/<int:sender_pk>/ignore/", views.ignore_sender, name="ignore_sender"),
    path("subjects/<int:pk>/unassigned/<int:sender_pk>/unignore/", views.unignore_sender, name="unignore_sender"),
]
