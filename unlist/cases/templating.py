# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Render the mail templates in `unlist/cases/mail_templates/<lang>/<kind>.txt`.

    subject, body = render("access_request", "de", context)

Templates use Django's template language in a separate engine with autoescaping off.
The variables each kind takes are listed in `mail_templates/README.md`.

Lookup, first match wins:
  1. `<DATA_DIR>/mail_templates/<lang>/<kind>.txt` (the Operator's local override)
  2. the bundled `<lang>/<kind>.txt`
  3. and 4. the same two for English.

UK templates exist only in English: with jurisdiction "UK", any other language is rendered
in English (the German texts cite the EU GDPR as "DSGVO").

The subject line is rendered on its own and always comes back as one line. In the body, a
line that holds only template tags (`{% ... %}` or `{# ... #}`) produces no output line,
so `{% if %}` can sit on its own line around an optional paragraph. Trailing spaces are
dropped and runs of blank lines collapse into one.

A variable the template prints but the context lacks renders as `[[missing: name]]`, so
the Operator sees it in the draft. `strict=True` raises `MissingVariableError` instead,
and also checks the required variables of the kind.
"""

import re
from functools import lru_cache
from pathlib import Path

from django.template import Context, Engine

from unlist import paths

TEMPLATE_DIR = Path(__file__).resolve().parent / "mail_templates"
FALLBACK_LANGUAGE = "en"
JURISDICTIONS = ("EU", "UK")
# Languages that have UK variants. Every other language falls back to English for the UK.
UK_LANGUAGES = ("en",)

# Erasure grounds of Art. 17(1) a removal request can name.
ERASURE_GROUNDS = ("no_longer_necessary", "consent_withdrawn", "objection", "unlawful")
# The requests a reminder or a UK complaint to the Organization can refer to.
ORIGINAL_KINDS = ("access_request", "removal_request")

_COMMON = frozenset({"jurisdiction", "reference", "subject_name", "subject_email", "organization_name"})

# Every kind and the variables it cannot do without. Optional variables are in the README.
REQUIRED_VARIABLES = {
    "access_request": _COMMON,
    "removal_request": _COMMON | {"erasure_grounds"},
    "reminder": _COMMON | {"original_kind", "original_date", "deadline_date"},
    "details_reply": _COMMON | {"details"},
    "id_pushback": _COMMON,
    "reconsider": _COMMON,
    "authority_letter": _COMMON | {"operator_name", "letter_date"},
    "uk_complaint_to_organization": _COMMON | {"original_kind", "original_date", "infringement", "remedy"},
    "complaint": _COMMON
    | {
        "supervisory_authority_name",
        "organization_contacts",
        "timeline",
        "infringement",
        "remedy",
        "prior_contact",
        "attachments",
    },
}
KINDS = tuple(REQUIRED_VARIABLES)
UK_ONLY_KINDS = ("uk_complaint_to_organization",)

# Short name of the law, by language and jurisdiction; offered to templates as `gdpr`.
_LAW_NAMES = {"en": {"EU": "GDPR", "UK": "UK GDPR"}, "de": {"EU": "DSGVO"}}

MISSING = "[[missing: %s]]"
_MISSING_RE = re.compile(r"\[\[missing: ([^\]]*)\]\]")
_TAG_ONLY_LINE = re.compile(r"^[ \t]*(?:(?:\{%.*?%\}|\{#.*?#\})[ \t]*)+\n", re.MULTILINE)
_LANGUAGE = re.compile(r"[a-z]{2,3}")


class MissingVariableError(ValueError):
    """A template needed a variable the context did not give."""


@lru_cache(maxsize=1)
def _engine() -> Engine:
    return Engine(autoescape=False, string_if_invalid=MISSING)


def _normalise_language(lang: str) -> str:
    lang = (lang or "").strip().lower().replace("_", "-").split("-")[0]
    return lang if _LANGUAGE.fullmatch(lang) else FALLBACK_LANGUAGE


def _candidates(kind: str, lang: str) -> list[Path]:
    return [paths.DATA_DIR / "mail_templates" / lang / f"{kind}.txt", TEMPLATE_DIR / lang / f"{kind}.txt"]


def template_language(kind: str, lang: str, jurisdiction: str) -> str:
    """The language `render` will use for this kind, language and jurisdiction."""
    lang = _normalise_language(lang)
    if jurisdiction == "UK" and lang not in UK_LANGUAGES:
        return FALLBACK_LANGUAGE
    if not any(path.is_file() for path in _candidates(kind, lang)):
        return FALLBACK_LANGUAGE
    return lang


def template_path(kind: str, lang: str) -> Path:
    """The file that will be rendered for this kind and (already resolved) language."""
    for path in _candidates(kind, lang):
        if path.is_file():
            return path
    raise FileNotFoundError(f"No mail template {lang}/{kind}.txt")


def missing_variables(text: str) -> list[str]:
    """Names of the variables that rendered as missing in `text`."""
    return sorted(set(_MISSING_RE.findall(text)))


def _check(kind: str, context: dict) -> None:
    absent = sorted(name for name in REQUIRED_VARIABLES[kind] if context.get(name) in (None, "", [], ()))
    if absent:
        raise MissingVariableError(f"{kind}: missing {', '.join(absent)}")
    if kind == "removal_request":
        unknown = set(context["erasure_grounds"]) - set(ERASURE_GROUNDS)
        if unknown:
            raise ValueError(f"{kind}: unknown erasure grounds {sorted(unknown)}")
    if "original_kind" in REQUIRED_VARIABLES[kind] and context["original_kind"] not in ORIGINAL_KINDS:
        raise ValueError(f"{kind}: original_kind must be one of {ORIGINAL_KINDS}")


def render(kind: str, lang: str, context: dict, *, strict: bool = False) -> tuple[str, str]:
    """Render one mail template and return (subject, body)."""
    if kind not in REQUIRED_VARIABLES:
        raise ValueError(f"Unknown mail template kind {kind!r}")
    jurisdiction = context.get("jurisdiction")
    if jurisdiction not in JURISDICTIONS:
        raise ValueError(f"jurisdiction must be one of {JURISDICTIONS}, not {jurisdiction!r}")
    if kind in UK_ONLY_KINDS and jurisdiction != "UK":
        raise ValueError(f"{kind} exists only for the UK")
    if strict:
        _check(kind, context)

    lang = template_language(kind, lang, jurisdiction)
    path = template_path(kind, lang)
    source = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    first, _, rest = source.partition("\n")
    if not first.startswith("Subject:") or not rest.startswith("\n"):
        raise ValueError(f"{path}: the first line must be 'Subject: ...', followed by a blank line")

    derived = {"uk": jurisdiction == "UK", "gdpr": _LAW_NAMES.get(lang, _LAW_NAMES["en"]).get(jurisdiction, "GDPR")}
    full_context = Context({**derived, **context})
    subject = _engine().from_string(first.removeprefix("Subject:")).render(full_context)
    body = _engine().from_string(_TAG_ONLY_LINE.sub(lambda m: m.group(0).strip(), rest)).render(full_context)

    if strict and (missing := missing_variables(subject + body)):
        raise MissingVariableError(f"{path}: missing {', '.join(missing)}")
    # One line, whatever the variables held: the subject becomes a mail header.
    subject = " ".join(subject.split())
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in body.split("\n"))).strip()
    return subject, body + "\n"
