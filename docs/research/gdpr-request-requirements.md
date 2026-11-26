# What a GDPR Access Request or Removal Request legally requires

Research for issue #5. Researched 2026-11-26. Covers the EU GDPR (Regulation (EU) 2016/679) and the UK GDPR / Data Protection Act 2018 as amended by the Data (Use and Access) Act 2025.

**This is a factual summary for software design, not legal advice.**

**Verification status — read this first.** The research session could not open any primary source directly: `eur-lex.europa.eu`, `edpb.europa.eu`, `ico.org.uk`, `legislation.gov.uk` and `curia.europa.eu` were all blocked by the session's network policy. Every claim below was checked one of two ways:

- **Unmarked claims** were checked against text excerpts of the cited primary source returned by a web search restricted to that source's own domain. That confirms the wording exists at the URL; it is not a read of the whole document, so context around the excerpt was not seen.
- Claims marked **(unverified against source)** are from memory of the source and were not confirmed even by excerpt. Paragraph numbers carrying that mark are the most likely thing to be wrong.

Before any wording from this file goes into a request template, re-check it against the linked source.

## Answer

1. **No form is required, in the EU or the UK.** A plain email is a valid Access Request or Removal Request. An Organization may offer a form or portal but cannot make it compulsory. The request must reach an *official* contact point (privacy/DPO address or general official contact): an Organization need not act on mail sent to a random or obviously wrong address.
2. **No reasons are needed** for an Access Request, and it covers all the Subject's data unless narrowed. It should ask for confirmation of processing, a copy (Art. 15(3)), and the Art. 15(1)(a)–(h) items — for a Broker, above all the *source* (15(1)(g)) and the *named recipients* (15(1)(c)).
3. **A Removal Request should stack three things**: erasure (Art. 17(1)), objection (Art. 21, where the direct-marketing objection in 21(2)–(3) is absolute), and withdrawal of consent (Art. 7(3)). Expect refusals based on Art. 17(3)(b) (legal retention duty — the most-used exception) and 17(3)(e) (legal claims).
4. **Deadline: one month from receipt**, extendable by two further months only if the Organization says so, with reasons, inside the first month. Count to the same day-number in the next month (last day of the month if there is none; next working day if it lands on a weekend or public holiday).
5. **Identity checks move the deadline.** EU: the clock may be suspended while the Organization waits for identity information, if it asked without undue delay. UK: by statute the month only starts when the requested identity information arrives.
6. **An Organization may ask for more identity information only on reasonable doubt, and only what is proportionate.** The EDPB treats demanding a copy of an ID document as generally inappropriate, and disproportionate where the person is already authenticated.
7. **Someone else can act for a Subject, with authority.** The Organization may verify both identity and authorisation; the representative carries the burden of proving authority (UK: e.g. signed written authority or a power of attorney). A child's rights belong to the child; a holder of parental responsibility acts for a child who is not mature enough. Age thresholds vary by state and are *consent* ages, not capacity-to-request ages.
8. **No fixed interval for repeating an Access Request exists** in either regime. It depends on how often the data changes; Organizations that refuse bear the burden of proof. A first request can be refused only if the Organization proves abusive intent (CJEU C-526/24, 2026).
9. **Complaints are free and are lodged by the Subject** with the Supervisory Authority of their residence, workplace or the place of infringement. For cross-border cases the Subject's own authority stays their contact point while a lead authority investigates. Organizations with no EEA establishment get no one-stop-shop.
10. **UK now has a statutory complain-to-the-Organization-first step** (DPA 2018 s.164A, in force 19 June 2026: acknowledgement within 30 days). The regulator recommends using it and waiting 30 days before complaining to it, and complaining within three months of last contact.
11. **UK specifics in force today**: "reasonable and proportionate search" limit on access (deemed in force from 1 January 2024); statutory time-limit rules incl. stop-the-clock for clarification (commenced in 2026); the Information Commissioner was replaced by the **Information Commission** on 30 September 2026.
12. **Two things are moving**: the EU "Digital Omnibus" proposal to loosen Art. 12(5) for "abusive" access requests (not adopted as far as could be confirmed), and Regulation (EU) 2025/2518, which fixes what a cross-border complaint must contain from 2 April 2027.

## Sources used

