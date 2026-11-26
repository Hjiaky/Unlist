# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Deleting a Subject erases everything about them."""

from django.db import transaction

# Callables `f(subject)` run before the delete. Later apps register here to remove files (attachments) they store.
before_delete = []


def delete_subject(subject):
    with transaction.atomic():
        for hook in list(before_delete):
            hook(subject)
        subject.delete()  # every FK to Subject is CASCADE
