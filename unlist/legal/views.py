# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Legal notices. None of these pages needs a login: the notices must always be reachable."""

import os

from django.http import HttpResponse
from django.shortcuts import render

from unlist import __version__
from unlist.paths import BASE_DIR

COPYRIGHT = "Copyright (C) 2026 The Unlist contributors"
DEFAULT_SOURCE_URL = "https://github.com/Hjiaky/Unlist/tree/v{version}"

# Every script the pages load. The test suite checks that each <script src> of a rendered
# page is listed here.
SCRIPTS = [
    {
        "path": "unlist/htmx.min.js",
        "name": "htmx.min.js",
        "licence": "0BSD",
        "licence_file": "unlist/htmx.LICENSE.txt",
        "source": "https://github.com/bigskysoftware/htmx/tree/v2.0.11",
    },
]


def source_url() -> str:
    """Where the Corresponding Source of this running version can be had (AGPL section 13).

    The Operator of a modified instance sets UNLIST_SOURCE_URL to their own source.
    """
    custom = os.environ.get("UNLIST_SOURCE_URL", "").strip()
    if custom.lower().startswith(("http://", "https://")):
        return custom
    return DEFAULT_SOURCE_URL.format(version=__version__)


def _text(name: str) -> HttpResponse:
    text = (BASE_DIR / name).read_text(encoding="utf-8")
    return HttpResponse(text, content_type="text/plain; charset=utf-8")


def about(request):
    return render(
        request,
        "legal/about.html",
        {"version": __version__, "copyright": COPYRIGHT, "source_url": source_url()},
    )


def licence(request):
    return _text("LICENSE")


def notices(request):
    return _text("THIRD-PARTY-NOTICES")


def javascript(request):
    return render(request, "legal/javascript.html", {"scripts": SCRIPTS})
