# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.db import models


class LoginFailure(models.Model):
    """One failed login, kept briefly for throttling (spec section 14)."""

    address = models.GenericIPAddressField()
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["address", "at"])]
