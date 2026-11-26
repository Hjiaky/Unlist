# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Whether an endpoint address is local (a model the Operator runs) or remote. Pure: no database.

Local: ``localhost`` (and ``*.localhost``), loopback addresses (127.0.0.0/8, ::1), the private
ranges of RFC 1918 (10/8, 172.16/12, 192.168/16) and IPv6 unique local addresses (fc00::/7),
names under ``.local``, ``.lan``, ``.internal`` and ``.home.arpa``, and single-label names (a
container name such as ``ollama`` on the same Docker network). Everything else is remote. The
Operator can override the result either way.

Decided by agent (ticket #56): fc00::/7, ``.internal``, ``.home.arpa`` and single-label names
count as local, as the private-network equivalents of the ranges and names the ticket lists.
"""

import ipaddress
from urllib.parse import urlsplit

LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)
LOCAL_SUFFIXES = (".localhost", ".local", ".lan", ".internal", ".home.arpa")


def host_of(url: str) -> str:
    """The host name of ``url`` in lower case, without a trailing dot; "" if there is none."""
    try:
        host = urlsplit((url or "").strip()).hostname or ""
    except ValueError:
        return ""
    return host.lower().rstrip(".")


def is_local_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".").strip("[]")
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host == "localhost" or host.endswith(LOCAL_SUFFIXES) or "." not in host
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return any(address in network for network in LOCAL_NETWORKS)


def is_local_url(url: str) -> bool:
    """True for an address that points at the Operator's own machine or network. No host: not local."""
    return is_local_host(host_of(url))


def chat_url(base_url: str) -> str:
    """``<base>/chat/completions`` for an OpenAI-compatible base URL such as ``http://localhost:11434/v1``."""
    return (base_url or "").strip().rstrip("/") + "/chat/completions"
