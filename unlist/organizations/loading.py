# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Loading Organization Lists into the database, and recomputing the merged Organizations.

Nothing here runs on its own. Bundled lists load at start-up (`load_bundled_lists`, called
by the entrypoint after `migrate`); subscribed lists are fetched only when the Operator
presses "Update lists" (spec section 4).
"""

import datetime
import json
import logging
import urllib.parse
import urllib.request

from django.db import transaction
from django.utils import timezone

from unlist.organizations import hooks, merge, validation
from unlist.organizations.domains import DATA_DIR, normalize_domain
from unlist.organizations.models import (
    Domain,
    ListRecord,
    LocalOverride,
    Organization,
    OrganizationList,
    PendingContactChange,
    SupervisoryAuthority,
)

log = logging.getLogger("unlist.organizations")

BUNDLED = [("organizations.json", "Unlist official Organization List"), ("jdm-domains.json", "JustDeleteMe domains")]
USER_AGENT = "Unlist (self-hosted; Organization List update requested by the Operator)"
MAX_LIST_BYTES = 32 * 1024 * 1024
FETCH_TIMEOUT = 30


class ListError(Exception):
    """The whole file is unusable; the previous version stays."""


def _normalize_record(record):
    record = dict(record)
    if "domains" in record:
        record["domains"] = sorted({d for d in (normalize_domain(x) for x in record["domains"]) if d})
    return record


@transaction.atomic
def apply_list_document(organization_list, document):
    """Load a parsed list file into `organization_list`.

    Invalid records are skipped with a note on the list, and their previous version (if any)
    is kept. Raises ListError, changing nothing, when the file as a whole is unusable.
    """
    if not isinstance(document, dict) or not isinstance(document.get("records"), list):
        raise ListError("not an Organization List file (no records)")
    header = document.get("header")
    problems = validation.header_errors(header) if isinstance(header, dict) else ["header missing"]
    if problems:
        raise ListError(f"invalid header: {problems[0]}")
    obsolete_entries = document.get("obsolete", [])
    if not isinstance(obsolete_entries, list):
        raise ListError("obsolete must be a list")

    previous = {r.slug: r for r in organization_list.records.all()}
    notes = []
    active = {}
    obsolete = {}

    def take(entry, index, kind, errors_for, target):
        slug = entry.get("slug") if isinstance(entry, dict) else None
        label = slug if isinstance(slug, str) else f"{kind} {index + 1}"
        errors = errors_for(entry) if isinstance(entry, dict) else [f"{kind} is not an object"]
        if errors:
            kept = isinstance(slug, str) and slug in previous
            notes.append(f"{label}: skipped ({errors[0]})" + ("; previous version kept" if kept else ""))
            if kept:
                old = previous[slug]
                (obsolete if old.obsolete else active)[slug] = old.data
            return
        if slug in active or slug in obsolete:
            notes.append(f"{label}: skipped (slug appears twice)")
            return
        target[slug] = _normalize_record(entry)

    for index, entry in enumerate(document["records"]):
        take(entry, index, "record", validation.record_errors, active)
    for index, entry in enumerate(obsolete_entries):
        take(entry, index, "obsolete record", validation.obsolete_errors, obsolete)

    # A domain claimed by two records of the same list belongs to neither.
    claimed = {}
    for slug, record in active.items():
        for domain in record.get("domains", ()):
            claimed.setdefault(domain, []).append(slug)
    for domain, slugs in sorted(claimed.items()):
        if len(slugs) > 1:
            notes.append(f"{domain}: claimed by {', '.join(sorted(slugs))} in this list; ignored")
            for slug in slugs:
                active[slug] = {**active[slug], "domains": [d for d in active[slug]["domains"] if d != domain]}

    wanted = {**{s: (d, False) for s, d in active.items()}, **{s: (d, True) for s, d in obsolete.items()}}
    organization_list.records.exclude(slug__in=wanted).delete()
    changed, created = [], []
    for slug, (data, is_obsolete) in wanted.items():
        row = previous.get(slug)
        if row is None:
            created.append(ListRecord(organization_list=organization_list, slug=slug, data=data, obsolete=is_obsolete))
        elif row.data != data or row.obsolete != is_obsolete:
            row.data, row.obsolete = data, is_obsolete
            changed.append(row)
    ListRecord.objects.bulk_create(created, batch_size=500)
    ListRecord.objects.bulk_update(changed, ["data", "obsolete"], batch_size=500)

    organization_list.licence = header.get("licence", "")
    organization_list.homepage = header.get("homepage", "")
    organization_list.version = header.get("version", "")
    organization_list.date = datetime.date.fromisoformat(header["date"])
    if not organization_list.bundled or not organization_list.name:
        organization_list.name = header["name"][:200]
    organization_list.last_updated = timezone.now()
    organization_list.notes = notes
    organization_list.last_error = ""
    organization_list.save()
    return notes


def _read_bundled(filename):
    with open(DATA_DIR / filename, encoding="utf-8") as handle:
        return json.load(handle)


def load_bundled_lists(force=False):
    """Make sure the bundled lists and Supervisory Authorities are loaded. Returns True if anything changed."""
    changed = False
    for filename, default_name in BUNDLED:
        document = _read_bundled(filename)
        organization_list = OrganizationList.objects.filter(bundled=True, bundled_file=filename).first()
        if organization_list is None:
            last = OrganizationList.objects.order_by("-position").first()
            organization_list = OrganizationList.objects.create(
                name=default_name,
                bundled=True,
                bundled_file=filename,
                position=(last.position + 1) if last else 0,
            )
        version = document.get("header", {}).get("version")
        if force or organization_list.version != version or not organization_list.records.exists():
            try:
                apply_list_document(organization_list, document)
            except ListError as error:
                organization_list.last_error = f"{timezone.now():%Y-%m-%d}: {error}"
                organization_list.save(update_fields=["last_error"])
                log.error("Bundled list %s not loaded: %s", filename, error)
                continue
            changed = True
    load_supervisory_authorities()
    if changed or not Organization.objects.exists():
        recompute()
        changed = True
    return changed


@transaction.atomic
def load_supervisory_authorities():
    records = _read_bundled("supervisory-authorities.json")["records"]
    seen = []
    for record in records:
        SupervisoryAuthority.objects.update_or_create(
            slug=record["slug"],
            defaults={
                "name": record["name"],
                "countries": record.get("relevant-countries", []),
                "address": record.get("address", ""),
                "email": record.get("email", ""),
                "phone": record.get("phone", ""),
                "webform": record.get("webform", ""),
                "web": record.get("web", ""),
                "complaint_language": record.get("complaint-language", ""),
                "preferred_channel": record.get("suggested-transport-medium", ""),
                "sources": record.get("sources", []),
                "comments": record.get("comments", []),
            },
        )
        seen.append(record["slug"])
    SupervisoryAuthority.objects.exclude(slug__in=seen).delete()


def _model_value(name, value):
    attribute, kind = merge.FIELDS[name]
    if kind == "text":
        return "" if value is None else str(value)
    if kind in ("list", "json"):
        return value if isinstance(value, list) else []
    if kind == "bool":
        return bool(value)
    if kind == "int":
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None
    if kind == "date":
        try:
            return datetime.date.fromisoformat(value) if value else None
        except (TypeError, ValueError):
            return None
    raise ValueError(kind)


def _defaults_for(merged):
    values = {attr: _model_value(name, merged.values.get(name)) for name, (attr, _) in merge.FIELDS.items()}
    values["name"] = values["name"] or merged.slug
    values["quality"] = values["quality"] or "verified"
    values.update(
        domains=merged.domains,
        field_sources={**merged.sources, **({"domains": _domain_source(merged)} if merged.domains else {})},
        conflicts=merged.conflicts,
        aliases=merged.aliases,
        obsolete=False,
        redirect_to="",
        listed=True,
    )
    return values


def _domain_source(merged):
    names = []
    for sources in merged.domain_sources.values():
        names.extend(s for s in sources if s not in names)
    return ", ".join(names)


def _contact(values):
    return {name: values[merge.FIELDS[name][0]] for name in merge.CONTACT_FIELDS}


def list_inputs():
    inputs = []
    for organization_list in OrganizationList.objects.filter(enabled=True).order_by("position", "id"):
        records, obsolete = {}, {}
        for row in organization_list.records.all():
            (obsolete if row.obsolete else records)[row.slug] = row.data
        inputs.append(
            merge.ListInput(key=organization_list.pk, name=organization_list.name, records=records, obsolete=obsolete)
        )
    return inputs


def override_map():
    overrides = {}
    for override in LocalOverride.objects.order_by("created_at", "id"):
        overrides.setdefault(override.organization_slug, {})[override.field] = override.value
    return overrides


@transaction.atomic
def recompute():
    """Recompute every Organization from the enabled lists and the local overrides."""
    result = merge.merge(list_inputs(), override_map())
    existing = {o.slug: o for o in Organization.objects.all()}
    pending = {p.organization_id: p for p in PendingContactChange.objects.all()}
    fields = [attr for attr, _ in merge.FIELDS.values()] + [
        "domains",
        "field_sources",
        "conflicts",
        "aliases",
        "obsolete",
        "redirect_to",
        "listed",
    ]
    to_create, to_update = [], []
    for slug, merged in result.organizations.items():
        values = _defaults_for(merged)
        organization = existing.get(slug)
        if organization is None:
            to_create.append(Organization(slug=slug, **values))
            continue
        old_contact = {name: getattr(organization, merge.FIELDS[name][0]) for name in merge.CONTACT_FIELDS}
        new_contact = _contact(values)
        from_lists = any(
            old_contact[name] != new_contact[name] and merged.sources.get(name) != merge.LOCAL
            for name in merge.CONTACT_FIELDS
        )
        held = organization.pk in pending
        if old_contact != new_contact and from_lists and (held or hooks.organization_has_case(slug)):
            # Keep the contact the Case was started with until the Operator accepts the change.
            change = pending.get(organization.pk) or PendingContactChange(organization=organization)
            if change.pk is None or change.new != new_contact:
                change.old = change.old if change.pk else old_contact
                change.new = new_contact
                change.new_sources = {name: merged.sources.get(name, "") for name in merge.CONTACT_FIELDS}
                change.save()
            for name in merge.CONTACT_FIELDS:
                attribute = merge.FIELDS[name][0]
                values[attribute] = getattr(organization, attribute)
                if name in organization.field_sources:
                    values["field_sources"][name] = organization.field_sources[name]
                else:
                    values["field_sources"].pop(name, None)
        elif organization.pk in pending:
            pending[organization.pk].delete()
        if any(getattr(organization, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(organization, key, value)
            to_update.append(organization)

    for slug, entry in result.obsolete.items():
        values = {"obsolete": True, "redirect_to": entry["redirect_to"] or "", "listed": True}
        organization = existing.get(slug)
        if organization is None:
            to_create.append(Organization(slug=slug, name=entry["name"], **values))
        elif any(getattr(organization, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(organization, key, value)
            to_update.append(organization)

    Organization.objects.bulk_create(to_create, batch_size=500)
    Organization.objects.bulk_update(to_update, fields, batch_size=500)

    gone = set(existing) - set(result.organizations) - set(result.obsolete)
    keep = {slug for slug in gone if hooks.organization_has_case(slug)}
    Organization.objects.filter(slug__in=keep, listed=True).update(listed=False)
    Organization.objects.filter(slug__in=gone - keep).delete()

    ids = dict(Organization.objects.values_list("slug", "id"))
    Domain.objects.all().delete()
    Domain.objects.bulk_create(
        [Domain(domain=domain, source_id=source, organization_id=ids[slug]) for domain, source, slug in result.claims],
        batch_size=500,
    )
    return result


def fetch_url(url):
    """Fetch a list file. Called only from the Operator's "Update lists" (or "Add") button."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise ListError("only http and https addresses can be fetched")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
        body = response.read(MAX_LIST_BYTES + 1)
    if len(body) > MAX_LIST_BYTES:
        raise ListError("the file is larger than 32 MB")
    return body


def update_list(organization_list):
    """Fetch and load one subscribed list. Errors are stored on the list; the previous version stays."""
    try:
        document = json.loads(fetch_url(organization_list.url))
        apply_list_document(organization_list, document)
    except (OSError, ValueError, ListError) as error:
        organization_list.last_error = f"{timezone.now():%Y-%m-%d %H:%M}: {error}"
        organization_list.save(update_fields=["last_error"])
        return False
    return True


def update_lists():
    """The "Update lists" button: fetch every enabled subscribed list, then recompute once.

    Bundled lists are not fetched; they change only with a new Unlist release.
    """
    results = {}
    for organization_list in OrganizationList.objects.filter(enabled=True, bundled=False).exclude(url=""):
        results[organization_list.pk] = update_list(organization_list)
    recompute()
    return results