| Short name | Document | URL |
|---|---|---|
| GDPR | Regulation (EU) 2016/679 | https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng |
| EDPB 01/2022 | EDPB Guidelines 01/2022 on data subject rights – Right of access, v2.1, adopted 28 March 2023 | https://www.edpb.europa.eu/system/files/2023-04/edpb_guidelines_202201_data_subject_rights_access_v2_en.pdf |
| EDPB CEF 2024 | EDPB Coordinated Enforcement Action 2024 report, right of access (Jan 2025) | https://www.edpb.europa.eu/system/files/2025-01/edpb_cef-report-2024_20250116_rightofaccess_en.pdf |
| EDPB CEF 2025 | EDPB Coordinated Enforcement Action 2025 report, right to erasure (adopted 18 Feb 2026) | https://www.edpb.europa.eu/system/files/2026-02/edpb_cef-report_2025_right-to-erasure_en.pdf |
| EDPB 8/2022 | EDPB Guidelines 8/2022 on identifying a lead supervisory authority | https://www.edpb.europa.eu/system/files/documents/2023-04/edpb_guidelines_202208_identifying_lsa_targeted_update_v2_en.pdf |
| EDPB complaint form | EDPB Template Complaint Form, adopted 20 June 2023 | https://www.edpb.europa.eu/system/files/2023-06/edpb_20230620_templatecomplaintform_0.pdf |
| Reg. 1182/71 | Regulation (EEC, Euratom) No 1182/71 (rules for periods, dates and time limits) | https://eur-lex.europa.eu/eli/reg/1971/1182/oj/eng |
| Reg. 2025/2518 | Regulation (EU) 2025/2518 (procedural rules for GDPR enforcement) | https://eur-lex.europa.eu/eli/reg/2025/2518/oj/eng |
| ICO access | ICO right of access detailed guidance (current PDF v1.0.87, 8 Dec 2025; web pages updated since) | https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/right-of-access/ |
| ICO erasure | ICO right to erasure guidance | https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/right-to-erasure/ |
| ICO object | ICO right to object guidance (page dated 2 Nov 2026) | https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/right-to-object |
| DUAA | Data (Use and Access) Act 2025 (c. 18) | https://www.legislation.gov.uk/ukpga/2025/18 |
| SI 2026/82 | DUAA Commencement No. 6 and Transitional and Saving Provisions Regulations 2026 | https://www.legislation.gov.uk/uksi/2026/82/made |
| SI 2026/1015 | DUAA Commencement No. 9 Regulations 2026 | https://www.legislation.gov.uk/uksi/2026/1015/pdfs/uksi_20261015_en.pdf |

Paragraph numbers for EDPB 01/2022 refer to the adopted v2.1. The January 2022 public-consultation draft numbers paragraphs differently (usually one lower), and many secondary write-ups cite the draft.

## 1. What a valid request must contain

### 1.1 Form

- **The GDPR sets no form requirement.** "The GDPR does not impose any requirements on data subjects regarding the form of the request for access to the personal data" — EDPB 01/2022 para. 52. The EDPB CEF 2024 report repeats that the GDPR imposes no formal prerequisites and lists "formal requirements" as a barrier Organizations wrongly put up.
- **The Organization's own form or portal is optional.** The controller "should provide appropriate and user-friendly communication channels", but "the data subject is not required to use these specific channels and may instead send the request to an official contact point of the controller" — EDPB 01/2022 paras. 53–55 (text confirmed; exact paragraph within 53–56 not confirmed). A self-service tool may be encouraged but not required, and requests arriving another way must still be handled — EDPB 01/2022 paras. 134, 137–138.
- **The address matters.** "The controller is not obliged to act on requests that are sent to completely random, or apparently incorrect, addresses" — EDPB 01/2022 paras. 53–56. The clock starts when the request "reaches the controller through one of its official channels" — para. 159.
- **UK: same.** "There are no formal requirements for a valid request. A person can make a SAR verbally or in writing, including by social media"; it need not say "subject access request" or cite Article 15; a standard form may be offered but must not be compulsory — ICO access, "How do we recognise a subject access request (SAR)?" https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/right-of-access/how-do-we-recognise-a-subject-access-request-sar/
- **Erasure has no form requirement either.** UK: "individuals can make a request for erasure verbally or in writing" — ICO erasure. EU: Art. 12(2) GDPR obliges the controller to "facilitate the exercise of data subject rights under Articles 15 to 22" and Art. 17 prescribes no form; there is no general EDPB guideline on Art. 17 form (unverified against source).
- **Electronic requests get electronic answers.** Recital 59 GDPR: controllers should provide means for requests to be made electronically. Art. 12(3) GDPR: where the request is made by electronic means the information is to be provided electronically where possible, unless the data subject asks otherwise (unverified against source).
- **Free of charge.** Art. 12(5) GDPR; a first copy is free even if no reason is given — CJEU C-307/22 *FT v DW* (26 Oct 2023) https://eur-lex.europa.eu/legal-content/en/ALL/?uri=CELEX%3A62022CJ0307

### 1.2 What an Access Request should ask for

