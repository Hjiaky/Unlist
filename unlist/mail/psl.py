# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Registrable domains from the bundled Public Suffix List.

The list (`data/public_suffix_list.dat`, MPL-2.0, shipped unmodified) is parsed once, on
first use, with both its ICANN and PRIVATE sections: with the PRIVATE section,
`shop-a.myshopify.com` and `shop-b.myshopify.com` stay apart, which is what discovery wants
(docs/research/mailbox-discovery-signals.md).

The algorithm is the one in the list's `docs/format.md`: an exception rule (`!`) wins;
otherwise the matching rule with the most labels wins, a wildcard (`*.`) matching any one
label; with no match the rule is `*`. The registrable domain is the public suffix plus one
more label.
"""

from functools import cache
from pathlib import Path

PSL_FILE = Path(__file__).resolve().parent / "data" / "public_suffix_list.dat"


def _ascii_label(label):
    """One label, lowercased and Punycode-encoded, or None if it cannot be encoded."""
    label = label.lower()
    if label.isascii():
        return label
    try:
        return label.encode("idna").decode("ascii")
    except UnicodeError:
        return None


def _ascii_name(name):
    labels = [_ascii_label(label) for label in name.split(".")]
    if any(label is None for label in labels):
        return None
    return ".".join(labels)


@cache
def rules():
    """(normal rules, wildcard parents, exception rules) as sets of ASCII names."""
    normal, wildcard, exception = set(), set(), set()
    with open(PSL_FILE, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            rule = line.split()[0]
            if rule.startswith("!"):
                name = _ascii_name(rule[1:])
                target = exception
            elif rule.startswith("*."):
                name = _ascii_name(rule[2:])
                target = wildcard
            else:
                name = _ascii_name(rule)
                target = normal
            if name:
                target.add(name)
    return frozenset(normal), frozenset(wildcard), frozenset(exception)


def normalize_host(host):
    """The host lowercased and Punycode-encoded, without a trailing dot; None if it is not a host name."""
    if not isinstance(host, str):
        return None
    host = host.strip().rstrip(".")
    if not host or host.startswith(".") or ".." in host:
        return None
    return _ascii_name(host)


def public_suffix_length(labels):
    """How many labels at the end of `labels` form the public suffix."""
    normal, wildcard, exception = rules()
    count = len(labels)
    for i in range(count):
        if ".".join(labels[i:]) in exception:
            return count - i - 1
    for i in range(count):  # from the longest candidate down: the first hit has the most labels
        suffix = ".".join(labels[i:])
        if suffix in normal:
            return count - i
        if i + 1 < count and ".".join(labels[i + 1 :]) in wildcard:
            return count - i
    return 1  # the implicit "*" rule


def public_suffix(host):
    host = normalize_host(host)
    if host is None:
        return None
    labels = host.split(".")
    return ".".join(labels[len(labels) - public_suffix_length(labels) :])


def registrable_domain(host):
    """The registrable domain of a host (public suffix plus one label), or None.

    None for empty or malformed input and for a host that is itself a public suffix.
    The result is lowercase ASCII (Punycode for internationalized names).
    """
    host = normalize_host(host)
    if host is None:
        return None
    labels = host.split(".")
    length = public_suffix_length(labels)
    if len(labels) <= length:
        return None
    return ".".join(labels[len(labels) - length - 1 :])
