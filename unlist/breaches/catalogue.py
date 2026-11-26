# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Loading the Have I Been Pwned catalogue: from the bundled file, or (only when the Operator asks) from the web.

Nothing here sends anything about a Subject. The one request is a plain GET of the free,
keyless catalogue, made only from `fetch_catalogue`, which only the "Update breach list" button calls.
"""

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from unlist.breaches.models import Breach, BreachCatalogue

DATA_DIR = Path(__file__).resolve().parent / "data"
BUNDLED_FILE = DATA_DIR / "hibp-breaches.json"
SOURCE_URL = "https://haveibeenpwned.com/api/v3/breaches"
USER_AGENT = "Unlist (+https://github.com/Hjiaky/Unlist)"
TIMEOUT_SECONDS = 30
MAX_BYTES = 20 * 1024 * 1024


class CatalogueError(Exception):
    """The catalogue could not be fetched or read. The message is safe to show the Operator."""


def _text(value, limit):
    return value[:limit] if isinstance(value, str) else ""


def _flag(record, key):
    return record.get(key) is True


def _fields(record):
    """The model fields for one catalogue record (HIBP spelling in, ours out). None if it has no Name."""
    if not isinstance(record, dict) or not isinstance(record.get("Name"), str) or not record["Name"]:
        return None
    added = parse_datetime(record["AddedDate"]) if isinstance(record.get("AddedDate"), str) else None
    classes = record.get("DataClasses")
    return {
        "title": _text(record.get("Title"), 300) or record["Name"][:300],
        "domain": _text(record.get("Domain"), 253).strip().lower(),
        "breach_date": parse_date(record["BreachDate"]) if isinstance(record.get("BreachDate"), str) else None,
        "added_date": added,
        "data_classes": [c for c in classes if isinstance(c, str)] if isinstance(classes, list) else [],
        "is_verified": _flag(record, "IsVerified"),
        "is_spam_list": _flag(record, "IsSpamList"),
        "is_malware": _flag(record, "IsMalware"),
        "is_fabricated": _flag(record, "IsFabricated"),
        "is_sensitive": _flag(record, "IsSensitive"),
        "attribution": _text(record.get("Attribution"), 500),
        "description": record.get("Description") if isinstance(record.get("Description"), str) else "",
    }


@transaction.atomic
def store(records, *, source, fetched_at, bundled):
    """Make the Breach table match `records` (a list of catalogue dicts). Idempotent. Returns the count.

    Breaches missing from a newer catalogue are removed; hand assignments are keyed by name
    and stay. Raises CatalogueError (changing nothing) when there is nothing usable.
    """
    parsed = {}
    for record in records:
        fields = _fields(record)
        if fields:
            parsed[record["Name"][:200]] = fields
    if not parsed:
        raise CatalogueError("The catalogue holds no breaches.")
    existing = {breach.name: breach for breach in Breach.objects.all()}
    for name, fields in parsed.items():
        breach = existing.get(name)
        if breach is None:
            Breach.objects.create(name=name, **fields)
        elif any(getattr(breach, key) != value for key, value in fields.items()):
            for key, value in fields.items():
                setattr(breach, key, value)
            breach.save()
    Breach.objects.exclude(name__in=parsed).delete()
    BreachCatalogue.objects.update_or_create(
        pk=1, defaults={"source": source, "fetched_at": fetched_at, "count": len(parsed), "bundled": bundled}
    )
    return len(parsed)


def load_bundled(*, force=False):
    """Load the bundled snapshot. Local file only. Returns the count, or None when already loaded."""
    with open(BUNDLED_FILE, encoding="utf-8") as handle:
        document = json.load(handle)
    fetched_at = datetime.fromisoformat(document["fetched"]).replace(tzinfo=UTC)
    current = BreachCatalogue.objects.filter(pk=1).first()
    if (
        not force
        and current
        and current.source == document["source"]
        and current.fetched_at == fetched_at
        and current.bundled
        and current.count == Breach.objects.count()
    ):
        return None
    return store(document["breaches"], source=document["source"], fetched_at=fetched_at, bundled=True)


def fetch_catalogue(now=None):
    """Fetch the free catalogue from Have I Been Pwned and store it. Only the Update button calls this."""
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise CatalogueError(f"Could not reach Have I Been Pwned: {error}") from error
    if len(body) > MAX_BYTES:
        raise CatalogueError("The answer from Have I Been Pwned was too large; nothing was changed.")
    try:
        records = json.loads(body)
    except ValueError as error:
        raise CatalogueError("Have I Been Pwned did not return a catalogue; nothing was changed.") from error
    if not isinstance(records, list):
        raise CatalogueError("Have I Been Pwned did not return a catalogue; nothing was changed.")
    return store(records, source=SOURCE_URL, fetched_at=now or datetime.now(UTC), bundled=False)