- **No reasons required.** Controllers "should not assess 'why' the data subject is requesting access, but only 'what' the data subject is requesting" — EDPB 01/2022 (para. 13; number unverified). The CJEU held that neither Art. 12(5) nor Art. 15(1), (3) makes the right conditional on stating reasons, and it applies even where the purpose is unrelated to those in Recital 63 — C-307/22.
- **Default scope is everything.** Unless stated otherwise the request "should be understood as referring to all personal data concerning the data subject"; a controller processing a large quantity may ask the person to specify, but that "shall not aim at a limitation of the reply" — EDPB 01/2022 (para. 35; number unverified).
- **Art. 15(1) GDPR content** (list unverified against source except where a case is cited): confirmation whether data is processed; access to the data; (a) purposes; (b) categories of data; (c) recipients; (d) retention period or criteria; (e) existence of the rights to rectification, erasure, restriction and objection; (f) right to complain to a Supervisory Authority; (g) **source** of the data where not collected from the person; (h) existence of automated decision-making including profiling, with meaningful information on the logic. Art. 15(2): safeguards for third-country transfers.
- **Recipients by name.** Art. 15(1)(c) obliges the controller "to provide the actual identity of those recipients" unless identification is impossible or the request is manifestly unfounded or excessive — CJEU C-154/21 *RW v Österreichische Post* (12 Jan 2023) https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex%3A62021CJ0154
- **Copy means a real copy.** Art. 15(3) requires "a faithful and intelligible reproduction of all the personal data undergoing processing"; a general description or list of categories is not enough — CJEU C-487/21 *F.F. v Österreichische Datenschutzbehörde* (judgment date 4 May 2023 unverified) https://eur-lex.europa.eu/legal-content/en/TXT/?uri=CELEX%3A62021CJ0487
- **A negative answer is still an answer.** Art. 15(1) starts with the right to "confirmation as to whether or not" data is processed, so "we hold nothing" is a response the Organization owes (unverified against source).
- **UK limit:** the right extends only to what the controller can provide after "a reasonable and proportionate search" — UK GDPR Art. 15(1A), inserted by DUAA s.78 https://www.legislation.gov.uk/ukpga/2025/18/section/78

### 1.3 Art. 17(1) grounds for a Removal Request

Art. 17(1) GDPR grounds: (a) data no longer necessary for the purposes collected; (b) consent withdrawn and no other legal ground; (c) objection under Art. 21(1) with no overriding legitimate grounds, or objection under Art. 21(2); (d) data unlawfully processed; (e) erasure required by a legal obligation; (f) data collected from a child for an information society service under Art. 8(1). Grounds (a)–(d) were confirmed by excerpt (ICO erasure; CJEU C-26/22 and C-64/22 *SCHUFA* https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A62022CJ0026); (e) and (f) are unverified against source.

Which grounds fit which Organization is a reading of the text, not something a source states:

| Situation | Grounds that fit | Why |
|---|---|---|
| **Broker** (never had a relationship with the Subject; typically relies on legitimate interests) | 17(1)(c) via Art. 21(2) if data is used for direct marketing — absolute; 17(1)(c) via Art. 21(1) otherwise — the Broker must show overriding legitimate grounds; 17(1)(d) if there was never a valid legal basis; 17(1)(b) if the Broker claims consent | Objection is the natural route against legitimate-interest processing |
| **Service the Subject no longer uses** | 17(1)(a) once the account is closed and the purpose is spent; 17(1)(b) for consent-based processing (newsletters, tracking); 17(1)(c) via Art. 21(2) for marketing | The request should also close the account, otherwise contract necessity remains a basis |

### 1.4 Art. 17(3) exceptions Organizations invoke

- Art. 17(3) GDPR: erasure does not apply where processing is necessary (a) for freedom of expression and information; (b) to comply with a legal obligation or perform a public-interest task; (c) for public health; (d) for archiving, research or statistics; (e) "for the establishment, exercise or defence of legal claims" — text of (e) confirmed via CJEU excerpts; (a)–(d) confirmed in summary via ICO erasure.
- **Most used in practice: 17(3)(b).** In the EDPB's 2025 coordinated action (32 authorities, 764 controllers) the exception applied most often was compliance with a legal obligation under Union or Member State law; legal claims (17(3)(e)) appears to be next (ranking beyond first place not confirmed) — EDPB CEF 2025. Authorities that investigated found the refusals justified overall.
- The same report lists recurring failures: weak internal erasure procedures, anonymising instead of deleting, retention periods and backups.
- Organizations may also refuse under Art. 12(5) (manifestly unfounded or excessive) — see section 5.

### 1.5 How objection (Art. 21) and consent withdrawal (Art. 7(3)) relate

- **Direct marketing objection is absolute.** "Where personal data are processed for direct marketing purposes, the data subject shall have the right to object at any time ... which includes profiling to the extent that it is related to such direct marketing" (Art. 21(2)); then "the personal data shall no longer be processed for such purposes" (Art. 21(3)) — GDPR https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng. ICO object: "This is an absolute right and there are no exemptions or grounds for you to refuse."
- **General objection is conditional.** Art. 21(1) applies to processing based on Art. 6(1)(e) or (f); the controller must stop unless it demonstrates compelling legitimate grounds overriding the person's interests, or needs the data for legal claims (unverified against source).
- **Objection feeds erasure.** A successful objection is itself an erasure ground: Art. 17(1)(c).
- **Objection alone is not erasure.** After a marketing objection an Organization normally *suppresses* rather than deletes: it keeps the minimum needed to remember not to market to the person. "You should not delete a person's information from a suppression list" — ICO object. This matters for Brokers that re-acquire data: a suppression record is what keeps a Subject removed.
- **Consent withdrawal.** Consent can be withdrawn at any time and "it shall be as easy to withdraw as to give consent" (Art. 7(3) GDPR). Withdrawal triggers erasure ground 17(1)(b) where there is "no other legal ground". Withdrawal does not affect the lawfulness of earlier processing (unverified against source).
- **Passing it on.** A controller told of a withdrawal must communicate it to others who received the data relying on the same consent — CJEU C-129/21 *Proximus* (27 Oct 2022) https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A62021CJ0129. Where data was disclosed, the controller "must contact each recipient and inform them of the erasure, unless this proves impossible or involves disproportionate effort" — ICO erasure, reflecting Art. 19 GDPR (Art. 19 and 17(2) text unverified against source).

