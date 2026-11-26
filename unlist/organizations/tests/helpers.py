# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
import json

from unlist.organizations.models import OrganizationList


def document(records, obsolete=None, version="1", name="Test list"):
    doc = {
        "header": {"name": name, "licence": "CC0-1.0", "version": version, "date": "2026-11-26", "schema_version": 1},
        "records": records,
    }
    if obsolete is not None:
        doc["obsolete"] = obsolete
    return doc


def as_bytes(doc):
    return json.dumps(doc).encode()


def subscribed_list(url="https://lists.example/extra.json", position=10):
    return OrganizationList.objects.create(name=url, url=url, position=position)
