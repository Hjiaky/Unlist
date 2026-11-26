# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
from django import template

from unlist.legal.views import source_url as current_source_url

register = template.Library()


@register.simple_tag
def source_url() -> str:
    return current_source_url()