## 2. Deadlines

- **One month.** The controller must inform the person of the action taken on the request "without undue delay and in any event within one month of receipt of the request" — Art. 12(3) GDPR as quoted in EDPB 01/2022. Recital 59 says the same. This applies to requests under Arts. 15–22, so to both Access and Removal Requests.
- **Extension.** The period may be extended by two further months where necessary, taking into account the complexity and number of requests; the controller must tell the person of the extension and the reasons within the first month — Art. 12(3) GDPR (the notice-within-one-month detail is unverified against the EU text; the UK equivalent, UK GDPR Art. 12A, is confirmed: notice "before the end of the period of one month beginning with the relevant time" and it must "state the reasons for the delay").
- **Refusal also has a deadline.** If the controller does not act, it must say why within one month and mention the right to complain and to a judicial remedy — Art. 12(4) GDPR (unverified against source).
- **Clock start (EU).** "The time limit starts when the controller has received an Art. 15 request, meaning when the request reaches the controller through one of its official channels. It is not necessary that the controller is in fact aware of the request" — EDPB 01/2022 para. 159.
- **Counting the month (EU).** "The time period needs to be calculated in accordance with Regulation No 1182/71." EDPB example: request received 5 March, deadline 5 April inclusive; if the last day is a weekend or public holiday the controller has until the next working day — EDPB 01/2022 (around paras. 160–162; numbers unverified; the example text was seen in the consultation draft). Under Reg. 1182/71 Art. 3(2)(c) a period in months ends on the day with the same date as the starting day, or on the last day of the month if that date does not exist; Art. 3(4) rolls a period ending on a Saturday, Sunday or public holiday to the next working day; Art. 3(3) counts weekends and holidays inside the period.
- **Identity verification (EU).** Where the controller needs to check identity, "there may be a suspension in time until the controller has obtained the information needed from the data subject, provided the controller has asked for additional information without undue delay" — EDPB 01/2022 para. 159. The GDPR text itself says nothing about pausing; this is EDPB interpretation.
- **Speed.** The month is a maximum: the controller "should react as soon as possible" — EDPB 01/2022.

**UK**

- **Statutory rule.** "The applicable time period" is "the period of one month beginning with the relevant time". The relevant time is the latest of: when the controller receives the request; when it receives "the information (if any) requested in connection with a request under Article 12(6)" (identity); and when any Art. 12(5) fee is paid — UK GDPR Art. 12A, inserted by DUAA s.76 https://www.legislation.gov.uk/ukpga/2025/18/section/76. So in the UK the month **starts** on receipt of requested identity information; it is a fresh start, not a pause.
- **Stop the clock for clarification.** Where the controller reasonably needs more information to identify the data or processing an Art. 15 request relates to, the period from asking to receiving "does not count" — DUAA s.76. The controller must be able to show clarification is reasonably required — ICO DUAA summary https://ico.org.uk/about-the-ico/what-we-do/legislation-we-cover/data-use-and-access-act-2025/the-data-use-and-access-act-2025-duaa-summary-of-the-changes/data-protection/. This pause is for access requests only.
- **Counting.** From the day of receipt, "whether a working day or not", "until the corresponding calendar date in the next month" — ICO access, "What should we consider when responding to a request?" https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/right-of-access/what-should-we-consider-when-responding-to-a-request/. No corresponding date means the last day of that month, and a weekend or bank holiday rolls to the next working day (unverified against source).
- **Inconsistency in ICO material.** ICO pages disagree on whether a stopped clock resumes on the day clarification is received or the day after; the same worked example (received 14 May, clarification asked 15 May and received 18 May) yields 17 June in one version and 18 June in another. Not resolved here.

## 3. Identity verification

- **Rule.** "Where the controller has reasonable doubts concerning the identity of the natural person making the request referred to in Articles 15 to 21, the controller may request the provision of additional information necessary to confirm the identity of the data subject" — Art. 12(6) GDPR, "without prejudice to Article 11".
- **Recital 64.** "The controller should use all reasonable measures to verify the identity of a data subject who requests access, in particular in the context of online services and online identifiers." It adds that a controller should not retain data solely to be able to react to potential requests (second sentence unverified against source).
- **Art. 11.** A controller that cannot identify the person need not acquire extra data just to comply; then Arts. 15–20 "shall not apply except where the data subject ... provides additional information enabling his or her identification" (Art. 11(2)). Under Art. 12(2) the controller may refuse only if it *demonstrates* it cannot identify the person (unverified against source).
- **EDPB 01/2022** on how much may be asked:
  - The controller is not obliged to collect extra information merely to identify someone — para. 61.
  - Additional information may be requested only on reasonable doubt — para. 66; the controller must assess case by case what would confirm identity and ask only where proportionate — para. 67; it must say what kind of information it needs, and that should not exceed what was originally needed to authenticate the person — para. 68.
  - The authentication method "should be relevant, appropriate, proportionate and respect the data minimisation principle" — para. 70.
  - "It is disproportionate to require a copy of an identity document in the event where the data subject making a request is already authenticated by the controller" — para. 73.
  - Using a copy of an identity document "creates a risk for the security of personal data ... and as such it should be considered inappropriate, unless it is necessary, suitable, and in line with national law" — para. 74. ID copies should "generally not be considered an appropriate way of authentication" — para. 75.
  - Where an ID copy is legitimately required, the person may black out data not needed, and the controller should record that the ID was checked rather than keep the copy (paras. 78–79; unverified against source).
