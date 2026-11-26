# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The one HTTP client for the LLM endpoint: a plain ``urllib.request`` POST, no vendor SDK.

``chat(settings, messages)`` posts ``{"model", "messages", "temperature": 0}`` to
``<base>/chat/completions`` and returns the answer's text. It refuses to run unless the
settings are usable (enabled, and for a remote endpoint the notice accepted), so nothing leaves
the instance unless the Operator turned it on. Redirects are not followed: the API key must
never reach another host.

Callers catch :class:`LlmError` (which :class:`LlmUnavailable` is a kind of) and fall back to
what Unlist does without an LLM.
"""

import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlsplit

import unlist
from unlist.llm import endpoint

log = logging.getLogger("unlist.llm")

TIMEOUT = 60  # seconds; local models on modest hardware are slow
REQUEST_MAX = 128 * 1024  # bytes of JSON sent
RESPONSE_MAX = 256 * 1024  # bytes of JSON read
ANSWER_MAX = 32_000  # characters of answer kept
USER_AGENT = f"Unlist/{unlist.__version__} (self-hosted personal-data removal; LLM client)"


class LlmError(RuntimeError):
    """The endpoint could not be used or gave no usable answer."""


class LlmUnavailable(LlmError):
    """The LLM is switched off, not set up, or remote with the notice not yet accepted."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # urllib then raises HTTPError for the 3xx answer


_OPENER = urllib.request.build_opener(_NoRedirect)


def urlopen(request, timeout):
    """The only place the LLM client opens a connection (tests replace it)."""
    return _OPENER.open(request, timeout=timeout)


def chat(settings, messages: list[dict], *, timeout: float = TIMEOUT) -> str:
    """The endpoint's answer to ``messages`` (a list of ``{"role", "content"}``). Raises LlmError."""
    if settings is None or not settings.usable:
        raise LlmUnavailable("The LLM is not switched on.")
    url = endpoint.chat_url(settings.base_url)
    if urlsplit(url).scheme not in ("http", "https"):
        raise LlmUnavailable("The LLM address must start with http:// or https://.")
    payload = {
        "model": settings.model,
        "messages": [{"role": str(item["role"]), "content": str(item["content"])} for item in messages],
        "temperature": 0,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(data) > REQUEST_MAX:
        raise LlmError("The request to the LLM is too large.")
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT}
    try:
        key = settings.api_key()
    except Exception as error:  # crypto.MissingKey / WrongKey: do not send without the key it needs
        raise LlmError(f"The stored API key cannot be read: {error}") from error
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(request, timeout) as response:
            body = response.read(RESPONSE_MAX + 1)
    except urllib.error.HTTPError as error:
        raise LlmError(f"The LLM endpoint answered HTTP {error.code}.") from error
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise LlmError(f"The LLM endpoint could not be reached: {error}") from error
    if len(body) > RESPONSE_MAX:
        raise LlmError("The LLM's answer is too large.")
    try:
        content = json.loads(body.decode("utf-8", errors="replace"))["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise LlmError("The LLM's answer is not in the OpenAI chat format.") from error
    if not isinstance(content, str):
        raise LlmError("The LLM's answer has no text.")
    return content[:ANSWER_MAX]


def parse_json_object(text: str) -> dict:
    """The first JSON object in a model's answer (models like to wrap it in prose or code fences)."""
    start = text.find("{")
    while start != -1:
        try:
            found, _ = json.JSONDecoder().raw_decode(text[start:])
        except ValueError:
            start = text.find("{", start + 1)
            continue
        if isinstance(found, dict):
            return found
        start = text.find("{", start + 1)
    raise LlmError("The LLM's answer holds no JSON object.")
