<!--
SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (C) 2026 The Unlist contributors
-->
# Legal check of the mail templates

Ticket #43 asks that every legal statement in the templates be checked against the research. Checked 2026-11-26 against `docs/research/gdpr-request-requirements.md` as corrected by its verification pass (the corrected text and the Verification log win over earlier wording). "§" below means a section of that file. This is a check for software design, not legal advice.

Applies to English and German unless a row says otherwise. German citations follow the usual German form ("Art. 17 Abs. 1 lit. a DSGVO", "Art. 19 DSGVO").

## Every request template

| Statement | Source in the research |
|---|---|
| No reasons are given for a request | Answer 2; §1.2 (EDPB 01/2022 para. 13; CJEU C-307/22) |
| Answer within one month of receipt, without undue delay | §2 (Art. 12(3) GDPR); UK: §2 "UK" and §7 (UK GDPR Arts. 12(3), 12A, in force 5 Feb 2026) |
| A request sent by email asks for the answer by email | §1.1 (Art. 12(3), last sentence; Recital 59) |
| Answer is free of charge (Art. 12(5)) | §1.1 (Art. 12(5); C-307/22); UK wording unchanged: §5 "UK", §7 |
| Sent from the address the Organization knows the Subject by | Implications, "Identity" (cheapest authentication) |
| Only the identifiers passed in | Implications, "Identity"; §3 (data minimisation, para. 68) |
| No threats, no compensation demands | Implications, "Repeat requests" (C-526/24: a pattern of requests followed by compensation claims may count as abusive intention); `AGENTS.md` Tao rule 5 |
| UK cites UK GDPR and DPA 2018; EU cites the GDPR | Implications, "Sending requests" (same substance, switch citations and regulator name) |

## `access_request`

| Statement | Source |
|---|---|
| Confirmation whether or not data is processed; "we hold nothing" is an answer | §1.2 (Art. 15(1) first words; reading labelled in the research) |
| Copy of all data, Art. 15(3) | §1.2 (C-487/21) |
| Art. 15(1)(a)–(h) items, worded after the Art. 15(1) text quoted in §1.2 | §1.2 |
| Named recipients, not only categories; CJEU C-154/21, 12 January 2023 (EU text only) | §1.2; Verification log "Confirmed" (C-154/21) |
| Source of the data, Art. 15(1)(g) | §1.2; Answer 2 |
| Art. 15(2) safeguards for third-country transfers | §1.2 |
| Scope is all data unless narrowed | §1.2 (EDPB 01/2022 para. 35) |
| UK: right to complain to the controller under DPA 2018 s.164A (UK GDPR Art. 15(1)(ea)) | §1.2; Verification log row "UK Art. 15(1) list" (DUAA Sch. 10 para. 5) |
| UK: complaint to "the Information Commission" | §7 (SI 2026/1015; DPA 2018 ss.165–166 now read "Commission") |

## `removal_request`

| Statement | Source |
|---|---|
| Art. 17(1)(a)–(d) grounds, worded after the text in §1.3 | §1.3 (all six grounds checked against the GDPR text) |
| Which grounds fit Brokers and services no longer used (README guidance for `erasure_grounds`) | §1.3 table (labelled a reading in the research) |
| Art. 21(2) objection to direct marketing incl. related profiling, no reasons needed | §1.5 (Art. 21(2)–(3); ICO: absolute right) |
| Art. 21(1) objection only with grounds "relating to his or her particular situation" | §1.5; Verification log row "Art. 21(1)" |
| Withdrawal of consent, Art. 7(3) | §1.5 |
| Account closure | §1.3 table (otherwise contract necessity remains a basis) |
| Art. 19: tell recipients of the erasure; tell the Subject who they are on request | §1.5 (Art. 19 quoted); Implications, "Sending requests" |
| Brokers: Art. 17(2) when the data was made public | §1.5 (Art. 17(2) quoted; *Proximus* wording corrected — not relied on) |
| Brokers: ask for a minimal Suppression Record | §1.5 (ICO object: do not delete from a suppression list); Implications, "Sending requests" — phrased as a request, no legal duty claimed |
| Ask which data is kept under which legal provision, erase the rest | §1.4 (Art. 17(3) "to the extent that"; CEF 2025: exceptions applied without case-by-case assessment) |

## `reminder`

| Statement | Source |
|---|---|
| One month has passed since the request | §2 |
| 14 days to answer | Spec section 8 ("A reminder gives 14 days"); a request, no legal period claimed |
| No Complaint mentioned | `AGENTS.md` Tao rule 5 (gentle first) |

## `details_reply`

| Statement | Source |
|---|---|
| Gives only what was asked | §3 (para. 68: no more than needed); spec section 7 |
| "Continue ... within the one-month period" | §2. Deliberately neutral: the EU pause is EDPB interpretation (para. 159) and the UK restarts the month (Art. 12A); the text claims neither |

## `id_pushback`

