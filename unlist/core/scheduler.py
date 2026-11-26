# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The scheduler only prepares work; it never sends anything (spec section 8).

Later tickets register jobs here: marking overdue Cases, preparing due re-checks and
reminder suggestions, opt-in IMAP re-scans. Each job is a function taking `now` and
returning a short summary string (or None when it had nothing to do).
"""

import logging

log = logging.getLogger("unlist.scheduler")

JOBS = []


def job(func):
    JOBS.append(func)
    return func


def run_once(now):
    results = {}
    for func in JOBS:
        try:
            results[func.__name__] = func(now)
        except Exception:  # one failing job must not stop the others
            log.exception("Scheduler job %s failed", func.__name__)
            results[func.__name__] = "failed"
    return results
