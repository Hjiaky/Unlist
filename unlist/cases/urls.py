# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.urls import path

from unlist.cases import complaint_views, recheck_views, views

app_name = "cases"
urlpatterns = [
    path("", views.case_list, name="list"),
    path("new/", views.case_new, name="new"),
    path("<int:pk>/", views.case_detail, name="detail"),
    path("<int:pk>/action/<slug:action>/", views.case_action, name="action"),
    path("<int:pk>/outcome/", views.case_outcome, name="outcome"),
    path("<int:pk>/recheck/", views.case_recheck, name="recheck"),
    path("<int:pk>/reply-upload/", views.case_reply_upload, name="reply_upload"),
    path("<int:pk>/details/", views.case_details, name="details"),
    path("<int:pk>/send-id/", views.case_send_id, name="send_id"),
    path("<int:pk>/portal/", views.case_portal, name="portal"),
    path("<int:pk>/authority-letter/", views.case_authority_letter, name="authority_letter"),
    path("authority-letters/<int:pk>/", views.authority_letter_show, name="authority_letter_show"),
    path("replies/", views.reply_queue, name="replies"),
    path("replies/<int:pk>/confirm/", views.reply_confirm, name="reply_confirm"),
    path("replies/<int:pk>/dismiss/", views.reply_dismiss, name="reply_dismiss"),
    path("replies/<int:pk>/assign/", views.reply_assign, name="reply_assign"),
    path("drafts/<int:pk>/approve/", views.draft_approve, name="draft_approve"),
    path("drafts/<int:pk>/discard/", views.draft_discard, name="draft_discard"),
    path("drafts/<int:pk>/sent/", views.draft_sent, name="draft_sent"),
    path("drafts/<int:pk>/edit/", views.draft_edit, name="draft_edit"),
    path("drafts/<int:pk>/eml/", views.draft_eml, name="draft_eml"),
    path("drafts/<int:pk>/letter/", views.draft_letter, name="draft_letter"),
    path("attachments/<int:pk>/", views.attachment_download, name="attachment"),
    # Re-checks (#51)
    path("<int:pk>/early-recheck/", recheck_views.early_recheck, name="early_recheck"),
    # Complaints (#52)
    path("<int:pk>/complaint/", complaint_views.complaint, name="complaint"),
    path("<int:pk>/complaint/authority/", complaint_views.complaint_authority, name="complaint_authority"),
    path("<int:pk>/complaint/uk/<slug:step>/", complaint_views.complaint_uk, name="complaint_uk"),
    path("<int:pk>/complaint/uk-complaint.eml", complaint_views.complaint_uk_eml, name="complaint_uk_eml"),
    path("<int:pk>/complaint/evidence.zip", complaint_views.complaint_evidence, name="complaint_evidence"),
    path("<int:pk>/complaint/lodged/", complaint_views.complaint_lodged, name="complaint_lodged"),
]
