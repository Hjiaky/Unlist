# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from unlist.cases import views

app_name = "cases"
urlpatterns = [
    path("", views.case_list, name="list"),
    path("new/", views.case_new, name="new"),
    path("<int:pk>/", views.case_detail, name="detail"),
    path("<int:pk>/action/<slug:action>/", views.case_action, name="action"),
    path("<int:pk>/outcome/", views.case_outcome, name="outcome"),
    path("<int:pk>/recheck/", views.case_recheck, name="recheck"),
    path("drafts/<int:pk>/approve/", views.draft_approve, name="draft_approve"),
    path("drafts/<int:pk>/discard/", views.draft_discard, name="draft_discard"),
    path("drafts/<int:pk>/sent/", views.draft_sent, name="draft_sent"),
    path("drafts/<int:pk>/edit/", views.draft_edit, name="draft_edit"),
    path("drafts/<int:pk>/eml/", views.draft_eml, name="draft_eml"),
    path("drafts/<int:pk>/letter/", views.draft_letter, name="draft_letter"),
    path("attachments/<int:pk>/", views.attachment_download, name="attachment"),
]
