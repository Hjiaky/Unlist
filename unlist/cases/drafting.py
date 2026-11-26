# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""What goes into a draft: jurisdiction, language, recipient and the identifying details.

Pure functions over plain values or duck-typed objects (an Organization, IdentifyingDetails),
so they can be tested without the database.
"""

import re
from datetime import date

from unlist.cases.deadlines import Jurisdiction

FALLBACK_LANGUAGE = "en"
# Spec section 6, research: the grounds for a service no longer used. Overridable per draft.
DEFAULT_ERASURE_GROUNDS = ("no_longer_necessary", "consent_withdrawn", "objection")
# Supervisory Authority slugs (supervisory-authorities.json) that apply the UK GDPR.
UK_SUPERVISORY_AUTHORITIES = frozenset({"gbico"})
_UK_COUNTRIES = frozenset({"GB", "UK"})

_MONTHS = {
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    "de": (
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ),
}

# IdentifyingDetail kind -> label per language, for the "Other details you may need" lines.
DETAIL_LABELS = {
    "customer_number": {"en": "Customer number", "de": "Kundennummer"},
    "previous_address": {"en": "Previous address", "de": "Frühere Anschrift"},
    "date_of_birth": {"en": "Date of birth", "de": "Geburtsdatum"},
}

# Words in a required field's description (several languages, as the lists hold them).
_CUSTOMER_NUMBER_WORDS = re.compile(
    r"kunde|customer|client|account.?(number|no|id)|kontonummer|mitglied|member|vertrag|contract|"
    r"numéro de client|cliente|klant",
    re.IGNORECASE,
)
_PREVIOUS_ADDRESS_WORDS = re.compile(
    r"previous|former|earlier|\bold\b|vorherig|früher|frueher|voranschrift|vorige|\balte|ancienne|anterior",
    re.IGNORECASE,
)


def countries(organization) -> list[str]:
    """The Organization's relevant countries in upper case, without "all"."""
    return [code.upper() for code in (organization.relevant_countries or []) if code and code.lower() != "all"]


def jurisdiction_for(organization) -> Jurisdiction:
    """UK when the Organization's Supervisory Authority is the UK one or it is relevant only in the UK."""
    if (organization.supervisory_authority or "").lower() in UK_SUPERVISORY_AUTHORITIES:
        return Jurisdiction.UK
    found = countries(organization)
    if found and set(found) <= _UK_COUNTRIES:
        return Jurisdiction.UK
    return Jurisdiction.EU


def country_for(organization) -> str | None:
    """The first relevant country that is not "all", for public holidays; else None."""
    found = countries(organization)
    return found[0] if found else None


def request_language(organization) -> str:
    return (organization.request_language or "").strip().lower() or FALLBACK_LANGUAGE


def format_date(day: date | None, lang: str) -> str:
    """A date as the templates expect it: ``2 October 2026`` or ``2. Oktober 2026``."""
    if day is None:
        return ""
    if lang == "de":
        return f"{day.day}. {_MONTHS['de'][day.month - 1]} {day.year}"
    return f"{day.day} {_MONTHS['en'][day.month - 1]} {day.year}"


def choose_channel(organization) -> tuple[str, str]:
    """(channel, recipient): the preferred channel if its contact is known, else email, web form, letter."""
    contacts = {"email": organization.email, "webform": organization.webform, "letter": organization.address}
    preferred = organization.preferred_channel
    if preferred in contacts and contacts[preferred]:
        return preferred, contacts[preferred].strip()
    for channel in ("email", "webform", "letter"):
        if contacts[channel]:
            return channel, contacts[channel].strip()
    return "", ""


def _organization_names(organization) -> set[str]:
    names = {organization.name, organization.slug, *(organization.runs or []), *(organization.domains or [])}
    return {name.strip().lower() for name in names if name and name.strip()}


def asked_detail_kinds(required_elements) -> list[str]:
    """Which IdentifyingDetail kinds the Organization's required identification fields ask for.

    Name and email are always in the request already. A plain "address" asks for the current
    address, which Unlist does not store, so only an address field that says "previous" (or
    similar) matches previous addresses. Free-text fields match customer numbers by their words.
    """
    kinds: list[str] = []
    for element in required_elements or []:
        if not isinstance(element, dict):
            continue
        kind_of_field = element.get("type", "")
        desc = element.get("desc", "") or ""
        if kind_of_field == "birthdate":
            found = "date_of_birth"
        elif kind_of_field == "address" and _PREVIOUS_ADDRESS_WORDS.search(desc):
            found = "previous_address"
        elif kind_of_field in ("input", "textarea") and _CUSTOMER_NUMBER_WORDS.search(desc):
            found = "customer_number"
        else:
            continue
        if found not in kinds:
            kinds.append(found)
    return kinds


def identifying_lines(organization, details, lang: str) -> list[str]:
    """``identifying_details`` for a request: only what the Organization asks for, nothing else.

    Customer numbers are per Organization: only those whose label names this Organization (its
    name, slug, a brand or a domain) are used. Dates of birth and previous addresses belong to the
    Subject and are used whenever asked for.
    """
    asked = asked_detail_kinds(organization.required_elements)
    names = _organization_names(organization)
    lines = []
    for kind in asked:
        label = DETAIL_LABELS[kind].get(lang, DETAIL_LABELS[kind][FALLBACK_LANGUAGE])
        for detail in details:
            if detail.kind != kind:
                continue
            if kind == "customer_number" and (detail.organization_label or "").strip().lower() not in names:
                continue
            lines.append(f"{label}: {detail.value}")
    return lines
