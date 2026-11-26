<!--
SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (C) 2026 The Unlist contributors
-->
# Mail templates

The texts Unlist drafts for a Subject: requests and follow-ups to an Organization, a letter of authority, and the Complaint to a Supervisory Authority. Nothing here is sent without the Operator's approval (spec section 6).

- One plain-text file per kind and language: `<lang>/<kind>.txt`. English (`en`) and German (`de`) ship with Unlist.
- First line `Subject: ...`, one blank line, then the body. The subject line is rendered on its own (a tag cannot span it and the body) and always comes out as a single line, whatever the variables contain.
- Django template language, rendered by `unlist/cases/templating.py` in its own engine with autoescaping off. `{% if %}` drops optional paragraphs.
- A line holding only template tags (`{% ... %}` or `{# ... #}`) produces no line of output, so an `{% if %}` can sit on its own line. Trailing spaces are removed and several blank lines in a row become one.
- A variable that is printed but missing from the context shows up as `[[missing: name]]` in the draft. `render(..., strict=True)` raises an error instead.

```python
from unlist.cases.templating import render

subject, body = render("removal_request", "de", {"jurisdiction": "EU", "reference": "U-7KQ3", ...})
```

## Which file is used

1. `<DATA_DIR>/mail_templates/<lang>/<kind>.txt`: a local override by the Operator, if the file exists. `DATA_DIR` is the instance's data directory (`unlist.paths.DATA_DIR`). Overrides are read on every render, so no restart is needed. An override may also add a new language.
2. The bundled `<lang>/<kind>.txt`.
3. The same two for English. A language without a template gets English (spec section 6: other request languages get English).

**UK:** the UK texts exist only in English. With `jurisdiction` `"UK"`, every language, German included, is rendered in English: the German texts cite the EU GDPR ("DSGVO"), and a German-speaking UK Organization reads English. `uk_complaint_to_organization` exists only in English and only for the UK.

Languages are given as codes such as `de` or `de-AT` (only the part before the hyphen counts).

## Templates

| Kind | Sent to | What it does |
|---|---|---|
| `access_request` | Organization | Art. 15: confirmation whether data is processed, a copy (Art. 15(3)), every Art. 15(1) item with named recipients and the source spelled out, Art. 15(2) safeguards; UK adds the s.164A complaint right (UK GDPR Art. 15(1)(ea)). Answer by email, within one month. No reasons. |
| `removal_request` | Organization | Art. 17 erasure on the grounds in `erasure_grounds`; Art. 21(2) objection to direct marketing; an Art. 21(1) objection quoting `objection_grounds` only when given; Art. 7(3) consent withdrawal; closure of any account; Art. 19 notification of recipients and a request to name them; for Brokers an Art. 17(2) request (data made public) and a minimal Suppression Record; asks which data is kept under which legal duty. |
| `reminder` | Organization | Names the original request, its date and reference code and the passed deadline; asks for an answer within 14 days. Optionally repeats the original text. No mention of a Complaint. |
| `details_reply` | Organization | Gives exactly the items in `details`, nothing more, and asks the Organization to continue within the one-month period. |
| `id_pushback` | Organization | Answers a demand for an ID copy: the request came from the address the Organization knows; Art. 12(6) (reasonable doubts only); EU: EDPB Guidelines 01/2022 paras. 73–75; UK: the ICO's right-of-access guidance. Offers other details instead. |
| `reconsider` | Organization | After a (partial) refusal of erasure: asks for the exact legal duty or Art. 17(3) exception (UK: or DPA 2018 Schedules 2–4), which data it covers and for how long, and for erasure of everything else. |
| `authority_letter` | Organization (printed, signed by the Subject or a parent) | Dated letter authorising the Operator for one Organization and one reference code only; never reused. |
| `uk_complaint_to_organization` | Organization (UK only) | Complaint to the controller under DPA 2018 s.164A: what went wrong, what would put it right, acknowledgement within 30 days. Offered before a UK Complaint and can be skipped (spec section 9). |
| `complaint` | Supervisory Authority | The Complaint: Subject's details, the Organization's identity and contacts, a dated timeline, the infringement in plain words, the remedy sought, the prior contact, the attachments. EU: Art. 77 GDPR; UK: DPA 2018 s.165. |

None of the templates gives reasons for a request, threatens anything or asks for compensation (`AGENTS.md`, Tao rule 5). The tests check this.

## Variables

All values are plain strings unless noted. Dates are strings already formatted by the caller in the template's language (for example `2 October 2026`, `2. Oktober 2026`). Lists are lists of strings, one line each, written by the caller in the template's language.

### Every template

| Variable | Type | Required | Meaning |
|---|---|---|---|
| `jurisdiction` | `"EU"` or `"UK"` | yes | Which law to cite, chosen by the Organization's Supervisory Authority. Also picks the language fallback above. |
| `reference` | str | yes | The Case's reference code, for example `U-7KQ3`. Appears in every subject line as `[Ref U-7KQ3]`, so replies can be matched (spec section 7). Follow-ups repeat the original request's code. |
| `subject_name` | str | yes | The Subject's name, used as the signature. |
| `subject_email` | str | yes | The email address the Organization knows the Subject by, from which the mail is sent. |
| `organization_name` | str | yes | The Organization's name. |

Set by the renderer (a caller may override them, but need not):

