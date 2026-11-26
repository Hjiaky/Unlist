# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The scheduler job that records the figures once a day. It only writes counts; it sends nothing."""

from django.utils import timezone

from unlist.core.scheduler import job
from unlist.stats import snapshots


@job
def record_monthly_snapshot(now):
    today = timezone.localdate(now) if timezone.is_aware(now) else now.date()
    if not snapshots.record_snapshots(today):
        return None
    return f"Statistics snapshot for {today:%Y-%m} written."
