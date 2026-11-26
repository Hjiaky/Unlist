# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The sidebar of every logged-in page (#53): the Subjects and what waits for the Operator."""

from django.utils.functional import SimpleLazyObject

from unlist.core import household

# URL namespaces whose ``pk`` is a Subject's, so the sidebar can mark the Subject being viewed.
SUBJECT_NAMESPACES = {"subjects", "mail"}

# Which sidebar entry a page belongs to, by URL namespace (or full view name, which wins).
SECTIONS = {
    "home": "needs",
    "approve": "needs",
    "cases:replies": "needs",
    "stats": "stats",
    "cases": "cases",
    "organizations": "organizations",
    "organizations:lists": "lists",
    "breaches": "breaches",
    "settings": "settings",
    "llm": "settings",
    "backup": "settings",
    "mail:connections": "settings",
}


def section_of(match) -> str:
    if match is None:
        return ""
    return SECTIONS.get(match.view_name) or SECTIONS.get(match.namespace, "")


def sidebar(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    match = getattr(request, "resolver_match", None)
    current = None
    if match is not None and "pk" in match.kwargs:
        if match.namespace in SUBJECT_NAMESPACES or match.view_name == "breaches:subject":
            current = match.kwargs["pk"]
    return {
        # Lazy: computed only when a template shows the sidebar (four small queries).
        "sidebar": SimpleLazyObject(household.sidebar),
        "current_subject_id": current,
        "nav_section": "" if current else section_of(match),
    }
