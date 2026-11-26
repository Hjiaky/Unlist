# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Host and port presets for live connections, from ``data/mail-providers.json``."""

import json
from functools import cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "mail-providers.json"
# Microsoft account mail domains and servers: they generally need OAuth for IMAP (not supported).
MICROSOFT_DOMAINS = frozenset({"outlook.com", "hotmail.com", "live.com", "msn.com", "outlook.de", "hotmail.de"})
MICROSOFT_HOSTS = ("outlook.office365.com", "smtp-mail.outlook.com", "smtp.office365.com")


@cache
def presets():
    with open(DATA_FILE, encoding="utf-8") as handle:
        return {provider["key"]: provider for provider in json.load(handle)["providers"]}


def get(key):
    return presets().get(key or "")


def for_address(address):
    """The preset whose domains include the address's domain, or None."""
    domain = (address or "").rpartition("@")[2].lower()
    for provider in presets().values():
        if domain in provider["domains"]:
            return provider
    return None


def looks_like_microsoft(address="", *hosts):
    domain = (address or "").rpartition("@")[2].lower()
    return domain in MICROSOFT_DOMAINS or any((host or "").lower().endswith(MICROSOFT_HOSTS) for host in hosts)
