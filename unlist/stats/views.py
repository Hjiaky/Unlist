# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from unlist.cases import lifecycle
from unlist.stats import charts, figures, snapshots
from unlist.subjects.models import Subject


def cases_url(subject_id=None, state=None, **filters) -> str:
    """The Case list with the exact filters behind a figure: Subject, state, result, Organization."""
    query = {}
    if subject_id:
        query["subject"] = subject_id
    if state:
        query["state"] = state
    query.update({name: value for name, value in filters.items() if value})
    return reverse("cases:list") + (f"?{urlencode(query)}" if query else "")


def _with_query(url, **params) -> str:
    return f"{url}?{urlencode(params)}"


def _fmt_days(value) -> str:
    return f"{value:g}"


@login_required
def index(request):
    subjects = list(Subject.objects.all())
    try:
        subject_id = int(request.GET.get("subject", ""))
    except ValueError:
        subject_id = None
    selected = next((subject for subject in subjects if subject.pk == subject_id), None)
    subject_id = selected.pk if selected else None

    per_subject = figures.compute_all()
    shown = [selected] if selected else subjects
    found = figures.combine(per_subject[subject.pk] for subject in shown)

    evidence_columns = [
        {"subject": subject, "url": reverse("mail:discoveries", args=[subject.pk]), "figures": per_subject[subject.pk]}
        for subject in shown
    ]
    evidence_rows = [
        {
            "label": figures.EVIDENCE_LABELS[kind],
            "cells": [
                (column["figures"].evidence[kind], _with_query(column["url"], evidence=kind))
                for column in evidence_columns
            ],
        }
        for kind in figures.EVIDENCE_ORDER
    ]
    discovery_rows = [
        {"label": "All Organizations found", "cells": [(c["figures"].discoveries, c["url"]) for c in evidence_columns]},
        {
            "label": "Of them Brokers",
            "cells": [(c["figures"].brokers, _with_query(c["url"], broker="yes")) for c in evidence_columns],
        },
    ]

    state_rows = [
        {
            "label": lifecycle.STATE_LABELS[lifecycle.State(state)],
            "count": found.cases_by_state[state],
            "url": cases_url(subject_id, state),
        }
        for state in figures.STATE_ORDER
        if found.cases_by_state[state]
    ]
    all_cases_url = cases_url(subject_id)
    outcome_rows = [
        {
            "label": figures.OUTCOME_LABELS[outcome],
            "count": found.outcomes[outcome],
            "url": cases_url(subject_id, result=outcome),
        }
        for outcome in figures.OUTCOME_LABELS
    ]

    today = timezone.localdate()
    points = snapshots.history(subject_id, found, today)
    who = selected.name if selected else "the household"
    chart = charts.line_chart(
        points,
        uid="stats-history",
        title=f"Organizations holding data and removed, by month, for {who}",
        description="Two lines by month: Organizations holding the data, and Organizations that removed it. "
        + "; ".join(f"{charts.month_label(m)}: {h} holding, {r} removed" for m, h, r in points)
        + ".",
    )

    organization_rows = []
    for row in figures.organization_figures():
        organization_rows.append(
            {
                "organization": row.organization,
                "url": reverse("organizations:detail", args=[row.organization.slug]),
                "cases_url": cases_url(organization=row.organization.slug),
                "cases": row.cases,
                "median": _fmt_days(row.median_days) if row.median_days is not None else None,
                "answered": row.answered,
                "on_time": f"{row.on_time} of {row.answered} ({row.on_time_percent}%)" if row.answered else None,
                "id_demands": row.id_demands,
            }
        )

    context = {
        "subjects": subjects,
        "selected": selected,
        "found": found,
        "columns": evidence_columns,
        "evidence_rows": evidence_rows,
        "discovery_rows": discovery_rows,
        "state_rows": state_rows,
        "all_cases_url": all_cases_url,
        "outcome_rows": outcome_rows,
        "removed_confirmed": found.removed_confirmed,
        "removed_confirmed_url": cases_url(subject_id, result="removed_suppression"),
        "removed_url": cases_url(subject_id, result=figures.REMOVED),
        "chart": mark_safe(chart),  # noqa: S308  (built by charts.line_chart, which escapes every text)
        "organization_rows": organization_rows,
    }
    return render(request, "stats/index.html", context)
