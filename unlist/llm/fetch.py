# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Fetch one public privacy-policy page, only when the Operator clicks "Find privacy contact".

Only ``http``/``https``, only hosts that resolve to public addresses (also after each
redirect, at most five), a size limit, and a User-Agent naming Unlist. The text is read with
the standard library's HTML parser (``unlist.cases.replies.html_to_text``).

Decided by agent (ticket #56): addresses on the Operator's own machine or network are refused,
so a pasted link cannot make the instance read its own private services.
"""

import ipaddress
import socket
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from unlist.cases.replies import html_to_text
from unlist.llm.client import USER_AGENT

TIMEOUT = 20
PAGE_MAX = 2 * 1024 * 1024  # bytes read
TEXT_MAX = 30_000  # characters of page text sent to the LLM
MAX_REDIRECTS = 5


class FetchError(RuntimeError):
    pass


def check_public_url(url: str) -> None:
    """Raise FetchError unless ``url`` is http(s) and its host resolves only to public addresses."""
    parts = urlsplit(url or "")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Enter an http:// or https:// address.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or None, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError) as error:
        raise FetchError(f"{parts.hostname} could not be found.") from error
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%", 1)[0])
        if not address.is_global:
            raise FetchError(f"{parts.hostname} is not a public address.")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_CheckedRedirect)


def urlopen(request, timeout):
    """The only place the page fetch opens a connection (tests replace it)."""
    return _OPENER.open(request, timeout=timeout)


def page_text(url: str) -> str:
    """The readable text of the page at ``url``, at most TEXT_MAX characters. Raises FetchError."""
    check_public_url(url)
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"}, method="GET"
    )
    try:
        with urlopen(request, TIMEOUT) as response:
            content_type = response.headers.get_content_type() if response.headers else "text/html"
            charset = (response.headers.get_content_charset() if response.headers else None) or "utf-8"
            data = response.read(PAGE_MAX + 1)
    except FetchError:
        raise
    except urllib.error.HTTPError as error:
        raise FetchError(f"The page answered HTTP {error.code}.") from error
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise FetchError(f"The page could not be fetched: {error}") from error
    if len(data) > PAGE_MAX:
        raise FetchError("The page is too large.")
    if content_type not in ("text/html", "application/xhtml+xml", "text/plain"):
        raise FetchError(f"The address is not a web page ({content_type}).")
    try:
        text = data.decode(charset, errors="replace")
    except LookupError:
        text = data.decode("utf-8", errors="replace")
    if content_type != "text/plain":
        text = html_to_text(text)
    text = text.strip()
    if not text:
        raise FetchError("The page has no text.")
    return text[:TEXT_MAX]
