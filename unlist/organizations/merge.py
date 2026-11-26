# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Merging Organization Lists into Organizations (spec section 4, "Organization List").

Pure functions, no database:

- The Operator orders the lists. Per field, the highest list with a value wins, and a
  local override beats every list. Two lists with different values for a field are a
  conflict, recorded for the Organization page.
- Domains are the exception: an Organization's domains are the union of every list's
  domains for it (a domain-only list such as JustDeleteMe adds domains to records it
  shares a slug with). A local override of `domains` replaces the union.
- Records are matched by slug, or, when slugs differ, by a shared domain. One Organization
  takes at most one record from each list.
- A domain claimed by two Organizations matches neither, until a local override settles
  it: the Organization whose overridden `domains` names it wins.
- Obsolete records redirect: a record whose slug a list marks obsolete joins the
  redirect target.
"""

from dataclasses import dataclass, field

LOCAL = "local override"

# List-format field -> (Organization attribute, kind). `domains` is handled separately.
FIELDS = {
    "name": ("name", "text"),
    "runs": ("runs", "list"),
    "relevant-countries": ("relevant_countries", "list"),
    "categories": ("categories", "list"),
    "address": ("address", "text"),
    "phone": ("phone", "text"),
    "email": ("email", "text"),
    "webform": ("webform", "text"),
    "web": ("web", "text"),
    "suggested-transport-medium": ("preferred_channel", "text"),
    "required-elements": ("required_elements", "json"),
    "needs-id-document": ("needs_id_document", "bool"),
    "request-language": ("request_language", "text"),
    "comments": ("comments", "list"),
    "notes": ("notes", "list"),
    "sources": ("sources", "list"),
    "quality": ("quality", "text"),
    "supervisory-authority": ("supervisory_authority", "text"),
    "broker": ("broker", "bool"),
    "recheck-default": ("recheck_default", "int"),
    "last-checked": ("last_checked", "date"),
}
DOMAINS = "domains"
OVERRIDABLE = (*FIELDS, DOMAINS)
CONTACT_FIELDS = ("email", "address", "webform")
MAX_REDIRECTS = 20


def has_value(value):
    return value is not None and value != "" and value != [] and value != {}


@dataclass
class ListInput:
    """One enabled list, in the Operator's order (first = highest)."""

    key: object
    name: str
    records: dict  # slug -> record (list format)
    obsolete: dict = field(default_factory=dict)  # slug -> {"name", "reason", "redirect-to"}


@dataclass
class MergedOrganization:
    slug: str
    values: dict = field(default_factory=dict)  # list-format field -> value
    sources: dict = field(default_factory=dict)  # field -> list name or LOCAL
    conflicts: dict = field(default_factory=dict)  # field -> [[list name, value], ...] (every list with a value)
    domains: list = field(default_factory=list)
    domain_sources: dict = field(default_factory=dict)  # domain -> [list names]
    members: dict = field(default_factory=dict)  # list index -> record slug
    aliases: list = field(default_factory=list)  # other slugs this Organization goes by
    local_only: bool = False


@dataclass
class MergeResult:
    organizations: dict  # slug -> MergedOrganization
    obsolete: dict  # obsolete slug -> {"name": str, "redirect_to": final slug or None}
    claims: list  # (domain, list key or None for a local override, organization slug)
    owners: dict  # domain -> owning organization slug, or None while conflicted
    domain_conflicts: dict  # domain -> sorted claiming slugs


def domain_owners(claims):
    """{domain: owner slug or None}. Local claims settle a conflict; otherwise one claimant must remain."""
    claimants = {}
    local = {}
    for domain, source, slug in claims:
        claimants.setdefault(domain, set()).add(slug)
        if source is None:
            local.setdefault(domain, set()).add(slug)
    owners = {}
    for domain, slugs in claimants.items():
        if len(local.get(domain, ())) == 1:
            owners[domain] = next(iter(local[domain]))
        elif len(slugs) == 1:
            owners[domain] = next(iter(slugs))
        else:
            owners[domain] = None
    return owners


def _redirects(lists):
    """{obsolete slug: (name, target or None)}. A list marking a slug obsolete is ignored when
    a higher list still has the slug as an active record."""
    active_rank = {}
    for index, lst in enumerate(lists):
        for slug in lst.records:
            active_rank.setdefault(slug, index)
    redirects = {}
    for index, lst in enumerate(lists):
        for slug, entry in lst.obsolete.items():
            if slug in redirects or active_rank.get(slug, len(lists)) < index:
                continue
            redirects[slug] = (entry.get("name") or slug, entry.get("redirect-to") or None)
    return redirects


