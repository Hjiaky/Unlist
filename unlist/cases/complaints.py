# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""Complaint drafts (spec section 9, ticket #52). Unlist drafts; the Subject lodges.

``services.draft_complaint`` moves a Case to "Complaint draft" (only where the lifecycle allows
it: gentle first) and runs ``on_complaint_drafted``, which records where the Complaint starts.
The text itself is built on demand by ``build_complaint`` from the Case's history, so it always
matches the events; when the Subject marks it lodged (``mark_lodged``), the text is kept in the
"Complaint lodged" event. Nothing is stored outside ``CaseEvent.details`` and ``Attachment``.

Rules (decided by agent, ticket #52; each can be overturned)
--------------------------------------------------------------
- **Which Supervisory Authority** (``select_authority``): the Subject's own, by their country of
  residence, from the bundled authority records.
  - One authority for the country (every country but Germany): that one.
  - Germany has one authority per Land plus the federal one, and Unlist does not know the
    Subject's Land. Church and broadcasting authorities and Bavaria's public-sector authority
    (``DE_NOT_GENERAL``) are left out. Then, in this order: the Operator's choice for this Case;
    the Organization's own authority from its record, if it is a German one (the federal BfDI is
    picked only this way, because it is responsible only for telecoms and postal companies and
    federal bodies); the authority chosen for an earlier Complaint of the same Subject; else no
    authority, and the Operator chooses from the German ones.
  - The UK: the GB record, shown as "Information Commission" (it replaced the Information
    Commissioner's Office on 30 September 2026; the bundled record still has the old name).
  - A country without a record (or none set): no authority; the Operator chooses from all of them
    (Art. 77(1) GDPR also allows the authority where the Subject works or where the infringement
    happened).
- **Language** (``complaint_language``): German for Subjects living in Germany or Austria,
  English otherwise. A Complaint to the UK regulator is always English.
- **UK first step**: a UK Subject whose Case runs under UK rules (the Organization's jurisdiction
  is the UK) is first offered the short complaint to the Organization under DPA 2018 s.164A
  (``uk_complaint_to_organization``). It is handed over, never sent by Unlist; one click skips
  it. The regulator draft follows once the Organization's answer is recorded, or 30 days after
  the s.164A complaint was sent. For a UK Subject at an Organization under EU rules, s.164A is not
  offered: it is a duty under UK law, and the request itself invoked the EU GDPR.
- **Timeline**: the Case's events plus, for an English Complaint, the deadline engine's own
  ``Step`` texts for the current request (they are English only). A German Complaint uses short
  German lines built from the same ``Deadline``.
- **PDF**: no PDF library (that would be a new dependency). The Complaint page prints cleanly
  (``@media print`` in ``complaints.css``), so the browser can print it or save it as PDF.
- **Evidence bundle**: a ``.zip`` (standard library) with ``complaint.txt``, every sent draft
  (``.eml`` with headers for email, ``.txt`` for web forms and letters), the s.164A complaint, and
  the stored replies.
"""

import io
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, formataddr
from enum import StrEnum

from django.db import transaction
from django.utils import timezone

from unlist.cases import drafting, lifecycle, sending, storage, templating
from unlist.cases.deadlines import Jurisdiction
from unlist.cases.lifecycle import Action, DraftKind, State
from unlist.cases.models import CaseEvent, Draft

GERMAN_COUNTRIES = frozenset({"DE", "AT"})
UK_COUNTRIES = frozenset({"GB", "UK"})
UK_AUTHORITY = "gbico"
FEDERAL_DE_AUTHORITY = "debfdi"
# German authority records that do not take a resident's complaint about an Organization in
# general: church data protection, broadcasting, and the Bavarian authority for public bodies.
DE_NOT_GENERAL = frozenset(
    {"dekathbayddsb", "dekathdsz", "dekathffdsz", "dekathnordddsb", "dekathostddsb", "deekdbfd", "derf", "derfdw"}
    | {"debayldb"}
)
DISPLAY_NAMES = {UK_AUTHORITY: "Information Commission"}
UK_WAIT_DAYS = 30
COMPLAINT_STATES = (State.COMPLAINT_DRAFT, State.COMPLAINT_LODGED)

STAGE_KEY = "complaint_stage"
AUTHORITY_KEY = "complaint_authority"
UK_MESSAGE_ID_KEY = "uk_message_id"
NO_AUTHORITY = {"en": "[choose the Supervisory Authority]", "de": "[Aufsichtsbehörde auswählen]"}


class Stage(StrEnum):
    UK_ORGANIZATION = "uk_organization"
    """The s.164A complaint to the Organization is offered."""
    UK_SKIPPED = "uk_organization_skipped"
    UK_SENT = "uk_organization_sent"
    UK_ANSWERED = "uk_organization_answered"
    AUTHORITY = "authority"
    """Straight to the Supervisory Authority."""


class Ground(StrEnum):
    MISSED_DEADLINE = "missed_deadline"
    REFUSAL = "refusal"
    ID_DEMAND = "id_demand"
    RELISTED = "relisted"


def _error(message):
    from unlist.cases import services

    return services.CaseError(message)


def _today(on):
    return on or timezone.localdate()


# --- Authority and language --------------------------------------------------------------


@dataclass(frozen=True)
class AuthorityChoice:
    authority: object | None
    """The SupervisoryAuthority the Complaint is addressed to, or None until the Operator chooses."""
    candidates: tuple
    """The authorities the Operator may choose from."""
    rule: str
    """Why this authority (or why a choice is needed), in plain words."""

    @property
    def name(self) -> str:
        return authority_name(self.authority) if self.authority else ""

    @property
    def options(self) -> list[tuple[str, str]]:
        """(slug, display name) of the candidates, for a chooser."""
        return [(authority.slug, authority_name(authority)) for authority in self.candidates]


def authority_name(authority) -> str:
    return DISPLAY_NAMES.get(authority.slug, authority.name)


def subject_country(subject) -> str:
    code = (subject.country or "").strip().upper()
    return "GB" if code == "UK" else code


def complaint_language(subject) -> str:
    """German for Subjects living in Germany or Austria, English otherwise."""
    return "de" if subject_country(subject) in GERMAN_COUNTRIES else "en"


def _remembered_authority(subject, slugs) -> str | None:
    """The authority the Operator chose for an earlier Complaint of this Subject, if still a candidate."""
    events = CaseEvent.objects.filter(case__subject=subject, kind=CaseEvent.Kind.NOTE).order_by(
        "-occurred_on", "-recorded_at", "-id"
    )
    for event in events:
        slug = event.details.get(AUTHORITY_KEY)
        if slug in slugs:
            return slug
    return None


def select_authority(subject, organization=None, chosen: str = "") -> AuthorityChoice:
    """The Subject's own Supervisory Authority (see the module docstring for the rule)."""
    from unlist.organizations.models import SupervisoryAuthority

    everything = list(SupervisoryAuthority.objects.order_by("name"))
    country = subject_country(subject)
    in_country = [a for a in everything if country and country.lower() in [c.lower() for c in a.countries or []]]
    if country == "DE":
        in_country = [a for a in in_country if a.slug not in DE_NOT_GENERAL]
    pool = in_country or everything
    by_slug = {a.slug: a for a in pool}
    candidates = tuple(pool)
    if chosen and chosen in by_slug:
        return AuthorityChoice(by_slug[chosen], candidates, "Chosen by the Operator.")
    if len(in_country) == 1:
        return AuthorityChoice(
            in_country[0], candidates, f"The Supervisory Authority of the Subject's country of residence ({country})."
        )
    if not in_country:
        return AuthorityChoice(
            None,
            candidates,
            f"Unlist has no Supervisory Authority for the Subject's country of residence ({country or 'not set'}). "
            "Choose one: Art. 77(1) GDPR also allows the authority where the Subject works or where the "
            "infringement took place.",
        )
    own = (getattr(organization, "supervisory_authority", "") or "").strip().lower()
    if own in by_slug:
        return AuthorityChoice(
            by_slug[own], candidates, "The German authority responsible for this Organization, from its record."
        )
    remembered = _remembered_authority(subject, by_slug)
    if remembered:
        return AuthorityChoice(by_slug[remembered], candidates, "The authority chosen for an earlier Complaint.")
    return AuthorityChoice(
        None,
        candidates,
        "Germany has a data-protection authority for each Land, and Unlist does not know the Subject's Land. Choose "
        "the authority of the Land where the Subject lives. The federal authority (BfDI) is only responsible for "
        "telecoms and postal companies and federal bodies.",
    )


def complaint_jurisdiction(subject, authority) -> str:
    if authority is not None:
        return Jurisdiction.UK if authority.slug == UK_AUTHORITY else Jurisdiction.EU
    return Jurisdiction.UK if subject_country(subject) in UK_COUNTRIES else Jurisdiction.EU


# --- Reading the Case --------------------------------------------------------------------


def _events(case) -> list[CaseEvent]:
    return list(case.events.order_by("occurred_on", "recorded_at", "id"))


def _drafted_index(events) -> int | None:
    for index in range(len(events) - 1, -1, -1):
        if events[index].kind == CaseEvent.Kind.COMPLAINT_DRAFTED:
            return index
    return None


def _history(case, events) -> list[CaseEvent]:
    """The events the Complaint is about: those before the latest "Complaint drafted", if drafted."""
    index = _drafted_index(events) if case.state in COMPLAINT_STATES else None
    return events if index is None else events[:index]


def _since_drafted(events) -> list[CaseEvent]:
    index = _drafted_index(events)
    return [] if index is None else events[index:]


def _sent_kind(event) -> str | None:
    return event.details.get("draft_kind") if event.kind == CaseEvent.Kind.SENT else None


def complaint_ground(case, events=None) -> Ground | None:
    """What the Complaint is about, from the latest decisive event before it."""
    history = _history(case, events if events is not None else _events(case))
    suppression_before = [i for i, e in enumerate(history) if e.suppression_confirmed]
    for index in range(len(history) - 1, -1, -1):
        kind = history[index].kind
        if kind == CaseEvent.Kind.REFUSED:
            return Ground.REFUSAL
        if kind == CaseEvent.Kind.ID_OR_DETAILS_ASKED:
            return Ground.ID_DEMAND
        if kind == CaseEvent.Kind.LISTING_FOUND and any(i < index for i in suppression_before):
            return Ground.RELISTED
        if kind == CaseEvent.Kind.OVERDUE:
            return Ground.MISSED_DEADLINE
    return None


def check_allowed(case) -> None:
    """Gentle first: raise ``IllegalStep`` unless the Case has, or may now have, a Complaint."""
    from unlist.cases import services

    if case.state in COMPLAINT_STATES:
        return
    result = lifecycle.transition(services.case_state(case), Action.DRAFT_COMPLAINT)
    if not result.ok:
        raise services.IllegalStep(result.error)


def _latest(events, kind) -> CaseEvent | None:
    found = [event for event in events if event.kind == kind]
    return found[-1] if found else None


@dataclass
class _Facts:
    """What the texts need, gathered once."""

    case: object
    lang: str
    law: str
    ground: Ground | None
    request_event: CaseEvent | None = None
    request_draft: Draft | None = None
    request_kind: str = DraftKind.ACCESS_REQUEST
    reminders: list = field(default_factory=list)
    pushbacks: list = field(default_factory=list)
    asks: list = field(default_factory=list)
    reconsiders: list = field(default_factory=list)
    refusal: CaseEvent | None = None
    suppression: CaseEvent | None = None
    listing: CaseEvent | None = None
    deadline: object = None
    uk_sent: CaseEvent | None = None
    uk_answered: CaseEvent | None = None
    replies: int = 0

    def d(self, day) -> str:
        return drafting.format_date(day, self.lang)


REPLY_KINDS = (
    CaseEvent.Kind.NOTHING_HELD,
    CaseEvent.Kind.LISTING_FOUND,
    CaseEvent.Kind.REMOVED,
    CaseEvent.Kind.REFUSED,
    CaseEvent.Kind.ID_OR_DETAILS_ASKED,
    CaseEvent.Kind.EXTENSION_ANNOUNCED,
)


def _law_name(organization, lang) -> str:
    """How the texts cite the law the request invoked (by the Organization's jurisdiction)."""
    if drafting.jurisdiction_for(organization) == Jurisdiction.UK:
        return "UK GDPR"
    return "DSGVO" if lang == "de" else "GDPR"


def _facts(case, lang, events) -> _Facts:
    from unlist.cases import services

    history = _history(case, events)
    facts = _Facts(case=case, lang=lang, law=_law_name(case.organization, lang), ground=complaint_ground(case, events))
    start = 0
    for index, event in enumerate(history):
        if _sent_kind(event) in (DraftKind.ACCESS_REQUEST, DraftKind.REMOVAL_REQUEST):
            facts.request_event, start = event, index
    if facts.request_event is not None:
        facts.request_kind = _sent_kind(facts.request_event)
        facts.request_draft = case.drafts.filter(pk=facts.request_event.details.get("draft")).first()
    current = history[start:]
    facts.reminders = [e for e in current if _sent_kind(e) == DraftKind.REMINDER]
    facts.pushbacks = [e for e in current if _sent_kind(e) == DraftKind.ID_PUSHBACK]
    facts.reconsiders = [e for e in current if _sent_kind(e) == DraftKind.RECONSIDER]
    facts.asks = [e for e in current if e.kind == CaseEvent.Kind.ID_OR_DETAILS_ASKED]
    facts.refusal = _latest(current, CaseEvent.Kind.REFUSED)
    facts.listing = _latest(current, CaseEvent.Kind.LISTING_FOUND)
    facts.suppression = next((e for e in reversed(history) if e.suppression_confirmed), None)
    facts.replies = sum(1 for e in history if e.kind in REPLY_KINDS)
    facts.deadline = services.case_deadline(case)
    for event in _since_drafted(events):
        stage = event.details.get(STAGE_KEY)
        if stage == Stage.UK_SENT:
            facts.uk_sent = event
        elif stage == Stage.UK_ANSWERED:
            facts.uk_answered = event
    return facts


def _sender(case, facts=None) -> str:
    from unlist.cases import services

    if facts is not None and facts.request_draft is not None:
        return facts.request_draft.sender
    draft = case.drafts.filter(status=Draft.Status.SENT).order_by("-id").first()
    return draft.sender if draft else services._sender(case.subject)


# --- Texts -------------------------------------------------------------------------------

_REQUEST_WORDS = {
    "en": {
        DraftKind.ACCESS_REQUEST: "access request (Article 15 {law})",
        DraftKind.REMOVAL_REQUEST: "erasure request (Article 17 {law})",
    },
    "de": {
        DraftKind.ACCESS_REQUEST: "Auskunftsersuchen (Art. 15 {law})",
        DraftKind.REMOVAL_REQUEST: "Löschersuchen (Art. 17 {law})",
    },
}
_KIND_WORDS = {
    "en": {
        DraftKind.ACCESS_REQUEST: "Access request",
        DraftKind.REMOVAL_REQUEST: "Erasure request",
        DraftKind.REMINDER: "Reminder",
        DraftKind.DETAILS_REPLY: "Reply with the details asked for",
        DraftKind.ID_PUSHBACK: "Reply to the demand for proof of identity",
        DraftKind.RECONSIDER: "Request to reconsider the refusal",
    },
    "de": {
        DraftKind.ACCESS_REQUEST: "Auskunftsersuchen",
        DraftKind.REMOVAL_REQUEST: "Löschersuchen",
        DraftKind.REMINDER: "Erinnerung",
        DraftKind.DETAILS_REPLY: "Antwort mit den erbetenen Angaben",
        DraftKind.ID_PUSHBACK: "Antwort auf die Forderung nach einem Identitätsnachweis",
        DraftKind.RECONSIDER: "Bitte um erneute Prüfung der Ablehnung",
    },
}


def _request_words(facts) -> str:
    kind = facts.request_kind if facts.request_kind in _REQUEST_WORDS["en"] else DraftKind.ACCESS_REQUEST
    return _REQUEST_WORDS[facts.lang][kind].format(law=facts.law)


def _how(event, drafts, lang) -> str:
    channel = event.details.get("channel", "email")
    recipient = event.details.get("recipient", "")
    draft = drafts.get(event.details.get("draft"))
    sender = event.details.get("sender") or (draft.sender if draft else "")
    if channel == Draft.Channel.WEBFORM:
        return f"über das Webformular {recipient}" if lang == "de" else f"through the web form {recipient}"
    if channel == Draft.Channel.LETTER:
        return "per Post" if lang == "de" else "by post"
    if lang == "de":
        return f"von {sender} an {recipient}"
    return f"from {sender} to {recipient}"


def _event_line(event, drafts, facts) -> str | None:
    lang, law, kind = facts.lang, facts.law, event.kind
    de = lang == "de"
    sent = _sent_kind(event)
    if sent:
        how = _how(event, drafts, lang)
        words = {
            DraftKind.ACCESS_REQUEST: (
                "Auskunftsersuchen (Art. 15 {law}) gesendet",
                "Access request (Article 15 {law}) sent",
            ),
            DraftKind.REMOVAL_REQUEST: (
                "Löschersuchen (Art. 17 {law}) gesendet",
                "Erasure request (Article 17 {law}) sent",
            ),
            DraftKind.REMINDER: ("Erinnerung gesendet", "Reminder sent"),
            DraftKind.DETAILS_REPLY: ("Die erbetenen Angaben gesendet", "Sent the details the organisation asked for,"),
            DraftKind.ID_PUSHBACK: (
                "Auf die Forderung nach einem Identitätsnachweis geantwortet und andere Wege der Bestätigung angeboten",
                "Replied to the demand for proof of identity, offering other ways to confirm my identity,",
            ),
            DraftKind.RECONSIDER: (
                "Um erneute Prüfung der Ablehnung gebeten",
                "Asked the organisation to reconsider its refusal,",
            ),
        }.get(sent)
        if words is None:
            return None
        text = words[0 if de else 1].format(law=law)
        if de and sent == DraftKind.REMINDER:
            return (
                f"{text} ({how}), mit einer Frist von 14 Tagen bis {facts.d(event.occurred_on + timedelta(days=14))}."
            )
        return f"{text} ({how})." if de else f"{text} {how}."
    if kind == CaseEvent.Kind.NOTHING_HELD:
        return (
            "Der Verantwortliche antwortete, er verarbeite keine Daten über mich."
            if de
            else "The organisation answered that it holds no personal data about me."
        )
    if kind == CaseEvent.Kind.LISTING_FOUND:
        return (
            "Der Verantwortliche übersandte die über mich gespeicherten Daten."
            if de
            else "The organisation sent the personal data it holds about me."
        )
    if kind == CaseEvent.Kind.REMOVED:
        if de:
            text = "Der Verantwortliche bestätigte die Löschung meiner Daten."
            if event.suppression_confirmed:
                text += " Er bestätigte, einen minimalen Sperrvermerk zu führen, damit er mich nicht erneut aufnimmt."
            return text
        text = "The organisation confirmed the erasure of my personal data."
        if event.suppression_confirmed:
            text += " It confirmed that it keeps a minimal suppression record so that it does not list me again."
        return text
    if kind == CaseEvent.Kind.REFUSED:
        exception = " ".join((event.exception_text or "").split())
        if de:
            return (
                f"Der Verantwortliche lehnte ab oder erfüllte nur teilweise und berief sich auf: „{exception}“."
                if exception
                else "Der Verantwortliche lehnte ab oder erfüllte nur teilweise, ohne einen Rechtsgrund zu nennen."
            )
        return (
            f"The organisation refused, or complied only in part, relying on: “{exception}”."
            if exception
            else "The organisation refused, or complied only in part, without naming a legal reason."
        )
    if kind == CaseEvent.Kind.ID_OR_DETAILS_ASKED:
        return (
            "Der Verantwortliche verlangte einen Identitätsnachweis oder weitere Angaben."
            if de
            else "The organisation asked for proof of identity or further details."
        )
    if kind == CaseEvent.Kind.EXTENSION_ANNOUNCED:
        reasons = bool(event.details.get("with_reasons"))
        if de:
            return "Der Verantwortliche kündigte eine Fristverlängerung an" + (
                " mit Gründen." if reasons else ", ohne Gründe zu nennen."
            )
        return "The organisation announced an extension of the deadline" + (
            " with reasons." if reasons else " without giving reasons."
        )
    if kind == CaseEvent.Kind.BOUNCE:
        return (
            "Die E-Mail kam als unzustellbar zurück."
            if de
            else "The email bounced; the organisation did not receive it."
        )
    stage = event.details.get(STAGE_KEY)
    if stage == Stage.UK_SENT:
        how = _how(event, drafts, "en")
        return f"Complaint to the organisation under section 164A of the Data Protection Act 2018 sent {how}."
    if stage == Stage.UK_ANSWERED:
        return "The organisation answered the complaint under section 164A of the Data Protection Act 2018."
    return None


# Events the deadline engine's steps describe for the current request (an English timeline
# takes the step instead of a second line).
def _covered_by_steps(event) -> bool:
    return _sent_kind(event) in (DraftKind.REMINDER, DraftKind.DETAILS_REPLY, DraftKind.ID_PUSHBACK) or event.kind in (
        CaseEvent.Kind.ID_OR_DETAILS_ASKED,
        CaseEvent.Kind.EXTENSION_ANNOUNCED,
    )


def _german_deadline_lines(deadline, facts) -> list[tuple[date, str]]:
    if deadline is None:
        return []
    if deadline.paused:
        return [
            (
                deadline.paused_since,
                "Seit diesem Tag ist die Frist angehalten, weil der Verantwortliche einen Identitätsnachweis oder "
                "weitere Angaben verlangt.",
            )
        ]
    rule = "Art. 12 Abs. 3 DSGVO" if facts.law == "DSGVO" else f"Art. 12 Abs. 3 {facts.law}"
    extended = " (nach einer wirksam angekündigten Verlängerung um zwei Monate)" if deadline.extended else ""
    return [(deadline.due_date, f"Ende der Frist für die Antwort ({rule}){extended}.")]


def timeline(case, facts, events) -> list[str]:
    """Dated lines, oldest first: the Case's events and, in English, the deadline engine's steps."""
    history = _history(case, events) + [e for e in _since_drafted(events) if e.details.get(STAGE_KEY)]
    drafts = {draft.pk: draft for draft in case.drafts.all()}
    # The deadline matters for a missed deadline and for an ID demand; after a refusal or a
    # returned Listing the Organization did answer, so its deadline would only add noise.
    deadline = facts.deadline if facts.ground in (Ground.MISSED_DEADLINE, Ground.ID_DEMAND) else None
    use_steps = facts.lang == "en" and deadline is not None
    round_start = None
    if deadline is not None:
        from unlist.cases import services

        round_start = next(
            (i for i in range(len(history) - 1, -1, -1) if _sent_kind(history[i]) in services.ROUND_STARTS), None
        )
    entries: list[tuple[date, int, str]] = []
    for index, event in enumerate(history):
        if use_steps and round_start is not None and index > round_start and _covered_by_steps(event):
            continue
        text = _event_line(event, drafts, facts)
        if text:
            entries.append((event.occurred_on, 0, text))
    if use_steps:
        entries.extend((step.on, 1, step.text) for step in deadline.steps)
    elif facts.lang == "de":
        entries.extend((day, 1, text) for day, text in _german_deadline_lines(deadline, facts))
    entries.sort(key=lambda entry: (entry[0], entry[1]))
    return [f"{facts.d(day)}: {text}" for day, _order, text in entries]


def _infringement(facts) -> str:
    """What went wrong, in plain words, addressed to the Supervisory Authority."""
    de, d, org = facts.lang == "de", facts.d, facts.case.organization.name
    law = facts.law
    req = _request_words(facts)
    sent = d(facts.request_event.occurred_on) if facts.request_event else ""
    access = facts.request_kind == DraftKind.ACCESS_REQUEST
    deadline = facts.deadline
    if facts.ground is Ground.REFUSAL:
        refusal = facts.refusal
        exception = " ".join((refusal.exception_text or "").split()) if refusal else ""
        when = d(refusal.occurred_on) if refusal else ""
        if de:
            text = f"Am {sent} habe ich bei {org} ein {req} gestellt. "
            text += f"Am {when} hat {org} es abgelehnt oder nur teilweise erfüllt"
            text += (
                f" und sich dabei auf Folgendes berufen: „{exception}“."
                if exception
                else ", ohne einen Rechtsgrund zu nennen."
            )
            if facts.reconsiders:
                text += f" Am {d(facts.reconsiders[-1].occurred_on)} habe ich um erneute Prüfung gebeten."
            return text + " Ich bitte Sie zu prüfen, ob die Ablehnung rechtmäßig ist."
        text = f"I made an {req} to {org} on {sent}. On {when} it refused it, or complied only in part,"
        text += f" relying on: “{exception}”." if exception else " without naming a legal reason."
        if facts.reconsiders:
            text += f" I asked it to reconsider on {d(facts.reconsiders[-1].occurred_on)}."
        return text + " I ask you to examine whether the refusal is lawful."
    if facts.ground is Ground.ID_DEMAND:
        first = d(facts.asks[0].occurred_on) if facts.asks else ""
        again = d(facts.asks[-1].occurred_on) if facts.asks else ""
        pushback = d(facts.pushbacks[-1].occurred_on) if facts.pushbacks else ""
        if de:
            return (
                f"Am {sent} habe ich bei {org} ein {req} gestellt. Am {first} verlangte {org} einen Identitätsnachweis "
                f"oder weitere Angaben. Am {pushback} habe ich erklärt, dass die Anfrage von der E-Mail-Adresse kommt, "
                f"unter der {org} mich kennt, und andere Wege angeboten, meine Identität zu bestätigen. Am {again} hat "
                f"{org} die Forderung wiederholt. Nach Art. 12 Abs. 6 {law} darf der Verantwortliche zusätzliche "
                "Informationen nur bei begründeten Zweifeln an der Identität verlangen, und nur soweit sie zur "
                "Bestätigung nötig sind. Die Forderung geht darüber hinaus und verhindert die Beantwortung meiner "
                "Anfrage."
            )
        return (
            f"I made an {req} to {org} on {sent}. On {first} it asked for proof of identity or further details. On "
            f"{pushback} I explained that the request came from the email address it knows me by, and offered other "
            f"ways to confirm my identity. On {again} it repeated the demand. Under Article 12(6) {law} it may ask "
            "for additional information only where it has reasonable doubts about my identity, and only as far as "
            "needed to confirm it. I believe the demand goes beyond that and keeps my request from being answered."
        )
    if facts.ground is Ground.RELISTED:
        removed = d(facts.suppression.occurred_on) if facts.suppression else ""
        found = d(facts.listing.occurred_on) if facts.listing else ""
        if de:
            return (
                f"Am {removed} bestätigte {org}, meine personenbezogenen Daten gelöscht zu haben und einen minimalen "
                "Sperrvermerk zu führen, damit meine Daten nicht erneut erhoben und veröffentlicht werden. Auf mein "
                f"neues Auskunftsersuchen vom {sent} zeigte {org} am {found}, dass es meine Daten wieder verarbeitet. "
                f"Ich gehe davon aus, dass meine Daten trotz der bestätigten Löschung (Art. 17 {law}) erneut "
                "verarbeitet werden."
            )
        return (
            f"On {removed} {org} confirmed that it had erased my personal data and that it keeps a minimal "
            "suppression record so that it does not collect and list my data again. In answer to my new access "
            f"request of {sent}, it showed on {found} that it holds my data again. I believe it processes my data "
            f"again despite the erasure it confirmed (Article 17 {law})."
        )
    # Missed deadline (overdue after a reminder)
    if law == "UK GDPR":
        rule = "Art. 12 Abs. 3 und Art. 12A UK GDPR" if de else "Articles 12(3) and 12A UK GDPR"
    else:
        rule = f"Art. 12 Abs. 3 {law}" if de else f"Article 12(3) {law}"
    due = d(deadline.due_date) if deadline is not None and deadline.due_date else ""
    reminder = facts.reminders[-1].occurred_on if facts.reminders else None
    right_de = "mein Recht auf Auskunft (Art. 15" if access else "mein Recht auf Löschung (Art. 17"
    right_en = "my right of access (Article 15" if access else "my right to erasure (Article 17"
    if de:
        text = (
            f"Am {sent} habe ich bei {org} ein {req} gestellt. Die Antwort war innerhalb eines Monats fällig ({rule})"
        )
        text += f", also bis {due}." if due else "."
        text += f" {org} hat nicht geantwortet."
        if reminder:
            text += (
                f" Auf meine Erinnerung vom {d(reminder)}, mit Frist bis {d(reminder + timedelta(days=14))}, kam "
                "ebenfalls keine Antwort."
            )
        return text + f" Das verletzt {right_de} {law}) und {rule}."
    text = f"I made an {req} to {org} on {sent}. It had to answer within one month ({rule})"
    text += f", by {due}." if due else "."
    text += " It has not answered."
    if reminder:
        text += (
            f" I sent a reminder on {d(reminder)}, giving it until {d(reminder + timedelta(days=14))}, and it has not "
            "answered that either."
        )
    return text + f" This infringes {right_en} {law}) and {rule}."


def _remedy(facts) -> str:
    de, org, law = facts.lang == "de", facts.case.organization.name, facts.law
    access = facts.request_kind == DraftKind.ACCESS_REQUEST
    if facts.ground is Ground.RELISTED:
        want_de = f"{org} anzuweisen, meine Daten erneut zu löschen und nicht wieder zu erheben oder zu veröffentlichen"
        want_en = f"ask {org} to erase my personal data again and to stop collecting and listing it"
    elif access:
        want_de = f"{org} anzuweisen, mein Auskunftsersuchen vollständig zu beantworten (Art. 15 {law})"
        want_en = f"ask {org} to answer my access request in full (Article 15 {law})"
    else:
        want_de = (
            f"{org} anzuweisen, meine personenbezogenen Daten wie verlangt zu löschen und mir dies zu bestätigen "
            f"(Art. 17 {law})"
        )
        want_en = (
            f"ask {org} to erase my personal data as I requested and to confirm the erasure to me (Article 17 {law})"
        )
    if de:
        return (
            f"Bitte prüfen Sie meine Beschwerde und, wenn Sie sie für begründet halten, {want_de}. Bitte informieren "
            "Sie mich über den Stand und das Ergebnis."
        )
    return (
        f"Please examine my complaint and, where you find it justified, {want_en}. Please keep me informed of the "
        "progress and the outcome."
    )


def _prior_contact(facts) -> str:
    de, d, org = facts.lang == "de", facts.d, facts.case.organization.name
    if facts.request_event is None:
        return ""
    parts = [
        (f"mein {_request_words(facts)} vom {d(facts.request_event.occurred_on)}")
        if de
        else f"my {_request_words(facts)} of {d(facts.request_event.occurred_on)}"
    ]
    for event in facts.reminders:
        parts.append(f"eine Erinnerung vom {d(event.occurred_on)}" if de else f"a reminder of {d(event.occurred_on)}")
    for event in facts.pushbacks:
        parts.append(
            f"meine Antwort auf die Forderung nach einem Identitätsnachweis vom {d(event.occurred_on)}"
            if de
            else f"my reply to its demand for proof of identity of {d(event.occurred_on)}"
        )
    for event in facts.reconsiders:
        parts.append(
            f"meine Bitte um erneute Prüfung vom {d(event.occurred_on)}"
            if de
            else f"my request to reconsider of {d(event.occurred_on)}"
        )
    if facts.uk_sent:
        parts.append(
            "a complaint to the organisation under section 164A of the Data Protection Act 2018 of "
            + d(facts.uk_sent.occurred_on)
        )
    listed = ", ".join(parts[:-1]) + (" und " if de else " and ") + parts[-1] if len(parts) > 1 else parts[0]
    if de:
        text = f"Ich habe mich vor dieser Beschwerde an {org} gewandt: {listed}."
        text += " Die Antworten sind oben aufgeführt und beigefügt." if facts.replies else " Es kam keine Antwort."
        return text
    text = f"I contacted {org} before this complaint: {listed}."
    if facts.uk_answered:
        text += f" It answered the section 164A complaint on {d(facts.uk_answered.occurred_on)}."
    if facts.replies:
        text += " Its replies are listed above and attached."
    elif not facts.uk_answered:
        text += " It has not replied."
    return text


def _organization_contacts(organization, lang) -> list[str]:
    de = lang == "de"
    labels = (
        ("email", "Datenschutzkontakt (E-Mail)" if de else "Privacy contact (email)"),
        ("webform", "Webformular" if de else "Web form"),
        ("address", "Anschrift" if de else "Postal address"),
        ("phone", "Telefon" if de else "Telephone"),
        ("web", "Website"),
    )
    lines = []
    for attribute, label in labels:
        value = " ".join((getattr(organization, attribute, "") or "").replace("\n", ", ").split())
        if value:
            lines.append(f"{label}: {value}")
    if organization.runs:
        lines.append(f"{'Marken und Dienste' if de else 'Brands and services'}: {', '.join(organization.runs)}")
    if organization.domains:
        lines.append(f"Domains: {', '.join(organization.domains)}")
    countries = drafting.countries(organization)
    if countries:
        lines.append(f"{'Land' if de else 'Country'}: {', '.join(countries)}")
    return lines


# --- Evidence ----------------------------------------------------------------------------


@dataclass
class EvidenceItem:
    filename: str
    description: str
    content: Callable[[], bytes | None]


def _draft_text(draft) -> bytes:
    lines = [
        f"Channel: {draft.get_channel_display()}",
        f"From: {draft.case.subject.name} <{draft.sender}>",
        f"To: {draft.recipient}",
        f"Sent on: {draft.sent_on.isoformat() if draft.sent_on else ''}",
        f"Subject: {draft.subject_line}",
        "",
        draft.body,
    ]
    return "\n".join(lines).encode("utf-8")


def _uk_letter_eml(case, event) -> bytes:
    details = event.details
    message = EmailMessage()
    message["From"] = formataddr((case.subject.name, details.get("sender", "")))
    message["To"] = details.get("recipient", "")
    message["Subject"] = details.get("subject_line", "")
    message["Date"] = format_datetime(event.recorded_at)
    if details.get("message_id"):
        message["Message-ID"] = details["message_id"]
    message.set_content(details.get("body", ""))
    return bytes(message)


def _read_attachment(attachment):
    def read():
        path = storage.attachment_path(attachment)
        return path.read_bytes() if path.is_file() else None

    return read


def evidence(case, facts, events) -> list[EvidenceItem]:
    """The files that go with the Complaint, in the order they are listed."""
    de, d = facts.lang == "de", facts.d
    items: list[EvidenceItem] = []

    def name(stem):
        return f"{len(items) + 1:02d}-{stem}"

    sent = case.drafts.filter(status=Draft.Status.SENT).order_by("sent_on", "id")
    for draft in sent:
        words = _KIND_WORDS[facts.lang].get(draft.kind, draft.get_kind_display())
        when = d(draft.sent_on)
        if draft.channel == Draft.Channel.EMAIL:
            description = (
                f"{words} vom {when}, wie gesendet, mit E-Mail-Kopfzeilen (Absender, Empfänger, Datum, Message-ID)"
                if de
                else f"{words} of {when}, as sent, with its email headers (sender, recipient, date, Message-ID)"
            )
            items.append(
                EvidenceItem(
                    name(sending.eml_filename(draft)), description, lambda draft=draft: sending.eml_bytes(draft)
                )
            )
        else:
            how = draft.get_channel_display().lower()
            description = (
                f"{words} vom {when}, Text wie gesendet ({how})"
                if de
                else f"{words} of {when}, the text as sent ({how})"
            )
            items.append(
                EvidenceItem(
                    name(f"{case.reference}-{draft.kind}.txt"), description, lambda draft=draft: _draft_text(draft)
                )
            )
    if facts.uk_sent is not None:
        uk_event = facts.uk_sent
        items.append(
            EvidenceItem(
                name(f"{case.reference}-uk-complaint-to-organization.eml"),
                f"Complaint to the organisation under section 164A of the Data Protection Act 2018 of "
                f"{d(uk_event.occurred_on)}, with its email headers",
                lambda: _uk_letter_eml(case, uk_event),
            )
        )
    for attachment in case.attachments.select_related("event").order_by("uploaded_at", "id"):
        if not storage.attachment_path(attachment).is_file():
            continue
        day = attachment.event.occurred_on if attachment.event else timezone.localdate(attachment.uploaded_at)
        description = (
            f"Schreiben des Verantwortlichen, eingegangen am {d(day)}"
            if de
            else f"Correspondence from the organisation, received on {d(day)}"
        )
        items.append(
            EvidenceItem(name(storage.safe_name(attachment.original_name)), description, _read_attachment(attachment))
        )
    return items


# --- The Complaint -----------------------------------------------------------------------


@dataclass
class Complaint:
    case: object
    ground: Ground | None
    lang: str
    jurisdiction: str
    choice: AuthorityChoice
    subject_line: str
    body: str
    evidence: list[EvidenceItem]
    timeline: list[str]

    @property
    def authority(self):
        return self.choice.authority

    @property
    def text(self) -> str:
        return f"Subject: {self.subject_line}\n\n{self.body}"


def current_authority_slug(case, events=None) -> str:
    """The authority the Operator chose for this Case's current Complaint, or empty."""
    for event in reversed(_since_drafted(events if events is not None else _events(case))):
        if event.details.get(AUTHORITY_KEY):
            return event.details[AUTHORITY_KEY]
    return ""


def build_complaint(case, *, lang: str | None = None) -> Complaint:
    """The Complaint text and its evidence, from the Case's history. Refuses unless allowed (gentle first)."""
    check_allowed(case)
    events = _events(case)
    subject, organization = case.subject, case.organization
    choice = select_authority(subject, organization, current_authority_slug(case, events))
    jurisdiction = complaint_jurisdiction(subject, choice.authority)
    lang = templating.template_language("complaint", lang or complaint_language(subject), jurisdiction)
    facts = _facts(case, lang, events)
    items = evidence(case, facts, events)
    lines = timeline(case, facts, events)
    context = {
        "jurisdiction": str(jurisdiction),
        "reference": case.reference,
        "subject_name": subject.name,
        "subject_email": _sender(case, facts),
        "organization_name": organization.name,
        "supervisory_authority_name": choice.name or NO_AUTHORITY.get(lang, NO_AUTHORITY["en"]),
        "subject_contact_details": _subject_lines(subject, lang),
        "organization_contacts": _organization_contacts(organization, lang),
        "timeline": lines,
        "infringement": _infringement(facts),
        "remedy": _remedy(facts),
        "prior_contact": _prior_contact(facts),
        "attachments": [f"{item.filename}: {item.description}" for item in items],
    }
    subject_line, body = templating.render("complaint", lang, context)
    return Complaint(case, facts.ground, lang, str(jurisdiction), choice, subject_line, body, items, lines)


def _subject_lines(subject, lang) -> list[str]:
    if subject.parental_responsibility:
        label = "Sorgeberechtigte Person" if lang == "de" else "Person with parental responsibility"
        return [f"{label}: {subject.parental_responsibility}"]
    return []


def evidence_zip(complaint: Complaint) -> bytes:
    """The evidence bundle: ``complaint.txt`` and every file the Complaint lists."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("complaint.txt", complaint.text)
        for item in complaint.evidence:
            data = item.content()
            if data is not None:
                archive.writestr(item.filename, data)
    return buffer.getvalue()


def evidence_filename(case) -> str:
    return f"{case.reference}-complaint-evidence.zip"


# --- UK first step and progress ----------------------------------------------------------


def uk_first_step(case) -> bool:
    """A UK Subject at an Organization under UK rules: offer the s.164A complaint first."""
    return subject_country(case.subject) in UK_COUNTRIES and drafting.jurisdiction_for(case.organization) == "UK"


@dataclass(frozen=True)
class Progress:
    stage: Stage
    sent_on: date | None = None
    """When the s.164A complaint was sent."""
    wait_until: date | None = None
    """Until when the regulator draft waits for the Organization's answer to the s.164A complaint."""
    authority_ready: bool = True
    """Whether the Complaint to the Supervisory Authority is offered now."""


def progress(case, *, today: date | None = None, events=None) -> Progress:
    """Where the Complaint stands; for the UK, whether the s.164A step still comes first."""
    stage, sent_on = Stage.AUTHORITY, None
    for event in _since_drafted(events if events is not None else _events(case)):
        if event.details.get(STAGE_KEY):
            stage = Stage(event.details[STAGE_KEY])
            if stage == Stage.UK_SENT:
                sent_on = event.occurred_on
    if stage == Stage.UK_ORGANIZATION:
        return Progress(stage, authority_ready=False)
    if stage == Stage.UK_SENT:
        wait_until = sent_on + timedelta(days=UK_WAIT_DAYS)
        return Progress(stage, sent_on, wait_until, authority_ready=_today(today) >= wait_until)
    return Progress(stage, sent_on)


def _uk_context(case, events):
    facts = _facts(case, "en", events)
    original = facts.request_kind if facts.request_kind in templating.ORIGINAL_KINDS else DraftKind.ACCESS_REQUEST
    d = facts.d
    org_request = "access request" if original == DraftKind.ACCESS_REQUEST else "erasure request"
    sent = d(facts.request_event.occurred_on) if facts.request_event else ""
    if facts.ground is Ground.REFUSAL and facts.refusal:
        exception = " ".join((facts.refusal.exception_text or "").split())
        infringement = f"On {d(facts.refusal.occurred_on)} you refused my request, or complied only in part"
        infringement += f", relying on: “{exception}”." if exception else ", without naming a legal reason."
        infringement += " I ask you to review whether this justifies the refusal."
    elif facts.ground is Ground.ID_DEMAND and facts.asks:
        pushback = d(facts.pushbacks[-1].occurred_on) if facts.pushbacks else ""
        infringement = (
            f"You asked for proof of identity or further details on {d(facts.asks[0].occurred_on)}. On {pushback} I "
            "explained that my request came from the email address you know me by, and offered other ways to confirm "
            f"my identity, but on {d(facts.asks[-1].occurred_on)} you repeated the demand. Under Article 12(6) UK GDPR "
            "you may ask for additional information only where you have reasonable doubts about my identity."
        )
    elif facts.ground is Ground.RELISTED:
        removed = d(facts.suppression.occurred_on) if facts.suppression else ""
        found = d(facts.listing.occurred_on) if facts.listing else ""
        infringement = (
            f"On {removed} you confirmed that you had erased my personal data and keep a minimal suppression record "
            f"so that you do not collect and list it again. Your answer of {found} to my new access request of {sent} "
            "shows that you hold my data again."
        )
    else:
        due = d(facts.deadline.due_date) if facts.deadline is not None and facts.deadline.due_date else ""
        infringement = f"You did not answer my {org_request} within one month"
        infringement += f", by {due}," if due else ""
        infringement += " as Articles 12(3) and 12A UK GDPR require"
        if facts.reminders:
            infringement += f", and you did not answer my reminder of {d(facts.reminders[-1].occurred_on)} either"
        infringement += "."
    if facts.ground is Ground.RELISTED:
        remedy = (
            "Please erase my personal data again, keep only the minimal suppression record, and tell me how my data "
            "came to be listed again."
        )
    elif original == DraftKind.ACCESS_REQUEST:
        remedy = "Please answer my access request in full."
    else:
        remedy = "Please erase my personal data as I requested and confirm this to me."
    return facts, {
        "jurisdiction": "UK",
        "reference": case.reference,
        "subject_name": case.subject.name,
        "subject_email": _sender(case, facts),
        "organization_name": case.organization.name,
        "original_kind": str(original),
        "original_date": sent,
        "infringement": infringement,
        "remedy": remedy,
    }


@dataclass(frozen=True)
class UkLetter:
    subject_line: str
    body: str
    sender: str
    channel: str
    recipient: str
    message_id: str


def uk_letter(case) -> UkLetter:
    """The short complaint to the Organization under DPA 2018 s.164A (UK only)."""
    check_allowed(case)
    events = _events(case)
    facts, context = _uk_context(case, events)
    subject_line, body = templating.render("uk_complaint_to_organization", "en", context)
    channel, recipient = drafting.choose_channel(case.organization)
    drafted = events[_drafted_index(events)] if _drafted_index(events) is not None else None
    message_id = (drafted.details.get(UK_MESSAGE_ID_KEY) if drafted else "") or ""
    return UkLetter(subject_line, body, context["subject_email"], channel or "email", recipient, message_id)


def uk_letter_eml(case) -> bytes:
    letter = uk_letter(case)
    message = EmailMessage()
    message["From"] = formataddr((case.subject.name, letter.sender))
    message["To"] = letter.recipient
    message["Subject"] = letter.subject_line
    message["Date"] = format_datetime(timezone.now())
    if letter.message_id:
        message["Message-ID"] = letter.message_id
    message.set_content(letter.body)
    return bytes(message)


def uk_letter_mailto(letter: UkLetter) -> str:
    return sending.mailto_link(
        Draft(recipient=letter.recipient, subject_line=letter.subject_line, body=letter.body)  # unsaved, for the link
    )


# --- Steps -------------------------------------------------------------------------------


def _record_note(case, on, text, details):
    from unlist.cases import services

    return services._record(case, CaseEvent.Kind.NOTE, on, text, details=details)


def _require_draft_state(case):
    from unlist.cases import services

    if case.state != State.COMPLAINT_DRAFT:
        raise services.IllegalStep("There is no Complaint draft.")


def on_complaint_drafted(case) -> None:
    """``services.complaint_drafters``: record where the Complaint starts, and check it can be built."""
    from unlist.cases import services

    if case.state != State.COMPLAINT_DRAFT:
        raise services.IllegalStep("A Complaint is only drafted where the lifecycle allows it.")
    events = _events(case)
    event = events[_drafted_index(events)]
    complaint = build_complaint(case)
    if uk_first_step(case):
        event.details[STAGE_KEY] = Stage.UK_ORGANIZATION
        event.details[UK_MESSAGE_ID_KEY] = sending.new_message_id(_sender(case))
        event.details["text"] += (
            " First step (UK): a short complaint to the Organization under DPA 2018 s.164A, which the Subject may skip."
        )
    else:
        event.details[STAGE_KEY] = Stage.AUTHORITY
    if complaint.authority is not None:
        event.details["text"] += f" Addressed to {complaint.choice.name}."
    else:
        event.details["text"] += " Choose the Supervisory Authority on the Complaint page."
    event.save(update_fields=["details"])


def choose_authority(case, slug: str, *, on: date | None = None) -> CaseEvent:
    """The Operator picks the Supervisory Authority (from the candidates) for this Complaint."""
    _require_draft_state(case)
    choice = select_authority(case.subject, case.organization)
    by_slug = {authority.slug: authority for authority in choice.candidates}
    if slug not in by_slug:
        raise _error("Choose one of the Supervisory Authorities listed.")
    name = authority_name(by_slug[slug])
    return _record_note(case, _today(on), f"Supervisory Authority chosen: {name}.", {AUTHORITY_KEY: slug})


def _require_stage(case, stage):
    _require_draft_state(case)
    if progress(case).stage != stage:
        raise _error("This step does not fit where the Complaint stands.")


def skip_uk_step(case, *, on: date | None = None) -> CaseEvent:
    """Skip the s.164A complaint to the Organization and go straight to the regulator draft."""
    with transaction.atomic():
        _require_stage(case, Stage.UK_ORGANIZATION)
        return _record_note(
            case,
            _today(on),
            "The Subject skipped the complaint to the Organization (DPA 2018 s.164A).",
            {STAGE_KEY: Stage.UK_SKIPPED},
        )


def uk_letter_sent(case, *, on: date | None = None) -> CaseEvent:
    """The Subject sent the s.164A complaint (handed over, never sent by Unlist)."""
    on = _today(on)
    if on > timezone.localdate():
        raise _error("The send date cannot be in the future.")
    with transaction.atomic():
        _require_stage(case, Stage.UK_ORGANIZATION)
        letter = uk_letter(case)
        return _record_note(
            case,
            on,
            "The Subject sent the complaint to the Organization (DPA 2018 s.164A). The regulator draft follows "
            f"after its answer, or from {drafting.format_date(on + timedelta(days=UK_WAIT_DAYS), 'en')}.",
            {
                STAGE_KEY: Stage.UK_SENT,
                "subject_line": letter.subject_line,
                "body": letter.body,
                "sender": letter.sender,
                "channel": letter.channel,
                "recipient": letter.recipient,
                "message_id": letter.message_id,
            },
        )


def uk_letter_answered(case, *, on: date | None = None, upload=None) -> CaseEvent:
    """The Organization answered the s.164A complaint: the regulator draft is offered now."""
    on = _today(on)
    if on > timezone.localdate():
        raise _error("The date cannot be in the future.")
    with transaction.atomic():
        _require_stage(case, Stage.UK_SENT)
        if on < progress(case).sent_on:
            raise _error("The answer cannot come before the complaint was sent.")
        event = _record_note(
            case,
            on,
            "The Organization answered the complaint under DPA 2018 s.164A.",
            {STAGE_KEY: Stage.UK_ANSWERED},
        )
        if upload is not None:
            storage.store_upload(case, upload, event=event)
        return event


def mark_lodged(case, *, on: date | None = None) -> CaseEvent:
    """The Subject lodged the Complaint: record it and keep the text that was lodged."""
    from unlist.cases import services

    on = _today(on)
    if on > timezone.localdate():
        raise _error("The date cannot be in the future.")
    with transaction.atomic():
        _require_draft_state(case)
        if not progress(case).authority_ready:
            raise _error("The Complaint to the Supervisory Authority is not offered yet (UK: the s.164A step first).")
        complaint = build_complaint(case)
        if complaint.authority is None:
            raise _error("Choose the Supervisory Authority first.")
        event = services.complaint_lodged(case, on=on)
        event.details["complaint"] = {
            "authority": complaint.authority.slug,
            "authority_name": complaint.choice.name,
            "lang": complaint.lang,
            "subject_line": complaint.subject_line,
            "body": complaint.body,
        }
        event.details["text"] += f" Lodged with {complaint.choice.name}."
        event.save(update_fields=["details"])
        return event


def lodged_complaint(case) -> CaseEvent | None:
    """The "Complaint lodged" event of the current Complaint (with the text kept), if lodged."""
    if case.state != State.COMPLAINT_LODGED:
        return None
    return case.events.filter(kind=CaseEvent.Kind.COMPLAINT_LODGED).order_by("-occurred_on", "-id").first()
