# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The four jobs the optional LLM does (spec section 12). Each is a suggestion with a fallback.

Every job builds what it sends from explicit fields, never from whole objects, and sends only
what :data:`SENDS` lists (the settings page and the remote notice show that list). Every job
returns None when the LLM is off or fails, and the caller does what it does without one: the
discovery and draft pages stay as they are, the keyword rules suggest reply outcomes, and the
Operator types the privacy contact in. Nothing here changes state or sends mail: the Operator
applies a suggestion with a button.

Decided by agent (ticket #56):

- Sorting is offered only for mail the rules left unsorted (evidence ``none``, spec section 5),
  and the model may answer transaction, account, bulk or none: order markup is a fact of the
  HTML, which the model never sees.
- The reply job sends the new part of the reply only (the quoted original holds the Subject's
  request with all their details), with the Subject's name, addresses and details replaced
  by placeholders, and waits at most 15 seconds: it runs while a reply is being stored.
- Sorting replaces the Subject's data in the subject line with placeholders too.
- Adapting a draft sends its subject line as well as its body (both come from the template).
"""

import logging
import re
from dataclasses import dataclass

from django.conf.locale import LANG_INFO
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from unlist.cases import drafting, replies
from unlist.cases.lifecycle import OUTCOME_LABELS, Action
from unlist.llm import client, fetch
from unlist.llm.models import LlmSettings
from unlist.llm.redaction import Redactor
from unlist.mail import scanner
from unlist.mail.models import Discovery

log = logging.getLogger("unlist.llm")

SENDS = (
    (
        "Sort leftover discovery mail",
        "Only when you click “Ask the LLM” on a sender the rules left unsorted: the sender's name and "
        "domain, and one subject line in which the Subject's name, email addresses and identifying details "
        "are replaced by placeholders.",
    ),
    (
        "Adapt a draft to another language",
        "Only when you click “Adapt to …” on a draft: its subject line and text, with the Subject's name, "
        "email addresses, identifying details and the reference code replaced by placeholders, and the "
        "name of the language.",
    ),
    (
        "Suggest reply outcomes",
        "For every reply Unlist takes in: the new text of the reply (without the quoted original), with the "
        "Subject's name, email addresses and identifying details replaced by placeholders. Not the sender, "
        "the subject line or any attachment.",
    ),
    (
        "Find a privacy contact",
        "Only when you click “Find privacy contact”: the text of the public privacy-policy page whose "
        "address you paste. Unlist fetches the page itself.",
    ),
)
COMMON = "Every request also carries the model name and Unlist's fixed instructions for the job."

SORTABLE = (scanner.TRANSACTION, scanner.ACCOUNT, scanner.BULK)
SORT_TEXT_MAX = 500
DRAFT_TEXT_MAX = 40_000
REPLY_TEXT_MAX = 12_000
REPLY_TIMEOUT = 15  # below SQLite's 20-second busy timeout: the reply is stored in a transaction
REPLY_OUTCOMES = tuple(action for action in OUTCOME_LABELS if action is not Action.BOUNCE)
REASON_MAX = 300


def _settings(settings=None) -> LlmSettings:
    return settings if settings is not None else LlmSettings.load()


def _reason(found: dict) -> str:
    return " ".join(str(found.get("reason") or "").split())[:REASON_MAX]


# --- 1. Discovery leftovers ------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceSuggestion:
    evidence: str
    reason: str
    label: str


def sort_messages(sender: str, subject_line: str) -> list[dict]:
    """The whole request for job 1: built from the sender and the subject line, nothing else."""
    instructions = (
        "You sort the senders of email for a personal-data tool. From the sender and one subject line, "
        "say what kind of mail it is. Answer with JSON only: "
        '{"evidence": "transaction" | "account" | "bulk" | "none", "reason": "a few words"}. '
        "transaction: an order, receipt, invoice, booking or shipping notice. "
        "account: an account notice such as a welcome, verification, password reset, security or policy notice. "
        "bulk: a newsletter or marketing mail. none: you cannot tell."
    )
    text = f"Sender: {sender[:SORT_TEXT_MAX]}\nSubject line: {subject_line[:SORT_TEXT_MAX]}"
    return [{"role": "system", "content": instructions}, {"role": "user", "content": text}]


def _sender_of(item) -> str:
    """The sender of a Discovery (its Organization) or an UnassignedSender, as name and domain."""
    if isinstance(item, Discovery):
        domains = list(item.organization.domains or [])
        name, domain = item.organization.name, domains[0] if domains else ""
    else:
        name, domain = item.display_name, item.domain
    return f"{name} ({domain})" if name and domain else name or domain


def sort_leftover(item, settings=None) -> EvidenceSuggestion | None:
    """Job 1: an evidence kind for a Discovery or UnassignedSender the rules left unsorted, or None."""
    settings = _settings(settings)
    if not settings.usable or item.evidence != scanner.NONE:
        return None
    redactor = Redactor.for_subject(item.subject)
    messages = sort_messages(_sender_of(item), redactor.redact(item.strongest_subject or ""))
    try:
        found = client.parse_json_object(client.chat(settings, messages))
    except client.LlmError as error:
        log.warning("Sorting with the LLM failed; the evidence stays as it is: %s", error)
        return None
    evidence = str(found.get("evidence") or "").strip().lower()
    if evidence not in (*SORTABLE, scanner.NONE):
        log.warning("The LLM answered an unknown evidence kind %r", evidence[:40])
        return None
    return EvidenceSuggestion(evidence, _reason(found), settings.source_label)


# --- 2. Drafts in another language -----------------------------------------------------------


@dataclass(frozen=True)
class DraftProposal:
    subject_line: str
    body: str
    lang: str
    language: str
    label: str


def language_name(code: str) -> str:
    info = LANG_INFO.get((code or "").lower(), {})
    return info.get("name") or (code or "").upper()


def adapt_target(draft) -> str | None:
    """The language a draft could be adapted to: the Organization's, when no template exists for it."""
    if draft.status != draft.Status.AWAITING_APPROVAL:
        return None
    wanted = drafting.request_language(draft.case.organization)
    return wanted if wanted != draft.lang and re.fullmatch(r"[a-z]{2,3}", wanted) else None


def adapt_messages(language: str, subject_line: str, body: str) -> list[dict]:
    """The whole request for job 2: the target language and the (already redacted) draft text."""
    instructions = (
        f"Translate the email below into {language}. It is a data-protection request a person sends to an "
        "organization: keep its meaning, its polite tone and every legal reference. Keep every placeholder in "
        "double curly braces, such as {{NAME}}, exactly as written. Keep the first line in the form "
        "'Subject: ...'. Answer with the translated email only."
    )
    text = f"Subject: {subject_line}\n\n{body}"[:DRAFT_TEXT_MAX]
    return [{"role": "system", "content": instructions}, {"role": "user", "content": text}]


def _split_email(answer: str) -> tuple[str, str] | None:
    text = re.sub(r"^\s*```\w*\n|\n```\s*$", "", answer.strip())
    first, _, rest = text.strip().partition("\n")
    # "Subject:" as asked, or a translated label on a line that keeps the reference code.
    match = re.match(r"^\s*\**\s*([^:\n]{1,30}?)\s*\**\s*:\s*(.*)$", first)
    if not match or not rest.strip():
        return None
    if match.group(1).strip().lower() != "subject" and "{{REFERENCE}}" not in match.group(2):
        return None
    return " ".join(match.group(2).split()), rest.strip("\n").rstrip() + "\n"


def adapt_draft(draft, settings=None) -> DraftProposal | None:
    """Job 2: the draft translated into its Organization's language, the Subject's data put back; or None."""
    settings = _settings(settings)
    lang = adapt_target(draft)
    if not settings.usable or lang is None:
        return None
    case = draft.case
    redactor = Redactor.for_subject(case.subject, emails=[draft.sender], reference=case.reference)
    subject_line, body = redactor.redact(draft.subject_line), redactor.redact(draft.body)
    language = language_name(lang)
    try:
        answer = client.chat(settings, adapt_messages(language, subject_line, body))
    except client.LlmError as error:
        log.warning("Adapting a draft with the LLM failed; the draft stays as it is: %s", error)
        return None
    parts = _split_email(answer)
    if parts is None:
        log.warning("The LLM's translation has no subject line")
        return None
    if lost := redactor.missing_in(subject_line + "\n" + body, parts[0] + "\n" + parts[1]):
        log.warning("The LLM's translation lost placeholders %s", sorted(lost))
        return None
    return DraftProposal(redactor.restore(parts[0]), redactor.restore(parts[1]), lang, language, settings.source_label)


# --- 3. Reply outcomes -----------------------------------------------------------------------


def reply_messages(text: str) -> list[dict]:
    """The whole request for job 3: the (already redacted) reply text, nothing else."""
    choices = " ".join(f"{action.value}: {OUTCOME_LABELS[action]}." for action in REPLY_OUTCOMES)
    instructions = (
        "You read one reply an organization sent to a person's data-protection request (an access or "
        "erasure request). Choose the one outcome that fits best and answer with JSON only: "
        '{"outcome": "...", "reason": "a short reason"}. Outcomes: '
        f"{choices} If none fits or it only acknowledges the request, answer "
        '{"outcome": "none", "reason": "..."}.'
    )
    return [{"role": "system", "content": instructions}, {"role": "user", "content": text[:REPLY_TEXT_MAX]}]


def reply_text(reply) -> str:
    """What job 3 sends: the new part of the reply's text, the Subject's data replaced."""
    redactor = Redactor.for_subject(reply.subject)
    return redactor.redact(replies.strip_quoted(reply.body or "").strip())[:REPLY_TEXT_MAX]


def suggest_reply_outcome(reply, settings=None):
    """Job 3, a ``replies.suggesters`` entry: a ``Suggestion(source="llm")``, or None so the rules apply."""
    settings = _settings(settings)
    if not settings.usable:
        return None
    text = reply_text(reply)
    if not text.strip():
        return None
    try:
        found = client.parse_json_object(client.chat(settings, reply_messages(text), timeout=REPLY_TIMEOUT))
    except client.LlmError as error:
        log.warning("Suggesting a reply outcome with the LLM failed; the keyword rules apply: %s", error)
        return None
    outcome = str(found.get("outcome") or "").strip().lower()
    if outcome not in {action.value for action in REPLY_OUTCOMES}:
        return None
    note = f"{settings.source_label}: {_reason(found)}".rstrip(": ")
    # The details the Operator confirms are read from the reply locally, as the rules read them.
    body = replies.strip_quoted(reply.body or "")
    if outcome == Action.REFUSED:
        return replies.Suggestion(outcome, "llm", note, exception=replies.cited_exception(body))
    if outcome == Action.REMOVED:
        return replies.Suggestion(outcome, "llm", note, suppression_confirmed=bool(replies.SUPPRESSION_RE.search(body)))
    if outcome == Action.EXTENSION_ANNOUNCED:
        return replies.Suggestion(outcome, "llm", note, with_reasons=bool(replies.REASONS_RE.search(body)))
    return replies.Suggestion(outcome, "llm", note)


# --- 4. Privacy contact ----------------------------------------------------------------------


@dataclass(frozen=True)
class ContactProposal:
    email: str
    address: str
    webform: str
    reason: str
    label: str
    url: str


def contact_messages(page_text: str) -> list[dict]:
    """The whole request for job 4: the public page's text, nothing else."""
    instructions = (
        "Below is the text of an organization's privacy policy. Find how a person contacts the organization "
        "about data protection (its data protection officer or privacy team). Answer with JSON only: "
        '{"email": "...", "address": "...", "webform": "...", "reason": "a few words"}. '
        "address: the full postal address for data-protection requests, one line per part. webform: the full "
        "URL of a form for privacy requests. Use an empty string for anything the text does not state; "
        "never guess."
    )
    return [{"role": "system", "content": instructions}, {"role": "user", "content": page_text[: fetch.TEXT_MAX]}]


def _clean_email(value) -> str:
    value = str(value or "").strip().removeprefix("mailto:")
    try:
        validate_email(value)
    except ValidationError:
        return ""
    return value[:300]


def _clean_webform(value) -> str:
    value = str(value or "").strip()
    return value[:1000] if re.match(r"^https?://[^\s/]+\.[^\s]+$", value) else ""


def find_privacy_contact(url: str, settings=None) -> ContactProposal | None:
    """Job 4: fetch the public page at ``url`` and ask for its data-protection contact; or None.

    Raises ``fetch.FetchError`` when the page cannot be fetched, so the Operator learns why.
    """
    settings = _settings(settings)
    if not settings.usable:
        return None
    text = fetch.page_text(url)
    try:
        found = client.parse_json_object(client.chat(settings, contact_messages(text)))
    except client.LlmError as error:
        log.warning("Finding a privacy contact with the LLM failed: %s", error)
        return None
    email = _clean_email(found.get("email"))
    address = "\n".join(line.strip() for line in str(found.get("address") or "").strip().splitlines() if line.strip())
    webform = _clean_webform(found.get("webform"))
    if not (email or address or webform):
        return None
    return ContactProposal(email, address[:1000], webform, _reason(found), settings.source_label, url)