| Variable | Type | Meaning |
|---|---|---|
| `uk` | bool | `jurisdiction == "UK"`. |
| `gdpr` | str | Short name of the law in the template's language: `GDPR`, `UK GDPR` or `DSGVO`. |

### Per template

| Template | Variable | Type | Required | Meaning |
|---|---|---|---|---|
| `access_request`, `removal_request` | `identifying_details` | list of str | no | Only the identifiers this Organization is known to ask for, such as `Customer number: 12345`. Left out when empty. |
| `removal_request` | `erasure_grounds` | list of str | yes | Which Art. 17(1) grounds to cite, any of `no_longer_necessary` (a), `consent_withdrawn` (b), `objection` (c), `unlawful` (d). Per the research: Brokers typically `objection`, `unlawful`, `consent_withdrawn`; services no longer used `no_longer_necessary`, `consent_withdrawn`, `objection`. |
| `removal_request` | `objection_grounds` | str | no | The Subject's own grounds relating to their particular situation, quoted in an Art. 21(1) objection paragraph. The paragraph is left out when empty. |
| `removal_request` | `is_broker` | bool | no (false) | The Organization is a Broker: adds the Art. 17(2) paragraph and the Suppression Record request. |
| `reminder`, `uk_complaint_to_organization` | `original_kind` | `"access_request"` or `"removal_request"` | yes | Which request the follow-up is about. |
| `reminder`, `uk_complaint_to_organization` | `original_date` | str (date) | yes | When the original request was sent. |
| `reminder` | `deadline_date` | str (date) | yes | The one-month due date that has passed. |
| `reminder` | `original_body` | str | no | The original request's text, repeated below the signature. |
| `details_reply` | `details` | list of str | yes | Exactly the details the Organization asked for, with their values, for example `Customer number: 12345`. |
| `id_pushback` | `offered_details` | list of str | no | Descriptions (not values) of details the Subject can confirm instead of an ID copy, such as `the postal address you hold for me`. Without it the text offers account details or details of earlier contact. |
| `reconsider` | `refusal_date` | str (date) | no | Date of the Organization's refusal. |
| `reconsider` | `cited_exception` | str | no | What the Organization relied on, in its own words or as recorded on the Case. |
| `authority_letter` | `operator_name` | str | yes | The Operator's name. |
| `authority_letter` | `letter_date` | str (date) | yes | The date of the letter. |
| `authority_letter` | `parent_name` | str | no | For a child Subject: the person with parental responsibility who signs instead. |
| `uk_complaint_to_organization`, `complaint` | `infringement` | str | yes | What went wrong, in plain words, for example "You did not answer my access request within one month." |
| `uk_complaint_to_organization`, `complaint` | `remedy` | str | yes | What would put it right, in plain words, for example "Please answer my request in full." |
| `complaint` | `supervisory_authority_name` | str | yes | The Subject's own Supervisory Authority, which the Complaint is addressed to. |
| `complaint` | `subject_contact_details` | list of str | no | Further contact lines for the Subject, such as `Postal address: ...`, `Telephone: ...`. |
| `complaint` | `organization_contacts` | list of str | yes | The Organization's contacts and identity details, one per line, such as `Privacy contact: privacy@example.com`, `Address: ...`, `Country: ...`, `Registration number: ...`. |
| `complaint` | `timeline` | list of str | yes | Dated lines from the Case history, oldest first, for example `2 October 2026: access request sent from alex@example.org to privacy@example.com`. |
| `complaint` | `prior_contact` | str | yes | Whether and how the Organization was contacted before the Complaint (request, reminder, a UK s.164A complaint), in plain words. |
| `complaint` | `attachments` | list of str | yes | What is attached: the sent request with headers, the reminder, the replies, for a UK Complaint the s.164A complaint. |

`unlist.cases.templating.REQUIRED_VARIABLES` holds the required names per template; `strict=True` checks them.

## Writing a local override

Copy the bundled file to `<DATA_DIR>/mail_templates/<lang>/<kind>.txt` and edit it. Keep the `Subject:` line with `[Ref {{ reference }}]` in it, or replies cannot be matched by subject. Keep it gentle: no threats, no compensation demands, no reasons.

## Sources and licence

The texts are new, adapted from ideas and wording in the CC0 request templates of datarequests.org / Datenanfragen.de (`templates/en/` and `templates/de/` in https://github.com/datenanfragen/data, commit `4f6385518492d0c15dddf0ac3e487098ccdc922a`, 26 November 2026), and from the research in `docs/research/gdpr-request-requirements.md`. Unlike those templates, Unlist's texts never announce legal action or a complaint in a request.

**The template files (`en/*.txt`, `de/*.txt`) are dedicated to the public domain under CC0 1.0** (`LICENSE-CC0-1.0.txt` next to this file), like the datarequests.org templates they build on. Reasons (decided by agent, can be overturned):

- Every email Unlist sends contains the template text. Under the AGPL, each request or Complaint would arguably be a copy of a covered work that should carry licence notices. CC0 removes that question for Subjects, Organizations and Supervisory Authorities.
- Short legal letters are most useful when anyone can reuse them; keeping them CC0 lets improvements flow back to datarequests.org.
- CC0 is compatible with the AGPL, so Unlist as a whole stays AGPL-3.0-or-later (`AGENTS.md`).

This README, `LEGAL-CHECK.md` and the renderer are part of Unlist and are AGPL-3.0-or-later.

`LEGAL-CHECK.md` records which statement in each template was checked against which source.
