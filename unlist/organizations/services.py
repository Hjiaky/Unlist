# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Operator actions on Organizations and lists: overrides, stubs, contact review, contributions."""

import datetime
import json

from django.db import transaction
from django.db.models import Max
from django.utils.text import slugify

from unlist.organizations import loading, merge, validation
from unlist.organizations.domains import is_ambiguous, normalize_domain
from unlist.organizations.lookup import by_domain
from unlist.organizations.models import Domain, LocalOverride, Organization, OrganizationList


class OverrideError(ValueError):
    pass


def parse_override(field, text):
    """Turn the Operator's text for `field` into a list-format value, or raise OverrideError."""
    text = (text or "").strip()
    if field == merge.DOMAINS:
        domains = []
        for line in text.split():
            domain = normalize_domain(line)
            if not domain:
                raise OverrideError(f"{line!r} is not a domain")
            if is_ambiguous(domain):
                raise OverrideError(
                    f"{domain} is a shared mail or platform domain and cannot belong to one Organization"
                )
            domains.append(domain)
        return sorted(set(domains))
    if field not in merge.FIELDS:
        raise OverrideError(f"{field!r} cannot be overridden")
    kind = merge.FIELDS[field][1]
    if kind == "text":
        value = text.replace("\r\n", "\n")
    elif kind == "list":
        value = [line.strip() for line in text.splitlines() if line.strip()]
    elif kind == "bool":
        if text.lower() not in ("yes", "no", "true", "false"):
            raise OverrideError("enter yes or no")
        value = text.lower() in ("yes", "true")
    elif kind == "int":
        if text and not text.isdigit():
            raise OverrideError("enter a number of days, or leave it empty")
        value = int(text) if text else None
    elif kind == "date":
        try:
            value = datetime.date.fromisoformat(text).isoformat() if text else ""
        except ValueError as error:
            raise OverrideError("enter a date as YYYY-MM-DD") from error
    else:  # json
        try:
            value = json.loads(text) if text else []
        except ValueError as error:
            raise OverrideError("enter valid JSON") from error
    if merge.has_value(value):
        errors = validation.validate(
            value, validation.schema()["definitions"]["record"]["properties"][field], validation.schema(), field
        )
        if errors:
            raise OverrideError(errors[0])
    return value


def override_text(field, value):
    """The form text for an existing value (inverse of parse_override)."""
    if value is None:
        return ""
    if field == merge.DOMAINS or (field in merge.FIELDS and merge.FIELDS[field][1] == "list"):
        return "\n".join(value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def set_override(slug, field, value, note=""):
    LocalOverride.objects.update_or_create(organization_slug=slug, field=field, defaults={"value": value, "note": note})
    loading.recompute()


def delete_override(override):
    override.delete()
    loading.recompute()


@transaction.atomic
def create_stub(domain, name=None):
    """A local Organization for a domain that no list knows. It has no contact until the Operator adds one.

    Returns the known Organization instead when the domain already belongs to one. Raises
    ValueError for shared mail or platform domains and for domains that are in conflict.
    """
    domain = normalize_domain(domain)
    if not domain:
        raise ValueError("not a domain")
    if is_ambiguous(domain):
        raise ValueError(f"{domain} is a shared mail or platform domain")
    known = by_domain(domain)
    if known is not None:
        return known
    if Domain.objects.filter(domain=domain).exists():
        raise ValueError(f"{domain} is claimed by more than one Organization; resolve that first")
    base = "local-" + slugify(domain.replace(".", "-"))
    slug, number = base, 1
    while (
        Organization.objects.filter(slug=slug).exists() or LocalOverride.objects.filter(organization_slug=slug).exists()
    ):
        number += 1
        slug = f"{base}-{number}"
    name = (name or "").strip() or domain
    LocalOverride.objects.create(organization_slug=slug, field="name", value=name, note="local stub")
    LocalOverride.objects.create(organization_slug=slug, field=merge.DOMAINS, value=[domain], note="local stub")
    organization = Organization.objects.create(
        slug=slug,
        name=name,
        domains=[domain],
        quality="local",
        field_sources={"name": merge.LOCAL, "domains": merge.LOCAL, "quality": merge.LOCAL},
    )
    Domain.objects.create(domain=domain, source=None, organization=organization)
    return organization


@transaction.atomic
def accept_contact_change(change):
    organization = change.organization
    for name in merge.CONTACT_FIELDS:
        setattr(organization, merge.FIELDS[name][0], change.new.get(name, ""))
        source = change.new_sources.get(name)
        if source:
            organization.field_sources[name] = source
        else:
            organization.field_sources.pop(name, None)
    organization.save()
    change.delete()


def reject_contact_change(change):
    """Keep the old contact by pinning it as local overrides, so later updates do not raise it again."""
    with transaction.atomic():
        slug = change.organization.slug
        today = datetime.date.today().isoformat()
        for name in merge.CONTACT_FIELDS:
            if change.old.get(name, "") != change.new.get(name, ""):
                LocalOverride.objects.update_or_create(
                    organization_slug=slug,
                    field=name,
                    defaults={"value": change.old.get(name, ""), "note": f"kept after a list update on {today}"},
                )
        change.delete()
    loading.recompute()


def contribution(organization):
    """The Operator's overrides for one Organization as a record in the list format, ready to propose."""
    record = {"slug": organization.slug, "name": organization.name}
    for override in LocalOverride.objects.filter(organization_slug=organization.slug).order_by("field"):
        if merge.has_value(override.value):  # a cleared value cannot be expressed in a record
            record[override.field] = override.value
    return record


def add_list(url):
    """Subscribe to a list by URL (lowest priority) and fetch it once, as the Operator asked."""
    position = (OrganizationList.objects.aggregate(top=Max("position"))["top"] or 0) + 1
    organization_list = OrganizationList.objects.create(name=url[:200], url=url, position=position)
    if loading.update_list(organization_list):
        loading.recompute()
    return organization_list


def remove_list(organization_list):
    if organization_list.bundled:
        raise ValueError("bundled lists can be disabled, not removed")
    organization_list.delete()
    loading.recompute()


@transaction.atomic
def move_list(organization_list, direction):
    ordered = list(OrganizationList.objects.order_by("position", "id"))
    index = ordered.index(organization_list)
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(ordered):
        ordered[index], ordered[other] = ordered[other], ordered[index]
    for position, item in enumerate(ordered):
        if item.position != position:
            item.position = position
            item.save(update_fields=["position"])
    loading.recompute()


def set_list_enabled(organization_list, enabled):
    organization_list.enabled = enabled
    organization_list.save(update_fields=["enabled"])
    loading.recompute()
