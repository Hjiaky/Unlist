# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django.db import models


class MonthlySnapshot(models.Model):
    """The figures of one month, so that the chart has a history from day one (spec section 11).

    One row per Subject and month, and one household row (``subject`` empty). The current
    month's row is rewritten once a day; earlier months keep the last figures written in them.
    Only counts are kept, never a name.
    """

    month = models.DateField(help_text="The first day of the month.")
    subject = models.ForeignKey(
        "subjects.Subject",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="Empty for the household total.",
    )
    holding = models.PositiveIntegerField(help_text="Organizations holding the Subject's data.")
    removed = models.PositiveIntegerField(help_text="Organizations that removed it.")
    counts = models.JSONField(default=dict, blank=True, help_text="The other figures, as the page shows them.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["month", "subject_id"]
        constraints = [
            models.UniqueConstraint(fields=["month", "subject"], name="snapshot_unique_per_subject_and_month"),
            models.UniqueConstraint(
                fields=["month"],
                condition=models.Q(subject__isnull=True),
                name="snapshot_unique_household_per_month",
            ),
        ]

    def __str__(self):
        return f"{self.month:%Y-%m} {self.subject or 'household'}"
