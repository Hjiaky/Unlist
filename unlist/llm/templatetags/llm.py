# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Small LLM buttons for other apps' pages. Each renders nothing unless the LLM is usable.

{% load llm %}
{% llm_sort_button "discovery" discovery %}   {# or "sender" with an UnassignedSender #}
{% llm_adapt_button draft %}
{% llm_contact_link organization %}
"""

from django import template

from unlist.llm import jobs
from unlist.llm.models import LlmSettings
from unlist.mail import scanner

register = template.Library()


def _settings(context) -> LlmSettings:
    """Read once per page render, however many rows ask."""
    cache = context.render_context
    if "llm_settings" not in cache:
        cache["llm_settings"] = LlmSettings.load()
    return cache["llm_settings"]


@register.inclusion_tag("llm/_sort_button.html", takes_context=True)
def llm_sort_button(context, kind, item):
    shown = _settings(context).usable and item.evidence == scanner.NONE
    return {"shown": shown, "kind": kind, "item": item, "csrf_token": context.get("csrf_token")}


@register.inclusion_tag("llm/_adapt_button.html", takes_context=True)
def llm_adapt_button(context, draft):
    lang = jobs.adapt_target(draft) if _settings(context).usable else None
    return {
        "shown": lang is not None,
        "draft": draft,
        "language": jobs.language_name(lang) if lang else "",
        "csrf_token": context.get("csrf_token"),
    }


@register.inclusion_tag("llm/_contact_link.html", takes_context=True)
def llm_contact_link(context, organization):
    return {"shown": _settings(context).usable, "organization": organization}
