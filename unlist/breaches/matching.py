# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Which breaches belong to which Organization, and when a breach fell against a Subject's mail history."""

import datetime

from unlist.breaches.models import Breach, BreachAssignment
from unlist.organizations import lookup
from unlist.organizations.domains import registrable_domain
from unlist.organizations.models import Domain

WHILE, BEFORE, AFTER, UNKNOWN = "while", "before", "after", "unknown"

TIMING_TEXT = {
    WHILE: "While the Subject was known to them",
    BEFORE: "Before the Subject was known to them",
    AFTER: "After the Subject was last seen there",
    UNKNOWN: "Cannot compare: no breach date or no mail dates",
}

NOT_A_CLAIM = (
    "This does not mean the Subject's own address was in the breach. Unlist never checks an address; "
    "it only shows breaches at Organizations that hold or held the Subject's data."
)


def timing(breach_date, first_seen, last_seen):
    """WHILE, BEFORE, AFTER or UNKNOWN: where the breach date falls within first_seen..last_seen (by day)."""
    if breach_date is None or (first_seen is None and last_seen is None):
        return UNKNOWN
    first = first_seen.date() if first_seen else None
    last = last_seen.date() if last_seen else None
    if first and breach_date < first:
        return BEFORE
    if last and breach_date > last:
        return AFTER
    return WHILE


def usable_breaches():
    """Breaches that may be matched: not spam lists, malware or fabricated."""
    return Breach.objects.filter(is_spam_list=False, is_malware=False, is_fabricated=False)


def organization_for(breach):
    """The Organization a breach belongs to: a hand assignment, else its domain. None if neither."""
    if breach.excluded:
        return None
    assignment = BreachAssignment.objects.filter(breach_name=breach.name).select_related("organization").first()
    if assignment:
        return assignment.organization
    return lookup.by_domain(breach.domain) if breach.domain else None


def breaches_for_organizations(organizations):
    """{organization pk: [Breach, ...]} for these Organizations."""
    wanted = {organization.pk for organization in organizations}
    found = {pk: [] for pk in wanted}
    if not wanted:
        return found
    assigned = {
        assignment.breach_name: assignment.organization_id
        for assignment in BreachAssignment.objects.filter(organization_id__in=wanted)
    }
    # A hand assignment wins over the domain, so a breach assigned elsewhere is skipped here.
    handled = set(BreachAssignment.objects.values_list("breach_name", flat=True))
    # Only breaches whose registrable domain some wanted Organization claims need the full lookup.
    claimed = {
        registrable_domain(domain)
        for domain in Domain.objects.filter(organization_id__in=wanted).values_list("domain", flat=True)
    }
    claimed.discard(None)
    for breach in usable_breaches():
        if breach.name in assigned:
            found[assigned[breach.name]].append(breach)
        elif breach.name not in handled and breach.domain and registrable_domain(breach.domain) in claimed:
            owner = lookup.by_domain(breach.domain)
            if owner and owner.pk in wanted:
                found[owner.pk].append(breach)
    return found


def rows_for_subject(subject):
    """One row per (Organization, breach) for the Organizations the Subject deals with.

    Ordered by Organization name, then newest breach first. Each row: breach, organization,
    case (or None), timing key and text.
    """
    discoveries = {d.organization_id: d for d in subject.discoveries.select_related("organization")}
    cases = {c.organization_id: c for c in subject.cases.select_related("organization")}
    organizations = {d.organization for d in discoveries.values()} | {c.organization for c in cases.values()}
    by_organization = breaches_for_organizations(organizations)
    rows = []
    for organization in sorted(organizations, key=lambda o: (o.name.lower(), o.pk)):
        discovery = discoveries.get(organization.pk)
        breaches = sorted(
            by_organization[organization.pk], key=lambda b: b.breach_date or datetime.date.min, reverse=True
        )
        for breach in breaches:
            key = timing(
                breach.breach_date,
                discovery.first_seen if discovery else None,
                discovery.last_seen if discovery else None,
            )
            rows.append(
                {
                    "breach": breach,
                    "organization": organization,
                    "case": cases.get(organization.pk),
                    "timing": key,
                    "timing_text": TIMING_TEXT[key],
                }
            )
    return rows