- **Enforcement practice.** Asking for ID indiscriminately on every access request may itself be excessive processing; controllers must be able to demonstrate their need for further identification documents — EDPB CEF 2024.
- **UK.** Be reasonable and proportionate; "only request formal identification documents if necessary"; do not ask for more where identity is obvious; existing account credentials or questions only the person could answer are acceptable alternatives; controllers need not keep copies of ID — ICO access, "What should we consider when responding to a request?"

## 4. Acting for someone else

- **Allowed.** "Although the right of access is generally exercised by the data subjects as it pertains to them, it is possible for a third party to make a request on behalf of the data subject. This may apply to, among others, acting through a proxy or legal guardians on behalf of minors, as well as acting through other entities via online portals" — EDPB 01/2022 para. 80. Identity and authorisation may be verified where suitable and proportionate. What counts as valid legal representation is a matter of national law (unverified against source).
- **Portals.** A controller first confirms the third party is legitimately acting for the person (para. 89). It must handle the request promptly but "is not obliged" to deliver the data through the portal, and may disclose directly to the data subject instead, for example where it finds the portal's security insufficient — EDPB 01/2022 paras. 88–90 (English wording of v2.1 para. 90 not confirmed; substance confirmed in other language versions and the draft).
- **UK authority.** The Organization must be satisfied the third party is entitled to act; "the third party is responsible for providing you with evidence of this, for example by providing a written authority, signed by the person the information is about", or a power of attorney — ICO access, "How do we recognise a SAR?". A request by a representative is treated as if the person made it, so the representative's other requests for other people cannot be counted against it; a request made as part of a bulk request has the same status as any other.
- **UK portals.** If the request cannot be viewed without paying a fee or signing up to a service, the Organization has not received it and need not respond. Agreement to a portal's terms and conditions "is unlikely to be evidence of appropriate authority". The Organization should send the answer directly to the person where it can — ICO access.
- **UK, AI-assisted requests** (ICO note, November 2026): an AI-assisted request must be treated like any other and is not invalid for containing inaccuracies; but if a controller suspects an authority letter was AI-generated it "should contact the person the request is about directly", and controllers may ask people to review an AI-assisted request before sending — https://ico.org.uk/about-the-ico/media-centre/news-and-blogs/2026/11/subject-access-requests-generated-by-artificial-intelligence/. Fuller guidance is planned for winter 2026.
- **Adults lacking capacity (UK).** Neither the UK GDPR nor the mental-capacity statutes contain a specific provision letting a third party make a request for them; an attorney with authority over property and affairs can reasonably be assumed to have authority — ICO access.

**Children**

