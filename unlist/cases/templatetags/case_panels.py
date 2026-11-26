# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Panels on the Case page that work out their own context, so the detail view stays unchanged.

{% load case_panels %}{% recheck_panel case %}{% complaint_panel case %}
"""

from django import template

from unlist.cases import complaints, rechecks
from unlist.cases.lifecycle import State

register = template.Library()


@register.inclusion_tag("cases/_recheck_panel.html", takes_context=True)
def recheck_panel(context, case):
    from unlist.cases.recheck_views import EarlyRecheckForm

    resting = case.state == State.RESTING
    return {
        "case": case,
        "csrf_token": context.get("csrf_token"),
        "resting": resting,
        "suggestion": rechecks.early_recheck_suggestion(case) if resting else None,
        "returned_listing": rechecks.returned_listing(case),
        "early_form": EarlyRecheckForm() if resting else None,
    }


@register.inclusion_tag("cases/_complaint_panel.html")
def complaint_panel(case):
    if case.state not in complaints.COMPLAINT_STATES:
        return {"case": case, "shown": False}
    return {"case": case, "shown": True, "progress": complaints.progress(case)}
