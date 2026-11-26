# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Writing and reading the monthly snapshots."""

from datetime import date

from django.utils import timezone

from unlist.stats import figures
from unlist.stats.models import MonthlySnapshot


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def record_snapshots(today: date, *, force: bool = False) -> bool:
    """Write (or rewrite) this month's snapshots. Once a day: a second call the same day does nothing.

    Returns whether anything was written. ``force`` skips the once-a-day check.
    """
    month = first_of_month(today)
    if not force:
        last = MonthlySnapshot.objects.filter(month=month, subject__isnull=True).first()
        if last is not None and timezone.localdate(last.updated_at) >= today:
            return False
    per_subject = figures.compute_all()
    rows = list(per_subject.items())
    rows.append((None, figures.combine(per_subject.values())))
    for subject_id, found in rows:
        MonthlySnapshot.objects.update_or_create(
            month=month,
            subject_id=subject_id,
            defaults={"holding": found.holding, "removed": found.removed, "counts": found.counts()},
        )
    return True


def history(subject_id: int | None, live: figures.Figures, today: date) -> list[tuple[date, int, int]]:
    """(month, holding, removed) for each earlier month with a snapshot, then the live current month."""
    current = first_of_month(today)
    rows = MonthlySnapshot.objects.filter(subject_id=subject_id, month__lt=current).order_by("month")
    result = [(row.month, row.holding, row.removed) for row in rows]
    result.append((current, live.holding, live.removed))
    return result
