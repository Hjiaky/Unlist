# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Validation of Organization List files against the bundled JSON Schema (spec section 4).

The validator below is the same code as in tools/organization-list/build.py, so the list
build and the instance agree on what a valid record is, without a jsonschema dependency.
"""

import datetime
import json
import re
import urllib.parse
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


@cache
def schema():
    with open(DATA_DIR / "schema.json", encoding="utf-8") as handle:
        return json.load(handle)


def record_errors(record):
    return validate(record, schema()["definitions"]["record"], schema(), "record")


def obsolete_errors(record):
    return validate(record, schema()["definitions"]["obsolete"], schema(), "obsolete")


def header_errors(header):
    return validate(header, schema()["definitions"]["header"], schema(), "header")


# --- validator begin ---
# A small JSON Schema validator for the subset schema.json uses. Kept identical in
# unlist/organizations/validation.py (a test compares the two blocks).
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _type_ok(value, name):
    if name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[name])


def _format_ok(value, fmt):
    if fmt == "date":
        if not _DATE_RE.match(value):
            return False
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if fmt == "uri":
        parts = urllib.parse.urlsplit(value)
        return parts.scheme in ("http", "https") and bool(parts.netloc)
    if fmt == "email":
        return bool(_EMAIL_RE.match(value))
    if fmt == "domain":
        return bool(_DOMAIN_RE.match(value))
    return True


def validate(value, schema, root=None, path="$"):
    """Return a list of error messages; empty when `value` matches `schema`."""
    root = schema if root is None else root
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            node = node[part]
        return validate(value, node, root, path)
    types = schema.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(_type_ok(value, t) for t in types):
            return [f"{path}: expected {' or '.join(types)}"]
    errors = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: too short")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']}")
        if "format" in schema and not _format_ok(value, schema["format"]):
            errors.append(f"{path}: {value!r} is not a valid {schema['format']}")
    if _type_ok(value, "number") and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: {value!r} is below {schema['minimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(item, sort_keys=True) for item in value]
            if len(seen) != len(set(seen)):
                errors.append(f"{path}: items are not unique")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(validate(item, schema["items"], root, f"{path}[{index}]"))
    if isinstance(value, dict):
        for key in schema.get("required", ()):
            if key not in value:
                errors.append(f"{path}: missing {key!r}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(validate(item, properties[key], root, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected field {key!r}")
    return errors


# --- validator end ---
