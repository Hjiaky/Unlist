# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from unlist.subjects import views

app_name = "subjects"
urlpatterns = [
    path("", views.subject_list, name="list"),
    path("add/", views.subject_add, name="add"),
    path("<int:pk>/", views.subject_detail, name="detail"),
    path("<int:pk>/consent/", views.consent_record, name="consent"),
    path("<int:pk>/consent/withdraw/", views.consent_withdraw, name="consent_withdraw"),
    path("<int:pk>/details/add/", views.detail_add, name="detail_add"),
    path("<int:pk>/details/<int:detail_pk>/remove/", views.detail_remove, name="detail_remove"),
    path("<int:pk>/mailboxes/add/", views.mailbox_add, name="mailbox_add"),
    path("<int:pk>/delete/", views.subject_delete, name="delete"),
]