- "Children are data subjects in their own right and, as such, the right of access belongs to the child. Depending on the maturity and capacity of the child, the child may need a third party to act on its behalf e.g. the holder of parental responsibility" — EDPB 01/2022 para. 84. The child's best interests lead (paras. 85–86). Parents' data-protection standing is separate from other national-law rights to information about a child (para. 87).
- **UK.** The Organization decides whether the child is mature enough to understand their rights; if so it should respond to the child. If not, a holder of parental responsibility may usually exercise the right unless that is against the child's best interests. Evidence of parental responsibility can be a birth or adoption certificate. In Scotland a person aged 12 or over is presumed mature enough unless shown otherwise; there is no such presumption elsewhere in the UK — ICO access (children section updated April 2026). The Scottish presumption is in DPA 2018 s.208 (section number unverified against source).
- **Age thresholds are about consent, not requests.** Art. 8 GDPR sets 16 as the age at which a child can consent to an information society service, and lets member states lower it, not below 13. It does not set an age for exercising Art. 15 or 17; that turns on maturity and national law. Reported thresholds — 16: DE, HR, HU, IE, LU, NL, PL, RO, SK; 15: CZ, EL, FR; 14: AT, BG, CY, ES, IT, LT (Commission-commissioned study, June 2020, https://commission.europa.eu/document/download/837d04b9-7e71-4534-8eaa-599902ea28dc_en?filename=GDPR+Study+Report-Tipik+-June+2020.pdf); 13: BE, DK, EE, FI, LV, MT, PT, SE (unverified against source). A late-2025 Commission report counts 7/6/5/9 states at 13/14/15/16, so at least one state has changed since 2020. UK: 13 (DPA 2018 s.9; unverified against source). Treat any hard-coded table as stale.

## 5. Repeat requests

- **Rule.** Requests are free, but where they are "manifestly unfounded or excessive, in particular because of their repetitive character", the controller may charge a reasonable fee or refuse; the controller bears the burden of demonstrating this — Art. 12(5) GDPR (confirmed in substance via C-307/22 and EDPB excerpts). Recital 63 speaks of exercising the right "easily and at reasonable intervals" (unverified against source).
- **No fixed interval (EU).** "It is not possible to generally determine any specific interval in which the submission of a further access request could be deemed excessive ... An overall consideration of the circumstances of the individual case is rather required" — EDPB 01/2022 paras. 183–185.
- **What drives it.** "The more often changes occur in the database of the controller, the more often data subjects may be permitted to request access" — para. 184; a social network changes faster than a land register. Factors (para. 185): how often the data is altered, the nature of the data, the purposes of processing, whether later requests concern the same information. Example: asking a carpenter every two months may be excessive because little changes.
- **A free copy is owed even if nothing changed** — EDPB 01/2022 (same section). The consultation draft said requests every three months to a frequently changing data set are in principle not excessive and that a one-year gap could never be excessive; those two sentences could **not** be confirmed in the adopted v2.1.
- **Fee before refusal.** For excessive requests it is "often more appropriate to charge a fee" than to refuse — EDPB 01/2022.
- **First requests and abuse.** A *first* request "may be regarded as 'excessive'" where the controller establishes "an abusive intention", for example a request made in order to claim compensation; the exception is read restrictively and the burden is on the controller — CJEU C-526/24 *Brillen Rottler* (19 March 2026) https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A62024CJ0526
- **Numbers alone never suffice.** Requests "cannot be classified as 'excessive' solely on account of their number during a specific period"; abusive intention must be shown — CJEU C-416/23 (9 Jan 2025), decided on complaints to a Supervisory Authority under Art. 57(4) https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:62023CJ0416
- **UK.** "A high threshold"; a request "should not be presumed manifestly unfounded or excessive simply because the person has submitted such a request before". Relevant: whether it largely repeats earlier requests, whether "a reasonable interval" has elapsed, and "the nature of the information and how often it changes". Repeating is justified if the Organization mishandled the earlier request. Using AI to draft does not make a request unfounded — ICO access, "When can we consider a SAR to be manifestly unfounded or excessive?" https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/right-of-access/when-can-we-consider-a-sar-to-be-manifestly-unfounded-or-excessive/
- **Pending.** The Commission's Digital Omnibus proposal (procedure 2025/0360(COD)) would let controllers refuse or charge for access requests seen as abusive, including those pursuing aims unrelated to data protection. EDPB–EDPS Joint Opinion 2/2026 opposes tying abuse to non-data-protection purposes. Council documents to 31 July 2026 show the Art. 12(5) wording still under discussion; no adoption was found. Current status not confirmed — https://www.edpb.europa.eu/system/files/2026-02/edpb_edps_jointopinion_202602_digitalomnibus_en.pdf

## 6. Complaints

**EU**

- **Right and venue.** "Every data subject shall have the right to lodge a complaint with a supervisory authority, in particular in the Member State of his or her habitual residence, place of work or place of the alleged infringement" — Art. 77(1) GDPR https://eur-lex.europa.eu/eli/reg/2016/679/art_77/oj. The authority must inform the complainant of progress and outcome (Art. 77(2)).
- **Who lodges.** The right belongs to the data subject. A not-for-profit body can be mandated under Art. 80(1); other representation depends on national procedural law (unverified against source). The Operator is not an Art. 80 body.
- **Free.** Handling is free for the data subject under Art. 57(3), which the CJEU calls the "free-of-charge principle"; Art. 57(4) lets an authority charge or refuse for manifestly unfounded or excessive requests — C-416/23.
- **If the authority stalls.** A judicial remedy is available where the authority does not handle the complaint or does not inform the person within three months — Art. 78(2) GDPR.
- **One-stop-shop.** For cross-border processing the authority of the controller's main establishment leads (Arts. 56, 60 GDPR; article text unverified against source). The lead authority is the contact for the controller, while the authority where the complaint was lodged is the contact for the individual — EDPB one-stop-shop leaflet https://www.edpb.europa.eu/system/files/2021-06/2020_06_22_one-stop-shop_leaflet_en.pdf. The Subject therefore complains at home in their own language.
- **No one-stop-shop for non-EEA Organizations.** "Controllers without any establishment in the EEA must deal with local supervisory authorities in every Member State they are active in, through their local representative"; an Art. 27 representative does not create a lead authority — EDPB 8/2022. Relevant to US-based Brokers.
- **What a complaint contains today.** National procedure decides. The EDPB template form (optional; each authority chooses mandatory fields) asks for: whether the filer is the affected person or a representative; name, address, email, phone; the Organization's name and contact details; facts in chronological order; the infringement alleged and the remedy sought; whether the Organization or its data protection officer was contacted first, with the exchanges attached; and evidence such as correspondence and "proof of when the entity received a request, such as the date stamps on an email" — EDPB complaint form. Some authorities treat prior contact with the Organization as a requirement.
- **From 2 April 2027 (cross-border complaints).** Reg. 2025/2518 makes a cross-border complaint admissible if it contains the complainant's name and contact details, information identifying the controller or processor, and a description of the alleged infringement. "No information additional to that ... shall be required"; "the complainant shall not be required to have contacted the party under investigation before lodging a complaint"; the authority has two weeks to declare a deficient complaint inadmissible and six weeks to pass an admissible one on. The article number is 3 or 4 depending on the version seen; not confirmed — https://eur-lex.europa.eu/eli/reg/2025/2518/oj/eng
- **Courts in parallel.** Arts. 77 and 79 remedies can be pursued side by side (unverified against source).

**UK**

- **Step 1, the Organization.** A data subject may complain to the controller; the controller must facilitate complaints (for example with an electronic form), "acknowledge receipt of the complaint within the period of 30 days", take appropriate steps to respond, and inform the complainant of the outcome without undue delay — DPA 2018 s.164A, inserted by DUAA s.103 https://www.legislation.gov.uk/ukpga/2025/18/section/103. In force 19 June 2026 for complaints made on or after that date — SI 2026/82 regs. 3 and 7.
- **Step 2, the regulator.** DPA 2018 s.165 (complaints to the Commissioner) remains. The regulator recommends giving the Organization a chance to complete its complaint handling first: complain to the Organization, ask it to clarify an unclear response, follow up if there is no reply after 30 days, then complain to the regulator "within three months of your last contact with the organisation" (elsewhere worded "last meaningful contact"), keeping copies of correspondence — https://ico.org.uk/for-the-public/how-to-make-a-data-protection-complaint/ and https://ico.org.uk/make-a-complaint/what-to-expect/
- **Is step 1 legally mandatory?** No statutory text was found that bars a complaint to the regulator until the Organization has been complained to. It is the regulator's stated expectation, not a confirmed legal precondition.
- **Free.** Complaining to the UK regulator is free (unverified against source).
- **No one-stop-shop.** The UK is outside the EU cooperation mechanism; a UK Subject complains to the UK regulator, an EU Subject to an EU authority (unverified against source).

## 7. UK differences and the Data (Use and Access) Act 2025

| Change | Provision | In force | Source |
|---|---|---|---|
| Access limited to what a "reasonable and proportionate search" finds | DUAA s.78 → UK GDPR Art. 15(1A) | At Royal Assent, 19 June 2025 (s.142(2)(b)); "treated as having come into force on 1 January 2024" | https://www.legislation.gov.uk/ukpga/2025/18/section/78 |
| Statutory time limits; month starts on receipt of ID information or fee; stop-the-clock for clarification of an access request | DUAA s.76 → UK GDPR Art. 12A | See note below | https://www.legislation.gov.uk/ukpga/2025/18/section/76 |
| Most other Part 5 data-protection provisions | SI 2026/82 (Commencement No. 6) | 5 February 2026 | https://ico.org.uk/about-the-ico/media-centre/news-and-blogs/2026/02/statement-on-the-commencement-of-the-data-use-and-access-act-duaa/ |
| Organizations must run a data-protection complaints process | DUAA s.103, Sch. 10 → DPA 2018 ss.164A, 164B | 19 June 2026 | https://www.legislation.gov.uk/uksi/2026/82/made |
| Information Commissioner abolished; functions pass to the Information Commission | DUAA ss.118, 119 | 30 September 2026 | https://www.legislation.gov.uk/uksi/2026/1015/pdfs/uksi_20261015_en.pdf |

- **Note on s.76.** No excerpt named s.76 in a commencement instrument. The government's plan put all of Part 5 except s.103 in the stage commenced on 5 February 2026, and the regulator stated on 19 June 2026 that "all outstanding provisions are now in force". So s.76 is in force today; the exact date (most likely 5 February 2026) is not confirmed. https://www.gov.uk/guidance/data-use-and-access-act-2025-plans-for-commencement
- **Regulator name.** Since 30 September 2026 the UK Supervisory Authority is the Information Commission, a body corporate with a board; it still publishes at ico.org.uk — https://www.gov.uk/government/news/information-commission-succeeds-the-ico-as-uks-data-protection-regulator. `GLOSSARY.md` still says "the UK ICO".
- **Otherwise the same.** No form requirement; one month; Art. 12(5) "manifestly unfounded or excessive" wording unchanged by DUAA (unverified against source); Art. 17 grounds and exceptions mirror the EU text — ICO erasure. UK-specific exemptions from access and erasure sit in DPA 2018 Schedules 2–4 (unverified against source).
- **Not checked:** whether UK GDPR Art. 12A changes how the month is counted compared with the pre-2026 ICO method; and whether DUAA altered Art. 12(6) UK GDPR.

## Could not verify

- The full text of every source: all five primary-source hosts were blocked, so nothing was read in full.
- EDPB 01/2022 paragraph numbers 13, 35, 53–56 (individually), 78–79, 160–162, and the English wording of para. 90.
- Whether the adopted EDPB 01/2022 keeps the draft's "every three months is not excessive" and "one year can never be excessive" statements.
- GDPR text of Arts. 12(2) (second sentence), 12(3) (electronic-reply and notice sentences), 12(4), 15(1) list, 15(2), 17(1)(e)–(f), 17(2), 19, 21(1), 56, 60, 79, 80; Recital 63; second sentence of Recital 64.
- The ranking of Art. 17(3) exceptions beyond first place in EDPB CEF 2025.
- The article number (3 or 4) and exact list wording of the admissibility rule in Reg. 2025/2518.
- The exact commencement date of DUAA s.76.
- Which ICO version is right on when a stopped clock resumes.
- Whether complaining to the Organization first is a legal precondition in the UK, or in any EU member state.
- Current status of the Digital Omnibus amendment to Art. 12(5).
- The current member-state list of Art. 8 ages, and the UK section numbers DPA 2018 s.9 and s.208.
- National rules on who may represent an adult before a Supervisory Authority.

## Implications for Unlist

**Sending requests**

- Send plain email; never depend on an Organization's form or portal. Do keep, per Organization, an *official* privacy/DPO contact in the Organization List: mail to a wrong address does not start the clock.
- Do not include reasons in an Access Request. Ask for everything: confirmation, a copy, and each Art. 15(1) item, calling out source and named recipients. The answers identify further Organizations to add.
- An Access Request must treat "we hold nothing" as a valid, terminal answer (no Listing).
- A Removal Request should combine erasure (Art. 17(1), citing the fitting grounds per Organization type), objection (Art. 21(1) and 21(2)), consent withdrawal (Art. 7(3)), account closure where there is one, and a request to notify recipients. It should accept — or ask for — a minimal suppression record at Brokers, since that is what stops re-listing.
- Model "refused under Art. 17(3)(b) or (e)" as an expected outcome with partial erasure, not as non-compliance. Model "refused under Art. 12(5)" separately; the Organization must give reasons.
- Keep request text identical in legal substance for EU and UK but switch citations (GDPR vs UK GDPR) and the regulator's name.

**Deadlines**

- Record a send timestamp and keep the sent message with headers: Supervisory Authorities ask for proof of when the Organization received the request.
- Compute due date as the same day-number in the following month, falling back to the last day of the month, then rolling past weekends and public holidays of the Organization's country. Store the rule used.
- Model three events that move the due date: an extension notice (plus two months, valid only if received inside the first month and reasoned); an identity-information request (EU: pause from ask to reply; UK: fresh month from reply); a clarification request (UK: pause, access only).
- Reply to identity or clarification requests fast: until the Subject answers, the clock is not running against the Organization.
- Add a grace margin before treating an Organization as overdue, because of the counting ambiguities above.

**Identity**

- Send from the address the Organization knows the Subject by where possible: it is the cheapest authentication and makes an ID demand harder to justify.
- Never attach ID documents pre-emptively. When an Organization demands a copy of ID, surface it to the Subject as a decision, offer a reply citing Art. 12(6) and EDPB 01/2022 paras. 73–75, and if ID is sent, support redaction.
- Expect Organizations to ask for information that distinguishes the Subject (previous addresses, customer number); store these per Subject so replies are quick.

**Acting for Subjects**

- Each adult Subject must authorise the Operator. Record that authorisation (who, when, scope) and be able to produce a signed authority, since UK guidance puts the burden of proof on the representative.
- Because mail goes from the Subject's own address, the request reads as made by the Subject. It must therefore really be theirs: have the Subject review and approve what is sent in their name. UK guidance on AI-assisted requests explicitly anticipates Organizations contacting the person directly to check.
- For child Subjects, record who holds parental responsibility and the child's age; do not auto-apply a consent-age table to decide who may request. Flag older children (UK: competent; Scotland: 12 and over) as needing the child's own involvement.
- Do not present Unlist as a portal the Organization must log into to answer; answers should come back to the Subject's mailbox.

**Repeat requests**

- Do not hard-code a re-request interval as "legally safe"; none exists. Make the interval configurable per Organization, longer by default for Organizations whose data rarely changes, shorter for Brokers.
- Never send requests whose evident aim is something other than exercising the right (for example to generate compensation claims); that is the fact pattern in which a first request can lawfully be refused.

**Complaints**

- Unlist drafts; the Subject lodges. Do not submit Complaints under the Operator's name.
- EU: target the Subject's own Supervisory Authority (residence), and note the Organization's country so a lead authority can be identified; for Organizations with no EEA establishment there is no lead authority.
- UK: put a stage before the Complaint, because the regulator expects it — a complaint to the Organization under DPA 2018 s.164A, a 30-day wait, then the regulator within three months of last contact.
- A Complaint draft needs: Subject's name and contact details, the Organization's identity and contacts, a chronological account, the infringement alleged (which request, which deadline missed), the remedy sought, whether the Organization was contacted first, and the attached correspondence with dates.
- Avoid flooding one Supervisory Authority with many Complaints at once; batch or prioritise.

**Maintenance**

- Treat this file as dated. Re-check before release: Digital Omnibus changes to Art. 12(5); Reg. 2025/2518 applying from 2 April 2027; the UK regulator's forthcoming AI-request guidance; the UK regulator's name in `GLOSSARY.md`.