| Statement | Source |
|---|---|
| Art. 12(6): more information only on reasonable doubts, only what is necessary | §3 (Art. 12(6) quoted) |
| EU, quoted: "it is disproportionate to require a copy of an identity document in the event where the data subject making a request is already authenticated by the controller" — para. 73 | §3; Verification log "Confirmed" (para. 73) |
| EU, paraphrased: ID copy is a security risk and inappropriate unless necessary, suitable and in line with national law — para. 74; generally not an appropriate way of authentication — para. 75 | §3; Verification log "Confirmed" (paras. 74, 75) |
| Cited as "Guidelines 01/2022 on data subject rights - Right of access, version 2.1" | "Sources used" (v2.1, paragraph numbers checked against v2.1) |
| UK, quoted: "Only request formal identification documents if necessary. You can use verification measures that you already have in place (eg an existing username and password)" | §3 "UK" (ICO resp, "Can we ask for ID?") |
| No EDPB citation in the UK text | Reading: the EDPB guidelines are EU guidance; the UK text uses the UK regulator's guidance |

## `reconsider`

| Statement | Source |
|---|---|
| Art. 17(3): data kept only "to the extent that processing is necessary" for a listed purpose | §1.4 (Art. 17(3) quoted) |
| Ask for the exact legal duty, the data it covers and for how long | §1.4 and Implications, "Sending requests" (record which exception and which legal duty) |
| UK: exemptions in DPA 2018 Schedules 2–4 | §7 (DPA 2018 s.15 quoted) |

## `authority_letter`

| Statement | Source |
|---|---|
| Signed, dated, specific to one Organization, not reused | §4 (ICO: written authority signed by the person; e-signed letters only if recent); Implications, "Acting for Subjects" |
| Parent signs for a child | §4 "Children" (para. 84; ICO: holder of parental responsibility) |
| Answers go to the Subject's address | §4 (ICO: respond to the authorised third party in most cases); Implications, "Acting for Subjects" (answers come back to the Subject's mailbox) |

## `uk_complaint_to_organization`

| Statement | Source |
|---|---|
| Complaint to the controller under DPA 2018 s.164A | §6 "UK", Step 1 |
| Acknowledgement within 30 days of receipt; outcome without undue delay; s.164A(3) and (4) | §6 "UK" (s.164A quoted; SI 2026/82 regs. 3(a), 7) |
| Not a precondition; no regulator mentioned in the text | §6 "UK" ("Is step 1 legally mandatory? No."); Tao rule 5 |

## `complaint`

| Statement | Source |
|---|---|
| EU: Art. 77 GDPR, lodged with the Subject's own authority | §6 "EU" (Art. 77(1); Arts. 56(6), 60(7)–(8)) |
| UK: DPA 2018 s.165 (UK GDPR Art. 77 omitted) | §6 "UK", Step 2 |
| The Subject lodges it personally | §6 "EU" (right belongs to the data subject; the Operator is not an Art. 80 body); Implications, "Complaints" |
| Contents: Subject's details, Organization's identity and contacts, chronological facts, infringement, remedy, prior contact, attachments | §6 "EU" (EDPB complaint form); Reg. 2025/2518 Art. 4 (name and contact, identification of the controller, description of the infringement); Implications, "Complaints" |

## Statements not settled by the research

These are in the templates but rest on the author's reading or on sources the research did not check:

1. **German EDPB citation.** The German `id_pushback` paraphrases paras. 73–75 in German without quotation marks. The official German translation of the Guidelines was not read; its title ("Leitlinien 01/2022 zu den Rechten der betroffenen Person – Auskunftsrecht") is translated here, and its paragraph numbering is assumed to match the English v2.1.
2. **"Already authenticated".** Para. 73 speaks of a data subject "already authenticated by the controller". That writing from the known email address amounts to this is an argument the text makes by placing the two side by side, not something the EDPB says.
3. **UK GDPR Art. 15(1)(f) wording.** The research confirms the regulator is now the Information Commission and that DPA 2018 ss.165–166 say "Commission", but not the current wording of UK GDPR Art. 15(1)(f).
4. **UK changes avoided rather than checked.** The Art. 21(1) paragraph does not cite Art. 6(1)(e)/(f), and the Art. 15(2) item does not cite Art. 46, because DUAA may have changed the UK numbering (recognised legitimate interests; the transfers chapter). Neither was checked.
5. **C-154/21 left out of the UK text** because post-2020 CJEU judgments do not bind UK courts. The research does not discuss this.
6. **Art. 17(1)(d) "to the extent that the processing has no legal basis".** A cautious reading of ground (d), so the Subject does not assert unlawfulness they cannot know.
7. **Suppression Record.** No EU source states a duty to keep one; the request relies on the ICO's suppression-list guidance (UK, direct marketing) and the design rationale in §1.5.
8. **Authority letter form.** National rules on the form of an authority are not covered by the research (§4, "Could not verify"); the letter may not meet every national requirement.