def _resolve(slug, redirects):
    """Follow redirects to an active slug. Returns (final slug or None, was_redirected)."""
    seen = set()
    current = slug
    while current in redirects:
        if current in seen or len(seen) > MAX_REDIRECTS:
            return None, True
        seen.add(current)
        current = redirects[current][1]
        if current is None:
            return None, True
    return current, current != slug


def merge(lists, overrides=None):
    """Merge ordered `lists` (ListInput) and `overrides` ({slug: {field: value}}) into a MergeResult."""
    overrides = overrides or {}
    redirects = _redirects(lists)
    clusters = {}  # cluster slug -> MergedOrganization
    slug_index = {}  # any slug -> cluster slug
    domain_index = {}  # domain -> set of cluster slugs

    for index, lst in enumerate(lists):
        for slug in sorted(lst.records):
            record = lst.records[slug]
            canonical, redirected = _resolve(slug, redirects)
            if canonical is None:
                continue  # a higher list says this Organization is gone
            key = slug_index.get(canonical)
            if key is not None and index in clusters[key].members:
                key = None
            domains = sorted(set(record.get(DOMAINS) or ()))
            if key is None and not redirected:
                found = {k for d in domains for k in domain_index.get(d, ())}
                candidates = {k for k in found if index not in clusters[k].members}
                if len(candidates) == 1 and candidates == found:
                    key = next(iter(candidates))
            if key is None:
                key = canonical if canonical not in clusters else slug
                if key in clusters:
                    continue  # two records of one list resolve to the same slug; the first stays
                clusters[key] = MergedOrganization(slug=key)
            cluster = clusters[key]
            cluster.members[index] = slug
            slug_index.setdefault(canonical, key)
            slug_index.setdefault(slug, key)
            for domain in domains:
                domain_index.setdefault(domain, set()).add(key)

    # Local overrides for slugs that no list has make local-only Organizations (stubs).
    resolved_overrides = {}
    for slug, values in overrides.items():
        canonical, _ = _resolve(slug, redirects)
        canonical = canonical or slug
        key = slug_index.get(canonical, canonical)
        if key not in clusters:
            clusters[key] = MergedOrganization(slug=key, local_only=True)
        resolved_overrides.setdefault(key, {}).update(values)

    claims = []
    for key, cluster in clusters.items():
        members = sorted(cluster.members.items())
        for name in FIELDS:
            found = [
                (lists[i].name, lists[i].records[s][name])
                for i, s in members
                if has_value(lists[i].records[s].get(name))
            ]
            if found:
                cluster.values[name] = found[0][1]
                cluster.sources[name] = found[0][0]
                if any(value != found[0][1] for _, value in found[1:]):
                    cluster.conflicts[name] = [[list_name, value] for list_name, value in found]
        domain_sources = {}
        for i, s in members:
            for domain in lists[i].records[s].get(DOMAINS) or ():
                domain_sources.setdefault(domain, []).append(lists[i].name)
                if DOMAINS not in resolved_overrides.get(key, {}):
                    claims.append((domain, lists[i].key, key))
        local = resolved_overrides.get(key, {})
        for name, value in local.items():
            if name == DOMAINS:
                continue
            cluster.values[name] = value
            cluster.sources[name] = LOCAL
        if DOMAINS in local:
            domain_sources = {domain: [LOCAL] for domain in local[DOMAINS]}
            claims.extend((domain, None, key) for domain in local[DOMAINS])
        cluster.domain_sources = dict(sorted(domain_sources.items()))
        cluster.domains = sorted(domain_sources)
        if cluster.local_only:
            cluster.values.setdefault("name", key)
            cluster.values["quality"] = "local"
            cluster.sources.setdefault("quality", LOCAL)
        cluster.aliases = sorted({s for _, s in members} - {key})

    owners = domain_owners(claims)
    claimants = {}
    for domain, _, slug in claims:
        claimants.setdefault(domain, set()).add(slug)
    conflicts = {domain: sorted(claimants[domain]) for domain, owner in owners.items() if owner is None}

    obsolete = {}
    for slug, (name, _) in redirects.items():
        if slug in clusters:
            continue
        target, _ = _resolve(slug, redirects)
        obsolete[slug] = {"name": name, "redirect_to": target if target in clusters else None}

    return MergeResult(
        organizations=clusters,
        obsolete=obsolete,
        claims=claims,
        owners=owners,
        domain_conflicts=conflicts,
    )
