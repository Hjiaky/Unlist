# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Lookups other apps use: which Organization a domain or slug belongs to."""

from unlist.organizations.domains import candidates, normalize_domain
from unlist.organizations.domains import is_ambiguous as _is_ambiguous
from unlist.organizations.merge import MAX_REDIRECTS, domain_owners
from unlist.organizations.models import Domain, Organization


def is_ambiguous(domain):
    """True for shared mail and platform domains, which never identify one Organization."""
    return _is_ambiguous(domain)


def get(slug):
    """The Organization with this slug, following obsolete redirects. None if unknown or defunct."""
    organization = Organization.objects.filter(slug=slug).first()
    for _ in range(MAX_REDIRECTS):
        if organization is None or not organization.obsolete:
            return organization
        if not organization.redirect_to:
            return None
        organization = Organization.objects.filter(slug=organization.redirect_to).first()
    return None


def by_domain(domain):
    """The Organization a domain (or URL, or email address) belongs to.

    Tries the domain, then its parent domains. Returns None for shared mail and platform
    domains, for domains claimed by more than one Organization (until a local override
    settles it), and for unknown domains.
    """
    domain = normalize_domain(domain)
    if not domain or _is_ambiguous(domain):
        return None
    for candidate in candidates(domain):
        claims = list(Domain.objects.filter(domain=candidate).values_list("domain", "source_id", "organization__slug"))
        if claims:
            owner = domain_owners(claims)[candidate]
            return get(owner) if owner else None
    return None
