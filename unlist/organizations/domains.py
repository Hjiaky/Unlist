# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Domain helpers without the database.

A domain here is a lowercase host without a leading "www.". Its registrable domain comes
from the bundled Public Suffix List (`unlist.mail.psl`); callers that look a domain up also
try its parent domains down to the registrable domain (see `candidates`).
"""

import json
import re
import urllib.parse
from functools import cache
from pathlib import Path

from unlist.mail import psl

DATA_DIR = Path(__file__).resolve().parent / "data"
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")


def normalize_domain(value):
    """The domain of a URL, bare host or email address, or None if it is not a plausible domain."""
    value = (value or "").strip()
    if "@" in value and "/" not in value:
        host = value.rsplit("@", 1)[1]
    else:
        try:
            host = urllib.parse.urlsplit(value if "//" in value else f"//{value}").hostname or ""
        except ValueError:
            return None
    try:
        host = host.encode("idna").decode("ascii") if not host.isascii() else host
    except UnicodeError:
        return None
    host = host.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host if _DOMAIN_RE.match(host) else None


def registrable_domain(value):
    """The registrable domain (Public Suffix List) of a URL, host or email address, or None."""
    domain = normalize_domain(value)
    return psl.registrable_domain(domain) if domain else None


def candidates(domain):
    """The domain and its parents down to its registrable domain, most specific first.

    a.b.example.co.uk gives a.b.example.co.uk, b.example.co.uk, example.co.uk; a public
    suffix such as co.uk is never a candidate. A domain that is itself a public suffix
    gives just itself.
    """
    labels = domain.split(".")
    registrable = psl.registrable_domain(domain)
    if registrable is None:
        return [domain]
    return [".".join(labels[i:]) for i in range(len(labels) - registrable.count("."))]


def _ancestors(domain):
    """The domain and every parent with at least two labels, public suffixes included."""
    labels = domain.split(".")
    return [".".join(labels[i:]) for i in range(len(labels) - 1)]


@cache
def ambiguous_domains():
    with open(DATA_DIR / "ambiguous-domains.json", encoding="utf-8") as handle:
        return frozenset(json.load(handle)["domains"])


def is_ambiguous(domain):
    """True for shared mail and platform domains (and their subdomains), which identify no one Organization."""
    domain = normalize_domain(domain)
    if not domain:
        return False
    shared = ambiguous_domains()
    # All parents, not just down to the registrable domain: the list names platform suffixes
    # such as github.io, and their subdomains are shared too.
    return any(candidate in shared for candidate in _ancestors(domain))
