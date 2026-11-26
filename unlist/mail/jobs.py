# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Opt-in scheduled re-scans of live mailboxes (spec section 5).

Only connections whose ``scheduled_rescans`` the Operator switched on, each at most once every
6 hours (counted from the last attempt, so a failing connection is not retried more often).
A re-scan reads mail; it never sends anything.
"""

import datetime

from django.db.models import Q

from unlist.core.scheduler import job

RESCAN_HOURS = 6
RESCAN_EVERY = datetime.timedelta(hours=RESCAN_HOURS)


def due_connections(now):
    from unlist.mail.models import MailboxConnection
    from unlist.subjects.models import Mailbox

    return (
        MailboxConnection.objects.filter(scheduled_rescans=True, mailbox__mode=Mailbox.Mode.LIVE)
        .filter(Q(last_attempt_at__isnull=True) | Q(last_attempt_at__lte=now - RESCAN_EVERY))
        .select_related("mailbox__subject")
        .order_by("last_attempt_at", "pk")
    )


@job
def rescan_live_mailboxes(now):
    from unlist.mail import imap, importer

    importer.clean_up_stale(now)  # a scan cut off by a restart must not block re-scans

    scanned = failed = 0
    for connection in due_connections(now):
        if imap.is_running(connection):
            continue
        run = imap.scan_connection(connection, now=now)
        if run.failure:
            failed += 1
        else:
            scanned += 1
    if not scanned and not failed:
        return None
    return f"{scanned} live mailbox(es) re-scanned, {failed} failed"
