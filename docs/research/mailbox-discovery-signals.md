# Which signals in a mailbox reliably identify an Organization and an account?

Research for issue #6. Checked on **2026-11-26**.

## Answer

1. **Identity key:** the registrable domain (Public Suffix List, both sections) of the `From:` address, counted only when the mailbox provider's own `Authentication-Results` shows a DMARC pass or an aligned DKIM `d=`. Header-only, no LLM.
2. **Do not key on the rest:** `Return-Path`, an unaligned DKIM `d=`, the `List-Id` namespace and `Feedback-ID` usually name the email service provider (ESP), not the brand. Use them to detect "sent through an ESP". If `From:` itself sits on a shared ESP or platform domain, fall back to display name plus `List-Unsubscribe` host and flag for review.
3. **Why headers are now dependable:** Gmail (from 1 February 2024) and Outlook.com (enforcement said to start May 2025; date from a search excerpt only) require senders of 5,000 or more messages a day to pass SPF, DKIM and DMARC with `From:` aligned to the SPF or DKIM domain. Yahoo (enforcement from February 2024) applies the same authentication rules to "bulk" senders but publishes **no volume threshold**. For marketing and subscribed mail Gmail requires RFC 8058 one-click (`List-Unsubscribe` + `List-Unsubscribe-Post`) from 5,000+/day senders; Yahoo requires a one-click-capable `List-Unsubscribe` header, calls the RFC 8058 POST method "highly recommended" and accepts `mailto:`. Transactional mail is exempt from the unsubscribe rule at both.
4. **Bulk versus personal:** any `List-*` header, `Precedence: bulk|list|junk`, or `Auto-Submitted` other than `no` marks a message as not written by a person. These prove the Organization holds the address and mails it. They do not prove an account.
5. **Account evidence, strongest first:** schema.org `Order` / `Invoice` / `ParcelDelivery` / `*Reservation` markup in the HTML body, then order, receipt, invoice and shipping mail, then welcome, verification, password-reset, security and policy notices, then newsletters. Subject and local-part keyword rules cover most of it without an LLM.
6. **Domain is not the legal entity:** an Access Request or Removal Request must reach the GDPR controller. Map domain to Organization through Organization Lists (`datenanfragen/data` has `web` and `runs`, JustDeleteMe has `domains`), then the Organization's own privacy page. Never guess an address.
7. **Cheap IMAP scan:** `EXAMINE` (read-only) plus `UID FETCH … BODY.PEEK[HEADER.FIELDS (…)]` reads chosen headers without setting `\Seen`. Incremental scans need only `UIDVALIDITY` and the highest UID seen. CONDSTORE and QRESYNC matter only for tracking flag changes and expunges.
8. **mbox:** there is no authoritative spec. RFC 4155 only registers the media type, and four variants (mboxo, mboxrd, mboxcl, mboxcl2) differ in `From ` quoting. Header signals only need correct message splitting. Google's Takeout help page confirms an `X-Gmail-Labels` header per message; no Google page read states that Takeout writes Gmail as mbox (see the Takeout section).
9. **Login today:**
   - **Gmail personal:** app password (needs 2-Step Verification; Google says they "aren't recommended") or OAuth. Both are documented on Google's own pages. Password-only third-party sign-in is gone; the date is not on any page read.
   - **Google Workspace:** OAuth. Whether an app password is still possible is **unconfirmed**: Google's app-password page lists "a work, school, or another organization account" among the reasons the option can be missing, while a search excerpt of the admin page says users may use an app password. The admin pages moved to a host that was blocked. Google's readable page says password-only access ends "Starting January 2025"; the "1 May 2025" date comes from a search excerpt only.
   - **Outlook.com:** Basic authentication ended 16 September 2024 and the settings page lists OAuth2/Modern Auth for IMAP, POP and SMTP. The same settings page still says "you may need an app password". Microsoft's pages contradict each other; treat app passwords as unproven for IMAP until a live test.
   - **Microsoft 365:** **IMAP:** Basic auth is disabled in all tenants and cannot be re-enabled; OAuth only, and Microsoft says the change also prevents app passwords with apps that don't support two-step verification. **SMTP AUTH:** a different timeline. Basic is still available (Microsoft page last updated 2026-09-16), disabled by default only where unused or under security defaults, and its retirement is announced with a date on a page that was blocked.
   - A Takeout mbox needs no credentials at all.
10. **Prior art:** `tmaeder/eraser` already does a headers-only IMAP scan, groups by registrable domain and sends GDPR requests. Nothing found combines authenticated-domain identity, graded account evidence and shareable Organization Lists. `email-oauth2-proxy` (Apache-2.0) is the reference for the OAuth problem.

**Confidence note (after the 2026-11-26 verification pass).** The first draft was written from a sandbox that reached only GitHub, package registries and web search. A second pass, with www.rfc-editor.org, support.google.com, developers.google.com, learn.microsoft.com, support.microsoft.com and senders.yahooinc.com reachable, re-read the primary pages and RFC texts. What they confirmed is now tagged `[read]` with the source URL and "read 2026-11-26"; what they contradicted is corrected in place and listed in the [Verification log](#verification-log). Still **not** confirmed: the Google Workspace admin pages (support.google.com/a/answer/14114704, 105694, 9176599 and 7281227 now redirect to knowledge.workspace.google.com, which the proxy blocked), anything on techcommunity.microsoft.com or workspaceupdates.googleblog.com, the ESP documentation sites (mailchimp.com, twilio.com, docs.aws.amazon.com, help.klaviyo.com), ftc.gov and eur-lex.europa.eu (never reachable), datatracker.ietf.org (not fetched; the RFC Editor pages were enough), and every point that only a live test on a real mailbox can settle. Remaining `[search]` tags rest on search-engine excerpts. The list is at the [end](#not-verified).

## Verification

| Tag | Meaning |
|---|---|
| `[read]` | Read in full on 2026-11-26 from the primary source: RFC text from www.rfc-editor.org (`.txt`, plus the `/info/` page for status and obsoleted-by), vendor pages on support.google.com, developers.google.com, learn.microsoft.com, support.microsoft.com and senders.yahooinc.com, or a clone of the project's own GitHub repo at the commit named. RFC quotes first read from the Ubuntu `doc-rfc_20230121` snapshot were re-matched against the rfc-editor.org text in the second pass. |
| `[search]` | Taken from search-engine excerpts or summaries of the live official page. Wording may be paraphrased. The page could not be read in full in this session (host blocked, or the page redirects to a host that is blocked). |
| `[memory]` | Not confirmed in this session. From memory, **(unverified)**. |
| `[analysis]` | My own reasoning from the verified facts. A design judgement, not a sourced fact. |

## Signals ranked by reliability and cost

"Body" means the scan must download the message body, not just headers. "LLM" means a language model is needed for acceptable results. Reliability is for the stated purpose only. `[analysis]` for every ranking; the facts behind each row are sourced in the sections below.

| # | Signal | What it tells Unlist | Reliability | Body? | LLM? | Cost and caveats |
|---|---|---|---|---|---|---|
| 1 | `From:` registrable domain, with DMARC pass or aligned DKIM `d=` in the provider's `Authentication-Results` | Which Organization (as a domain) sent it | High | No | No | One header fetch. Trust only the provider's own topmost `Authentication-Results`. Old mail may predate DMARC. |
| 2 | schema.org `Order`, `Invoice`, `ParcelDelivery`, `*Reservation` (JSON-LD or microdata) | A transaction happened; merchant name; order number | High when present | Yes (HTML part) | No | Present on a minority of mail (prevalence unverified). Fetch bodies only for candidates. |
| 3 | `List-Unsubscribe` + `List-Unsubscribe-Post: List-Unsubscribe=One-Click` | Marketing or subscribed mail; a one-click removal route exists | High for "bulk marketing" | No | No | Says nothing about an account. Gmail requires it on marketing mail from 5,000+/day senders (since 2024); Yahoo requires a one-click-capable header but accepts `mailto:`, so the POST pair is not universal. |
| 4 | `List-Unsubscribe` alone, `List-Id`, other `List-*` | Mailing-list or bulk mail | High for "not personal" | No | No | `List-Id` namespace is often the ESP's. Discussion lists: the Organization is the list operator, not the author. |
| 5 | `Auto-Submitted` (not `no`), `Precedence: bulk/list/junk`, `X-Auto-Response-Suppress`, null `Return-Path` | Machine-generated mail | Medium-high for "automated" | No | No | `Precedence` is non-standard. Many transactional senders set none of these. |
| 6 | Subject and `From:` local-part keyword rules (order, receipt, invoice, welcome, verify, reset, shipped; `noreply@`, `billing@`, `orders@`) | Evidence type: transaction, account, security, policy, marketing | Medium | No | No, but an LLM improves recall | Needs per-language keyword packs. Subject is personal data; store the class, not the text. |
| 7 | Recipient address (`To:`, `Delivered-To:`), including plus-tags and aliases | Which Subject, and which address the Organization holds | High | No | No | Needed to fill the request. Absent on some Bcc-style bulk mail. |
| 8 | First-seen date, last-seen date, message count per Organization | How long and how actively the Organization has had the address | High as a fact, medium as evidence | No | No | Free once headers are indexed. |
| 9 | Gmail category (`X-Gmail-Labels` in Takeout; `category:` search) | Google's own promotions / updates / purchases classification | Medium | No | No | Gmail only. Depends on the user's inbox settings. |
| 10 | DKIM `d=` not aligned with `From:`, `Return-Path` domain, `Feedback-ID`, `List-Id` namespace, ESP `X-*` headers | Which ESP carried the mail | High for "which ESP", low for "which Organization" | No | No | Use to detect ESP relays and shared sending domains. Never as the Organization key. |
| 11 | Display name in `From:` | Brand name | Low alone | No | No | Trivially spoofable. Useful only together with rows 1 or 10. |
| 12 | `List-Unsubscribe` URL host, link hosts in body | Brand or ESP tracking domain | Low-medium | Header: no. Links: yes | No | Often an ESP click-tracking domain. |
| 13 | Legal entity in footer or imprint (company name, registered address) | The GDPR controller behind the brand | Medium-high when found | Yes | Usually | Regex catches "GmbH", "Ltd", "Inc." lines poorly across languages. An LLM is the practical extractor. |
| 14 | Organization List match on domain (`datenanfragen/data` `web`/`runs`, JustDeleteMe `domains`) | Legal entity and privacy contact | High when matched | No | No | Coverage is partial and Germany-heavy. See `organization-lists.md`. |

Recommended pipeline without an LLM `[analysis]`: rows 1, 3, 4, 5, 7 and 8 from one headers-only pass give Organizations and a bulk / automated / personal split. Row 6 grades evidence. Row 2 is fetched only for Organizations whose evidence is still weak. Row 14 resolves the legal entity. An LLM is only needed for row 13 and for the residue row 6 cannot classify.

## 1. Header signals

### List-Unsubscribe (RFC 2369)

- RFC 2369 (Standards Track, July 1998) defines `List-Help`, `List-Unsubscribe`, `List-Subscribe`, `List-Post`, `List-Owner` and `List-Archive`. `[read]` https://www.rfc-editor.org/rfc/rfc2369
- Syntax: the value is a comma-separated list of angle-bracketed URLs, in "order of preference from left to right". "The client application should use the left most protocol that it supports", and use another "only if the first one used failed". Whitespace inside the brackets is to be ignored. `[read]` RFC 2369 §2
- Parsing rules a client MUST follow: ignore the field if it does not start with `<` (after whitespace and comments); ignore anything after a URL unless a comma follows; if a sub-item is not an angle-bracketed URL, ignore it and everything after it. `[read]` RFC 2369 §2
- `List-Unsubscribe` "describes the command (preferably using mail) to directly unsubscribe the user". Examples in the RFC use `mailto:` with `?subject=` or `?body=`, and `http:` URLs. `[read]` RFC 2369 §3.2
- There "MUST be no more than one of each field present in any given message", and "These fields MUST only be generated by mailing lists, not end users." `[read]` RFC 2369 §3. So any `List-*` header is, by spec, a sign of non-personal mail.
- A client that sends the `mailto:` command through a dialog "MUST include an option for the user to review (and possibly modify) the message before it is sent". `[read]` RFC 2369 Appendix B.2.4
- A plain HTTP(S) URL in `List-Unsubscribe` is not safe to fetch automatically. RFC 8058 explains that senders "return landing pages with a confirmation step" because anti-spam software fetches such URLs. `[read]` RFC 8058 §1

### One-click unsubscribe (RFC 8058)

- RFC 8058 (Standards Track, January 2017) adds `List-Unsubscribe-Post`. It "does not update [RFC2369]". `[read]` https://www.rfc-editor.org/rfc/rfc8058
- Sender side: the message carries one `List-Unsubscribe` and one `List-Unsubscribe-Post`. `List-Unsubscribe` "MUST contain one HTTPS URI" and "MAY contain other non-HTTP/S URIs such as MAILTO:". `List-Unsubscribe-Post` "MUST contain the single key/value pair `List-Unsubscribe=One-Click`". `[read]` RFC 8058 §3.1
- The URI must identify the recipient and the list by itself, because "there is no provision for extra POST arguments". It SHOULD contain an opaque, hard-to-forge component. The sender "MUST NOT return an HTTPS redirect". `[read]` RFC 8058 §3.1
- How a client performs it: "an HTTPS POST to the HTTPS URI in the List-Unsubscribe header", sending "the key/value pair in the List-Unsubscribe-Post header as the request body". The body "SHOULD be sent as `multipart/form-data`" or "MAY be sent as `application/x-www-form-urlencoded`". `[read]` RFC 8058 §3.2. The RFC's example:

  ```
  POST /unsubscribe/opaquepart HTTP/1.1
  Host: example.com
  Content-Type: application/x-www-form-urlencoded
  Content-Length: 26

  List-Unsubscribe=One-Click
  ```
  `[read]` RFC 8058 §8.1
- The POST "MUST NOT include cookies, HTTP authorization, or any other context information". `[read]` RFC 8058 §3.1
- Consent: "The mail receiver MUST NOT perform a POST on the HTTPS URI without user consent." `[read]` RFC 8058 §3.2. For Unlist this means an explicit Operator action per Organization, never a background sweep.
- DKIM precondition: the message must have a valid DKIM signature, and both headers "MUST be covered by the signature and included in the `h=` tag". Without it, "the mail receiver SHOULD NOT offer a one-click unsubscribe for that message". `[read]` RFC 8058 §4
- Practical consequence `[analysis]`: before offering one-click, check that a `DKIM-Signature` header lists `list-unsubscribe` and `list-unsubscribe-post` in `h=`, and that the provider's `Authentication-Results` reports `dkim=pass` for that signature's domain. Both are header-only checks. Re-verifying the signature locally needs the full body and the sender's DNS key, which may have been rotated for old mail.
- `tmaeder/eraser` posts one-click without a DKIM check (no reference to DKIM or `Authentication-Results` anywhere in `src/`). `[read]` commit 35bd73a

### The Gmail, Yahoo and Outlook.com bulk-sender rules

These rules are why the headers above are now near-universal on recent marketing mail.

- **Gmail.** Since 1 February 2024 every sender to Gmail accounts must set up SPF or DKIM, have valid forward and reverse DNS, use TLS, keep the user-reported spam rate below 0.3% and format mail per RFC 5322. Senders of more than 5,000 messages a day must set up SPF, DKIM and DMARC (policy may be `none`), and for direct mail the `From:` domain must align with the SPF domain or the DKIM domain; only one needs to align, and alignment is not required for forwarded or mailing-list mail. `[read]` https://support.google.com/a/answer/81126 and https://support.google.com/a/answer/14229414, read 2026-11-26
- A bulk sender is one that sends "close to 5,000 messages or more to personal Gmail accounts within a 24-hour period", counted per primary domain, and the status is permanent once reached. The guidelines and the sender requirements apply to mail sent to personal Gmail accounts, not to mail sent to Google Workspace accounts. `[read]` https://support.google.com/a/answer/14229414, read 2026-11-26
- Marketing and subscribed messages must support one-click unsubscribe and also carry a clearly visible unsubscribe link in the body. Only `List-Unsubscribe-Post: List-Unsubscribe=One-Click` plus a `List-Unsubscribe` header with one HTTPS URL, per RFC 8058, counts: "mailto and URL unsubscribe links, don't meet our one-click unsubscribe requirement". Senders that already had an unsubscribe link had until 1 June 2024. Google recommends honouring requests within 48 hours. Missing one-click does not by itself cause rejection or spam-foldering, but removes eligibility for mitigation support. `[read]` https://support.google.com/a/answer/81126 and https://support.google.com/a/answer/14229414, read 2026-11-26
- **Transactional mail is excluded** from the one-click requirement: "One-click unsubscribe is required only for marketing and promotional messages. Transactional messages are excluded". Google's examples: "password reset messages, reservation confirmations, and form submission confirmations". Google adds that the promotional / transactional line "can vary" and that "Message recipients, not Google, determine the nature of the messages they receive". `[read]` https://support.google.com/a/answer/14229414, read 2026-11-26
- Gmail says that "Starting November 2025, Gmail is ramping up its enforcement on non-compliant traffic", with temporary and permanent rejections. `[read]` https://support.google.com/a/answer/14229414, read 2026-11-26
- **Yahoo.** "Beginning in February 2024, enforcement of the following sending standards will take effect", rolled out gradually. Bulk senders must implement SPF and DKIM, publish a DMARC policy of at least `p=none` that passes, with `From:` aligned to the SPF or DKIM domain ("Relaxed alignment is acceptable"). Marketing and subscribed mail needs a "functioning list-unsubscribe header, which supports one-click unsubscribe"; "The Post (RFC 8058) method is highly recommended" and "The mail-to: method is acceptable". A visible unsubscribe link in the body is also required, and requests must be honoured within 2 days. **Yahoo sets no volume threshold**: a bulk sender is "an email sender sending a significant volume of mail. We will not specify a volume threshold." One-click is not required for transactional mail (order confirmations, password resets). Enforcement of the List-Unsubscribe policy began June 2024. The rules apply to all domains and consumer brands hosted by Yahoo Mail, AOL included. `[read]` https://senders.yahooinc.com/best-practices/ and https://senders.yahooinc.com/faqs/, read 2026-11-26
- **Outlook.com (consumer).** A high-volume sender is one that sends "5,000 or more email messages to Microsoft consumer email services" with all messages using the same 5322.From domain. Such domains must publish SPF and DKIM (both must pass), publish a DMARC record (`p=none` is enough) and pass DMARC through an aligned SPF and/or DKIM (only one is required). Failures bounce with `550 5.7.515`. `[read]` https://support.microsoft.com/en-us/outlook/fix-ndr-error-550-5-7-515-in-outlook-com, read 2026-11-26. That page gives **no enforcement date** and says nothing about unsubscribe links. "Enforcement started in May 2025" and "a functional unsubscribe link is a recommendation, not a requirement" remain `[search]` from https://techcommunity.microsoft.com/blog/microsoftthreatprotectionblog/strengthening-email-ecosystem-outlook%E2%80%99s-new-requirements-for-high%E2%80%90volume-senders/4399730 (blocked host).
- Consequence `[analysis]`: on mail received since 2024, `List-Unsubscribe-Post` present means bulk marketing, and its absence on automated mail from a known Organization is a weak hint of transactional mail. Neither inference holds for older mail or for small senders under the threshold.

### List-Id (RFC 2919)

- Syntax: `List-ID: [phrase] <list-label.list-id-namespace>`. The comparison "MUST ignore any part of the List-Id header outside of the angle brackets" and is case-insensitive. `[read]` https://www.rfc-editor.org/rfc/rfc2919 §3, §6
- The namespace is a domain: "the owner of a mailing list MUST NOT generate list identifiers in any domain namespace for which they do not have authority". But "a mailing list hosting service may choose to assign list identifiers in their own domain based namespace". `[read]` RFC 2919 §2. So the `List-Id` domain is as often the ESP's as the brand's.
- "This field MUST only be generated by mailing list software, not end users", and there MUST be at most one. `[read]` RFC 2919 §3
- A MUA "SHOULD treat a different list identifier as a different list". `[read]` RFC 2919 §4. `List-Id` is therefore a good key for "one subscription", finer than the Organization. `schellevis/bulk-unsubscribe` groups senders by `List-ID` with `From:` as fallback. `[read]` README, commit c7d82e6

### Precedence

- `Precedence` is not standardised. RFC 2076 (Informational, 1997) lists it as "Non-standard, controversial, discouraged", with common values "bulk" and "first-class". `[read]` https://www.rfc-editor.org/rfc/rfc2076 §3.9
- RFC 3834 repeats that "Precedence is not a standard header field, and its use and interpretation vary widely", while naming the values "list", "junk" and "bulk" as what responders look for. `[read]` https://www.rfc-editor.org/rfc/rfc3834 §2, §3.1.8

### Auto-Submitted (RFC 3834)

- Syntax: `Auto-Submitted: no | auto-generated | auto-replied | extension`, with optional parameters; at most one per message. `[read]` RFC 3834 §5.1
- `auto-generated` is for "messages generated by automatic (often periodic) processes … which are not direct responses to other messages". `auto-replied` is for automatic direct responses. `no` may mark human-originated mail. `[read]` RFC 3834 §5.2
- "Recipients of messages containing an Auto-Submitted field with any keyword other than "no" MAY assume that the message was not manually submitted by a human." `[read]` RFC 3834 §5.2
- A null return path (`MAIL FROM:<>`, `Return-Path: <>`) marks bounces and other automatic responses. `[read]` RFC 3834 §2
- `X-Auto-Response-Suppress` is a Microsoft header (values `DR`, `NDR`, `RN`, `NRN`, `OOF`, `AutoReply`, `All`, `None`) that suppresses delivery reports, read notifications and automatic replies. Automated senders set it; people do not. `[read]` https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxcmail/ced68690-498a-4567-9d14-5c01f974d8b1, read 2026-11-26. "Automated senders set it" is `[analysis]`.

### Feedback-ID and CFBL-Address

- `Feedback-ID` is defined by Gmail's Feedback Loop, not by an RFC. Format: `Feedback-ID: a:b:c:SenderId`. `a`, `b`, `c` are optional campaign or customer identifiers. `SenderId` is mandatory, 5 to 15 characters, chosen by the sender and stable across its mail stream. Traffic must be DKIM-signed by a domain the sender owns or controls, after the header is added, so the header cannot be spoofed. `[read]` https://support.google.com/mail/answer/6254652, read 2026-11-26
- Use for Unlist `[analysis]`: when an ESP sets it, `SenderId` names the ESP and the other fields name the ESP's customer. It is an ESP fingerprint and sometimes a stable per-brand token, not an identity.
- RFC 9477, "Complaint Feedback Loop Address Header", September 2023, Category **Experimental**, Independent Submission (not an IETF Standards Track document), defines `CFBL-Address` and `CFBL-Feedback-ID`, a sender-published complaint address. When present, both "MUST be included in the "h=" tag" of a valid DKIM signature for the sending domain; otherwise the Mailbox Provider "SHALL NOT send a report message". `[read]` https://www.rfc-editor.org/rfc/rfc9477, read 2026-11-26

### Other headers worth fetching

| Header | Use | Source |
|---|---|---|
| `From:` | Author. "The "From:" field specifies the author(s) of the message". | `[read]` RFC 5322 §3.6.2 |
| `Sender:` | The transmitting agent when it differs from the author. An ESP or a "on behalf of" relay may appear here. | `[read]` RFC 5322 §3.6.2 |
| `Reply-To:` | A second brand-controlled domain. `eraser` fetches it. | `[read]` eraser README |
| `Return-Path:` | The envelope sender, inserted at final delivery. "It is possible for the mailbox in the return path to be different from the actual sender's mailbox". | `[read]` RFC 5321 §4.4 |
| `DKIM-Signature:` | `d=` (signing domain), `s=` (selector), `h=` (signed headers). There may be several. | `[read]` RFC 6376 §3.5 |
| `Authentication-Results:` | The receiving provider's SPF, DKIM and DMARC verdicts. | `[read]` RFC 8601 |
| `To:`, `Delivered-To:` | Which address the Organization holds. | `[analysis]` |
| `Message-ID:`, `Date:` | Deduplication and timeline. | `[analysis]` |
| `In-Reply-To:`, `References:` | A reply to something the Subject wrote suggests personal or support correspondence. | `[analysis]` |

Distinguishing the three classes `[analysis]`:

- **Bulk / marketing:** any `List-*` header, `Precedence: bulk|list|junk`, or `Feedback-ID`.
- **Transactional / automated:** no `List-Unsubscribe`, but `Auto-Submitted` not `no`, or `X-Auto-Response-Suppress`, or a role local-part (`noreply`, `no-reply`, `billing`, `orders`, `security`, `account`), from a non-freemail domain.
- **Personal:** none of the above, a freemail or own-domain sender, and ideally `In-Reply-To` pointing at the Subject's own mail or an address the Subject has written to. `eraser` uses a built-in list of personal mail providers and excludes them "unless the mail carries mailing-list headers". `[read]` `src/scanner/domain.rs`, commit 35bd73a
- rspamd's `maillist` plugin and header rules are an Apache-2.0 reference for mailing-list detection from `Precedence`, `List-*` and software-specific headers. `[read]` https://github.com/rspamd/rspamd `src/plugins/lua/maillist.lua`, commit 21d3ad9

## 2. Identifying the Organization behind a sender

### Four identities in one message

| Identity | Where | What it authenticates | Sees through ESPs? |
|---|---|---|---|
| Author domain | `From:` (RFC5322.From) | Nothing by itself | Yes, if aligned (below) |
| Envelope sender | `Return-Path:` (RFC5321.MailFrom) | SPF checks this domain | No. Usually the ESP's bounce domain |
| Signing domain | `DKIM-Signature: d=` | That `d=` took responsibility for the message | Only the signature whose `d=` matches `From:` |
| List namespace | `List-Id:` | Nothing | Often the ESP's |

- DKIM deliberately does not tie the signer to the author: "DKIM separates the question of the identity of the Signer of the message from the purported author of the message." `d=` is "the SDID claiming responsibility for an introduction of a message into the mail stream". `[read]` https://www.rfc-editor.org/rfc/rfc6376 §1.2, §3.5
- "This document does not require the value of the SDID or AUID to match an identifier in any other message header field." `[read]` RFC 6376 §3.11
- The `From:` header "MUST be signed". A message may carry several signatures, "from the same or different organizations". `[read]` RFC 6376 §5.4, §1, §4
- DMARC is what binds them: it "authenticates use of the RFC5322.From domain by requiring that it match (be aligned with) an Authenticated Identifier". RFC 7489 is Informational, an Independent Submission, March 2015, §3.1. `[read]` https://www.rfc-editor.org/rfc/rfc7489. **Status now:** the RFC Editor lists RFC 7489 as obsoleted by RFC 9989 (DMARC, Standards Track, May 2026), RFC 9990 (Aggregate Reporting) and RFC 9991 (Failure Reporting). `[read]` https://www.rfc-editor.org/info/rfc7489, read 2026-11-26. Alignment rules below are quoted from RFC 7489; RFC 9989 was not compared clause by clause.
- DKIM alignment: in relaxed mode "the Organizational Domains of both the DKIM-authenticated signing domain (taken from the value of the "d=" tag in the signature) and that of the RFC5322.From domain must be equal". In strict mode the FQDNs must match exactly. `[read]` RFC 7489 §3.1.1
- SPF alignment is the same test between the SPF-authenticated `MAIL FROM` domain and the `From:` domain. `[read]` RFC 7489 §3.1.2
- Both modes default to relaxed (`adkim=r`, `aspf=r`). `[read]` RFC 7489 §6.3
- "a message can bear a valid signature from any domain, including domains used by a mailing list or even a bad actor. Therefore, merely bearing a valid signature is not enough to infer authenticity of the Author Domain." `[read]` RFC 7489 §3.1.1
- "a single email can contain multiple DKIM signatures, and it is considered to be a DMARC "pass" if any DKIM signature is aligned and verifies." `[read]` RFC 7489 §3.1.1

**Rule for Unlist** `[analysis]`: the Organization key is the registrable domain of `From:`, accepted as evidence when `Authentication-Results` shows `dmarc=pass`, or a `dkim=pass` whose domain shares the registrable domain of `From:`. Mail that fails this is not evidence of anything; it is as likely to be phishing in the brand's name. Mail in Spam or Junk folders should be skipped for the same reason.

### Trusting Authentication-Results

- RFC 8601 warns that the header can be forged: a malicious sender can add one naming the receiver's `authserv-id`, and a non-conformant border MTA "would fail to strip the forged header field". Clients should ignore the header "unless specifically enabled by the user or administrator after verifying that the border MTA is compliant", ideally with "an explicit list of hostnames whose Authentication-Results header fields are trustworthy". `[read]` https://www.rfc-editor.org/rfc/rfc8601 §7.1
- One usable test: the genuine header "should always appear above a Received header added by a trusted MTA". `[read]` RFC 8601 §7.1
- Rule for Unlist `[analysis]`: keep a small table of provider → `authserv-id` (for example `mx.google.com` for Gmail `[memory]`), accept only the topmost matching instance, and treat mail without one as unauthenticated. A forwarded message keeps the first hop's verdicts lower in the header block; ignore those.
- The exact property names Gmail writes (`header.i=` versus `header.d=`) were not checked. `[memory]` **(unverified)**. Parse both.

### How ESPs show up, and how to see through them

- **Mailchimp.** If the `From:` domain is not authenticated, clients show "via mailchimpapp.net", "via mcsv.net" or "on behalf of". Mailchimp's sending addresses "usually" contain `mcsv.net`, `mcdlv.net`, `mailchimpapp.net` or `rsgsv.net`. Custom-domain authentication uses two CNAME records for DKIM and one TXT for DMARC. Mailchimp tells customers that Gmail and Yahoo require custom authentication above 5,000 messages a day. `[search]` https://mailchimp.com/help/my-campaign-from-name-shows-mcsvnet/ and https://mailchimp.com/help/about-email-authentication/
- **Twilio SendGrid.** Domain authentication "removes tagline via sendgrid.net (or via eu.sendgrid.net …) after the from address". It publishes DKIM under `s1._domainkey` and `s2._domainkey` CNAMEs and a return-path subdomain like `em1234.example.com`. `[search]` https://www.twilio.com/docs/sendgrid/ui/account-and-settings/how-to-set-up-domain-authentication
- **Amazon SES.** By default the `MAIL FROM` (so `Return-Path`) domain is `amazonses.com` or a subdomain; a custom MAIL FROM must be a subdomain of the verified identity. `[search]` https://docs.aws.amazon.com/ses/latest/dg/mail-from.html
- Every SES message also carries a DKIM signature with `d=amazonses.com`, added automatically, "required for complaint feedback loops". The customer's own signature (Easy DKIM or BYODKIM) is a second one. `[search]` https://docs.aws.amazon.com/ses/latest/dg/troubleshoot-dkim.html
- **Klaviyo.** "By default, the DKIM domain is one owned and operated by Klaviyo, such as klaviyomail.com." With a branded sending domain (for example `send.example.com`) mail is "DKIM-signed by your own domain in addition to a shared Klaviyo domain". With the shared domain, "Return-Path and DKIM domains do not align with your brand's From Address domain". `[search]` https://help.klaviyo.com/hc/en-us/articles/4402601857307 and https://help.klaviyo.com/hc/en-us/articles/15268721014811

What this means `[analysis]`:

1. The pattern is the same across ESPs: `Return-Path`, one DKIM signature and often `List-Id` belong to the ESP. A second DKIM signature and `From:` belong to the brand.
2. With several `DKIM-Signature` headers, pick the one whose `d=` shares a registrable domain with `From:`. Ignore the rest for identity.
3. Brands often send from a delegated subdomain (`send.example.com`, `em.example.com`, `news.example.com`). Reducing to the registrable domain folds these together. `eraser` does exactly this (`news.shop.co.uk` → `shop.co.uk`). `[read]` eraser README
4. The hard case is a `From:` address on a shared domain: small senders on an ESP's own domain, marketplaces, newsletter platforms, and "noreply@platform" mail sent for a third party. Here the registrable domain is the platform. Keep a list of such platform domains; for them, key on the `From:` display name plus the `List-Unsubscribe` or `List-Id` token, and mark the result "needs review". AccountSweep's spec takes the same route: "Sender domain → registrable domain via the PSL, then an alias table (e.g. `accounts.google.com` → Google; email-service relay domains → the brand from the display name)". `[read]` https://github.com/Iioneua/AccountSweep `SPEC.md`, commit b182bb7
5. Whether a platform is a GDPR controller in its own right or a processor for the brand differs per platform. The domain cannot tell. `[analysis]`
6. Specific ESP fingerprint headers (`X-SG-EID`, `X-Mailgun-Sid`, `X-MC-User`, a `Feedback-ID` ending in `:AmazonSES`) are widely seen but were not checked against vendor documentation. `[memory]` **(unverified)**

### Registrable domain and the Public Suffix List

- RFC 7489 defines the Organizational Domain by a public-suffix lookup: find the longest matching public suffix and keep one more label. "The process of determining a suffix is currently a heuristic one. No list is guaranteed to be accurate or current." It names the Mozilla list at publicsuffix.org as "the most common one". `[read]` RFC 7489 §3.2, Appendix A.6.1
- The PSL algorithm: match the domain against all rules; an exception rule (`!`) wins; otherwise the rule with the most labels wins; if nothing matches, the rule is `*`. "The registered or registrable domain is the public suffix plus one additional label." Domain and rules must be lower-cased and Punycode-encoded first. `[read]` https://github.com/publicsuffix/list `docs/format.md`, commit 88260fe
- The list has two sections. `ICANN` holds registry suffixes (`com`, `co.uk`). `PRIVATE` holds suffixes submitted by domain holders, for example `github.io`, `blogspot.com`, `herokuapp.com`, `myshopify.com`, `web.app`. "other applications may wish to treat ICANN domains and PRIVATE domains differently." `[read]` `docs/format.md` and `public_suffix_list.dat`, commit 88260fe
- Recommendation `[analysis]`: use both sections. With the PRIVATE section, `shop-a.myshopify.com` and `shop-b.myshopify.com` stay separate Organizations, which is what Unlist wants.
- Licence: MPL-2.0, file-level copyleft. Shipping the unmodified `.dat` file alongside AGPL-3.0 code is the normal way libraries use it. `[read]` `LICENSE`; `[analysis]` for compatibility.
- The PSL "does not assess whether a listed suffix, its operator, or the names registered under it are secure, reputable, or trustworthy". `[read]` `README.md`
- A hand-rolled suffix subset is the shortcut to avoid. `eraser` hardcodes 45 two-label suffixes and carries a comment to "swap in the `psl` crate if odd ccTLDs show up". `[read]` `src/scanner/domain.rs`
- DMARCbis was published as **RFC 9989**, "Domain-Based Message Authentication, Reporting, and Conformance (DMARC)", Standards Track, May 2026, "Obsoletes: 7489, 9091". `[read]` https://www.rfc-editor.org/rfc/rfc9989, read 2026-11-26. Its §4.10 "DNS Tree Walk" defines how the Organizational Domain is found: RFC 7489 "discussed using a Public Suffix List (PSL)" and "even suggested that if a more reliable and secure method for determining the Organizational Domain could be created, that method should replace reliance on a PSL"; RFC 9989 defines "a discovery technique known colloquially as the 'DNS Tree Walk'" instead of "just using a PSL". (The earlier note quoted that last sentence from draft-41 as if it were DMARCbis's own wording; it is RFC 9989's description of RFC 7489.) This does not affect Unlist: the tree walk needs live DNS and answers a different question. The PSL remains the right offline tool for grouping.

### Brand, domain and legal entity

- A GDPR controller is the "natural or legal person, public authority, agency or other body which, alone or jointly with others, determines the purposes and means of the processing of personal data". `[search]` GDPR Art. 4(7), https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex%3A32016R0679
- A domain is a brand asset. One legal entity runs many brands and domains, and one brand may be run by different entities per country. The Datenanfragen schema models this directly: `name` is "The company's official name, including suffixes like 'Ltd.', 'LLC', 'GmbH'", `runs` is "A list of other services and companies the parent company is responsible (as defined in Article 4(7) GDPR) for", `web` is the main website, and "If a company has branches in different countries with unique contact data, separate records should be created". `[read]` https://github.com/datenanfragen/data `schema.json`, commit b27fb25
- Example record: `zalando.json` has `name: "Zalando SE"`, `runs: ["Zalando Lounge (www.zalando-lounge.de)"]`, `web: "https://www.zalando.de/"`, `relevant-countries: ["de"]`. 957 of 3,069 records have a `runs` field. `[read]` same commit
- JustDeleteMe's `sites.json` has a `domains` array per service (2,671 services). `[read]` https://github.com/jdm-contrib/jdm `_data/sites.json`, commit b75bc14
- Neither list is keyed by sender domain. Matching needs `web` host → registrable domain, plus the `domains` arrays. `[analysis]`
- Same brand under different TLDs is ambiguous. `eraser` treats `zalando.de` and `zalando.ch` as related when the label before the suffix is equal and at least 4 characters long. `[read]` `src/scanner/domain.rs`. That heuristic merges unrelated companies that share a name; it should be a suggestion to the Operator, not an automatic merge. `[analysis]`
- When no list matches, the fallback is the Organization's own privacy page. `eraser`: "Privacy contacts are never guessed", it uses its database entry, "otherwise an address published on the company's own website (privacy policy, Datenschutz, confidentialité, … pages; Impressum as last resort) on the company's domain, with the page URL recorded as source". `[read]` eraser README
- Commercial email in the US must include the sender's "valid physical postal address". `[search]` https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business. EU and German rules requiring controller identity and an imprint (GDPR Art. 13(1)(a), e-Commerce Directive Art. 5 and 6, German DDG §5) were not confirmed in this session. `[memory]` **(unverified)**. Footers are therefore a plausible source of the legal entity, at the cost of reading bodies (table row 13).

## 3. Kinds of evidence and their strength

Unlist's glossary calls an Organization's record of a Subject a **Listing**. Mail cannot prove a Listing exists; only the answer to an Access Request does. Mail gives a prior. The grading below is `[analysis]` throughout.

| Evidence type | What it shows | Strength for "holds data about the Subject" | Typical headers | Detectable without LLM? |
|---|---|---|---|---|
| Order confirmation, receipt, invoice | A purchase: name, address, payment trail, legal retention duties | Very strong | Usually no `List-Unsubscribe`; role local-part | Yes: keywords, or schema.org `Order` / `Invoice` |
| Shipping and delivery notice | A postal address was processed, often by a carrier too | Very strong, and reveals a second Organization (the carrier) | Same | Yes: keywords, or `ParcelDelivery` |
| Booking or reservation | Travel or event data | Very strong | Same | Yes: keywords, or `*Reservation` |
| Welcome, registration | An account was created | Strong | Often no `List-Unsubscribe` | Yes: keywords |
| Email verification, confirm your address | A sign-up was started with this address. It may never have been completed, or someone else typed the address | Medium | No `List-Unsubscribe` | Yes: keywords |
| Password reset, sign-in alert, security notice | An account exists now, or someone tried the address | Strong for reset actually issued; medium for "someone tried" | No `List-Unsubscribe`; often `Auto-Submitted` | Yes: keywords |
| Account or billing notice (statement ready, renewal, payment failed) | An active customer relationship | Very strong | No `List-Unsubscribe` | Yes: keywords |
| Policy-update notice (terms, privacy policy) | The Organization itself believes it must inform the Subject | Strong, and the best proof that an old account still exists | Bulk-sent, may carry `List-Unsubscribe` | Yes: keywords |
| Newsletter, marketing | The Organization holds the address and a marketing profile | Medium. May be a bought or scraped list; a Broker indicator if never subscribed | `List-Unsubscribe`, `List-Id`, `Precedence: bulk` | Yes: headers alone |
| Cold outreach, one-off bulk | Address obtained somewhere | Weak for an account; relevant for Broker tracing | Mixed | Partly |
| Mailing-list discussion | The list operator holds the address | Medium, for the operator only | `List-Id`, `List-Post` | Yes |
| Personal correspondence | A person, not an Organization | None | None of the above | Yes, by exclusion |

Notes:

- A single verification or password-reset mail is weaker than it looks: anyone can type an address into a form. Grade by combination: verification followed by any later mail from the same Organization is strong. `[analysis]`
- Recency and span matter. "Last mail 2014" suggests a dormant account that may be gone or may be exactly the forgotten Listing the Operator wants removed. Report first-seen, last-seen and count rather than hiding old Organizations. `eraser` uses "inactive for 12+ months or only send newsletters" as its trigger for automatic deletion requests and keeps banks, insurers, government and employer on a keep list. `[read]` eraser README
- The recipient address is part of the evidence. It says which Subject and which alias the Organization knows, and the request should quote it. Datenanfragen records list per-company `required-elements`, "identification elements the user has to provide for requests". `[read]` `datenanfragen/data` `schema.json`. Order and customer numbers in subjects are useful identifiers for the same reason.
- Keyword rules need per-language packs (Bestellbestätigung, Rechnung, Votre commande, Factura …). AccountSweep ships its queries as "a data file contributors can extend" and maps `welcome`, `verify` → `account` and `receipt`, `subscription` → `subscription`. `[read]` AccountSweep `SPEC.md`. The same shape fits Unlist: rules as data, shareable like Organization Lists. `[analysis]`
- `unsubvault` sends "subject, sender, and the first 500 characters" of mail that has an unsubscribe header to a model and classifies each sender as "newsletter, promotional, receipt/account notice, personal, or spam". That is the LLM-first design; it leaves transactional-only senders (no unsubscribe header) undiscovered. `[read]` https://github.com/falknerj0823/unsubvault README, commit 604b2cc

### Structured markers

- Gmail's email markup uses schema.org data in **JSON-LD or Microdata**, and "You can add structured information anywhere inside the `<body>` element of the" email. `[read]` https://developers.google.com/workspace/gmail/markup/getting-started and https://developers.google.com/gmail/markup/reference, read 2026-11-26
- Supported types include `Order`, `ParcelDelivery`, `Invoice`, `FlightReservation`, `LodgingReservation` (hotel), and bus, train, rental-car, restaurant and event reservations. `[read]` https://developers.google.com/workspace/gmail/markup/overview and https://developers.google.com/gmail/markup/reference, read 2026-11-26
- To have Gmail process the markup for real recipients, senders must register with Google: send a marked-up email from production servers to a Google review address and fill in a form. You can test by sending to yourself. Registration guidelines: mail "must be authenticated using DKIM or SPF" with the domain matching the `From:` domain; a static sender address; "Consistent history of sending a high volume of mail from your domain (order of hundreds of emails a day minimum to Gmail) for at least a few weeks"; a very low spam-complaint rate. "Gmail removes all markup when forwarding an email." `[read]` https://developers.google.com/gmail/markup/registering-with-google, read 2026-11-26
- For Unlist `[analysis]`: a `<script type="application/ld+json">` block with `"@type": "Order"` (or the Microdata equivalent) is an unambiguous, language-independent transaction marker, and its `merchant` / `seller` / `provider` / `reservationFor` objects often carry the Organization's name. Parsing needs the `text/html` part only. Fetch it with `BODY.PEEK[<part>]` for candidate messages rather than for the whole mailbox.
- How many senders embed this markup is unknown. Registration requires a sending history of "hundreds of emails a day minimum to Gmail", which limits the markup to established senders and is consistent with `[memory]` **(unverified)**: common at large retailers, airlines and booking sites, rare elsewhere. Google's pages give no prevalence figure. Treat it as a high-precision, low-recall signal and measure on a real mailbox.
- **Gmail's own categories.** Gmail search has `category:primary|social|promotions|updates|forums|reservations|purchases`. With the default inbox type, "Updates" holds "Automated confirmations, notifications, statements, and reminders that may not need immediate attention", and "Archived emails don't appear in categories". "If you use inbox categories, find emails under one of the categories" (search help). `[read]` https://support.google.com/mail/answer/3094499 and https://support.google.com/mail/answer/7190, read 2026-11-26
- Takeout writes each message's labels to `X-Gmail-Labels` (below). Third-party reports show category labels in it, for example `Category Forums`. `[search]` https://support.mozilla.org/en-US/questions/1336844 (host not on the allowed list). Over IMAP the same search is reachable with `X-GM-RAW`: "Arguments passed with the X-GM-RAW attribute ... are interpreted in the same manner as in the Gmail web interface". `[read]` https://developers.google.com/workspace/gmail/imap/imap-extensions, read 2026-11-26. Google's IMAP page never mentions categories, so whether they appear in `X-GM-LABELS` stays unconfirmed. **(unverified; live test)**

## 4. Formats and access

### mbox

- "The mbox database format is not documented in an authoritative specification". RFC 4155 (Informational, September 2005) only registers `application/mbox` and defines a "default" format: each message is preceded by a separator line `From`, one space, the envelope sender address, one space, a UTC timestamp in ctime format, end of line; each message is terminated by an empty line; lines end with LF. `[read]` https://www.rfc-editor.org/rfc/rfc4155 §2, Appendix A
- The default format "does not prescribe any escape syntax for message body lines that begin with the character sequence of "From "". `[read]` RFC 4155 Appendix A
- RFC 4155 points to the qmail `mbox(5)` man page as "mostly authoritative". That page defines the four variants: `[read]` https://github.com/notqmail/notqmail `mbox.5`, commit b2b7a1f

  | Variant | Body lines starting `From ` | Reader | Notes |
  |---|---|---|---|
  | mboxo | Prefixed with `>` | Cannot tell whether `>From ` was original text | "The original mboxo format quotes only From_ lines, not >From_ lines." |
  | mboxrd | `From `, `>From `, `>>From ` … each get one more `>` | Strips one `>` reversibly | "popularized by Rahul Dhesi in June 1995" |
  | mboxcl | Quoted as mboxo, plus a `Content-Length` header | May use the length | "used by SVR4 mailers" |
  | mboxcl2 | **Not quoted**; relies on `Content-Length` only | Must trust the length | "cannot be read safely by mboxrd readers" |

- A reader "should not attempt to take advantage of the fact that every From_ line (past the beginning of the file) is preceded by a blank line". `[read]` `mbox.5`
- Python's standard `mailbox.mbox` implements mboxo: `Content-Length` "is ignored", `From ` is quoted on write, and `>From ` is **not** unquoted on read. `[read]` https://github.com/python/cpython/blob/main/Doc/library/mailbox.rst
- For header-only discovery `[analysis]`: quoting affects body lines, never headers. The only variant risk is splitting a message in two at a body line that starts with `From ` (mboxcl2, or a non-quoting writer). Mitigate by accepting a separator only if it matches the full `From <addr> <timestamp>` shape and the next line looks like a header. A body-parsing step (schema.org) should unquote the mboxrd way.

### Google Takeout

- "When you export your mail from Gmail, each message's labels are preserved in a special X-Gmail-Labels header in your download file." `[read]` https://support.google.com/accounts/answer/3024190, read 2026-11-26. That page (and the Gmail data-export pages that could be read) does **not** name the mbox format, so "Takeout writes Gmail as mbox" rests on other sources (search excerpts and the third-party reports below). `[search]`
- The same page says Takeout does not support timeframe exports for Gmail ("we don't support timeframe exports") and that the archive contains an `archive_browser.html` describing the file formats. `[read]` same page. The export can be limited to chosen labels. `[search]` https://support.google.com/mail/thread/27077156
- Third-party reports: the value is a comma-separated label list, for example `X-Gmail-Labels: Important,Trash,Opened,Category Forums`, and an `X-GM-THRID` header is also present. `[search]` https://support.mozilla.org/en-US/questions/1336844. `X-GM-THRID` is documented by Google as an **IMAP** fetch attribute (a 64-bit thread id); no Google page says it is written into Takeout files. `[read]` https://developers.google.com/workspace/gmail/imap/imap-extensions, read 2026-11-26
- Which mbox variant Takeout writes, whether it emits one file or several, and the exact shape of its `From ` line were not confirmed. `[memory]` **(unverified; needs a real Takeout export)**: a single `All mail Including Spam and Trash.mbox` when all mail is selected, with `>From ` quoting.
- Consequences `[analysis]`:
  - The file holds full messages, so body signals cost nothing extra, but it can be many gigabytes. Parse as a stream, never load it whole.
  - Spam and Trash are included. Filter on `X-Gmail-Labels` (`Spam`, `Trash`) before counting evidence.
  - Sent mail is included. Use it to learn the Subject's own addresses and whom the Subject writes to.
  - It is a snapshot with no incremental mode. Deduplicate on `Message-ID` when a later export or an IMAP scan covers the same mail.
  - It needs no credentials and no OAuth client, which makes it the lowest-friction path for Gmail.

### IMAP for cheap scanning

- **Read-only.** `EXAMINE` "is identical to SELECT and returns the same output; however, the selected mailbox is identified as read-only. No changes to the permanent state of the mailbox, including per-user state, are permitted". The tagged OK begins with `[READ-ONLY]`. `[read]` https://www.rfc-editor.org/rfc/rfc3501 §6.3.2 (same in RFC 9051 §6.3.3)
- **Headers only, no `\Seen`.** `BODY.PEEK[<section>]` is "An alternate form of BODY[<section>] that does not implicitly set the \Seen flag." `HEADER.FIELDS (…)` returns "only those header fields with a field-name that matches one of the names in the list", matched case-insensitively. `[read]` RFC 3501 §6.4.5
- A suitable fetch `[analysis]`:

  ```
  UID FETCH <last+1>:* (UID INTERNALDATE RFC822.SIZE
    BODY.PEEK[HEADER.FIELDS (FROM SENDER REPLY-TO TO DELIVERED-TO DATE SUBJECT
      MESSAGE-ID IN-REPLY-TO LIST-ID LIST-UNSUBSCRIBE LIST-UNSUBSCRIBE-POST
      PRECEDENCE AUTO-SUBMITTED X-AUTO-RESPONSE-SUPPRESS FEEDBACK-ID
      RETURN-PATH DKIM-SIGNATURE AUTHENTICATION-RESULTS)])
  ```
  `eraser` fetches a shorter list (`FROM REPLY-TO LIST-UNSUBSCRIBE LIST-UNSUBSCRIBE-POST LIST-ID PRECEDENCE AUTO-SUBMITTED DATE MESSAGE-ID`) after `EXAMINE`, in batches, so it has no authentication data. `[read]` eraser README
- **Server-side pre-filter.** `SEARCH HEADER <field> ""`: "If the string to search is zero-length, this matches all messages that have a header line with the specified field-name regardless of the contents." So `UID SEARCH HEADER List-Unsubscribe ""` lists bulk mail without fetching anything. `[read]` RFC 3501 §6.4.4
- **Incremental scans without extensions.** UIDs "are assigned in a strictly ascending fashion in the mailbox; as each message is added to the mailbox it is assigned a higher UID". If UIDs do not persist, `UIDVALIDITY` "MUST be greater than the one used in the earlier session". `[read]` RFC 3501 §2.3.1.1. Store `(folder, UIDVALIDITY, highest UID)`; next time fetch `highest+1:*`; if `UIDVALIDITY` changed, rescan that folder and deduplicate on `Message-ID`. `eraser` keys on `Message-ID`, falling back to `folder/uidvalidity/uid`. `[read]` `src/scanner/headers.rs`
- **CONDSTORE and QRESYNC (RFC 7162).** CONDSTORE attaches a mod-sequence to each message, "updated whenever metadata (such as a message flag) is modified", and "gives a disconnected client the ability to quickly resynchronize IMAP flag changes for previously seen messages" through `FETCH … (CHANGEDSINCE <modseq>)`. To learn about expunges "the client still has to issue a UID FETCH or a UID SEARCH". QRESYNC adds "discovery of expunged messages, in a single round trip" through the `VANISHED` response. `[read]` https://www.rfc-editor.org/rfc/rfc7162 §1, §3.1, §3.2
- For discovery these are optional `[analysis]`. Headers of a delivered message never change, so new mail is found by UID alone. CONDSTORE helps only if Unlist wants flag state (read, answered). QRESYNC helps only if Unlist wants to notice deletions. Check `CAPABILITY` at runtime and degrade to the UID method.
- **Scan each message once.** Gmail exposes labels as folders ("Gmail treats labels as folders for the purposes of IMAP"), so the same message appears in several. `X-GM-MSGID` is "a unique message ID for each email so that you can identify a unique message across multiple folders" (64-bit); `X-GM-THRID` is the thread id; `X-GM-LABELS` returns a message's labels; `X-GM-RAW` runs Gmail search syntax. Support is advertised as `X-GM-EXT-1` in `CAPABILITY`. `[read]` https://developers.google.com/workspace/gmail/imap/imap-extensions, read 2026-11-26. The page lists special-use attributes for Starred, Important, Sent, Drafts, Spam, All Mail and Trash. RFC 6154 defines the `\All` special-use attribute for an all-messages mailbox. `[read]` https://www.rfc-editor.org/rfc/rfc6154 §2. On Gmail, scan the `\All` folder and skip `\Junk` and `\Trash`.
- Whether Gmail's IMAP server supports CONDSTORE or QRESYNC is **not documented** on the developer pages: neither word appears on the IMAP extensions, XOAUTH2 or IMAP overview pages, and Google's sample `CAPABILITY` line (`IMAP4rev1 UNSELECT LITERAL+ IDLE NAMESPACE QUOTA ID XLIST CHILDREN X-GM-EXT-1`) lists neither. `[read]` https://developers.google.com/workspace/gmail/imap/imap-extensions, read 2026-11-26. A sample line is not proof of absence. **(unverified; live `CAPABILITY` test)**
- **OAuth over IMAP.** The standard SASL mechanism is `OAUTHBEARER` (RFC 7628). `[read]` https://www.rfc-editor.org/rfc/rfc7628. Google and Microsoft both document `XOAUTH2`: `AUTHENTICATE XOAUTH2 <base64("user=" user ^A "auth=Bearer " token ^A ^A)>`, advertised as `AUTH=XOAUTH2` in `CAPABILITY`. `[read]` https://developers.google.com/workspace/gmail/imap/xoauth2-protocol and https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth, read 2026-11-26

### What each provider allows today

| Account | Password only | App password | OAuth 2.0 over IMAP | Other gates |
|---|---|---|---|---|
| **Gmail, personal** (`@gmail.com`) | No: Gmail "no longer supports third-party apps or devices which require you to share your Google username and password" (no end date on any page read) | **Yes**, if 2-Step Verification is on. Google says app passwords "aren't recommended". Option missing when 2SV is security-keys-only, for "a work, school, or another organization account", or with Advanced Protection | **Yes**, scope `https://mail.google.com/` (a restricted scope) | IMAP on/off setting removed from January 2025: "IMAP access is always turned on in Gmail" |
| **Google Workspace** (work, school) | No. Google's readable page: "Starting January 2025 ... will no longer be supported for Google Workspace accounts. For exact dates, visit Google Workspace Updates". "1 May 2025" is a search excerpt only | **Unconfirmed.** Google's app-password page lists "a work, school, or another organization account" among the reasons the option can be missing; a search excerpt of the admin page says app passwords remain possible for clients without OAuth. The admin page was unreadable | **Yes**, unless the admin blocks or restricts third-party app access or IMAP `[search]` | Admin can turn IMAP off, or allow only listed OAuth client IDs `[search]` |
| **Outlook.com, Hotmail, Live** (personal Microsoft account) | No. Basic Authentication ended 16 September 2024 | **Contradictory on Microsoft's own pages; treat as not working for IMAP until tested** (see below) | **Yes**, scope `https://outlook.office.com/IMAP.AccessAsUser.All` + `offline_access` | POP/IMAP is off by default and must be enabled in Outlook.com settings |
| **Microsoft 365 / Exchange Online** (work, school) | **IMAP:** no. Basic auth is disabled in all tenants and cannot be re-enabled. **SMTP AUTH:** Basic is still available (page updated 2026-09-16); retirement announced, timeline on a blocked page | **No** for IMAP: Microsoft says the deprecation "prevents the use of app passwords with apps that don't support two-step verification" | **Yes**: delegated (auth code or device code) or app-only (client credentials, admin-registered service principal) | App-only needs tenant admin consent. Delegated consent for `IMAP.AccessAsUser.All` is not stated on any page read; it follows the tenant's user-consent setting. Admins can disable IMAP per mailbox |

Sources, row by row:

- **Gmail personal.**
  - "To keep your account more secure, Gmail no longer supports third-party apps or devices which require you to share your Google username and password." "Starting January 2025, the option to choose "Enable IMAP" or "Disable IMAP" won't be available. IMAP access is always turned on in Gmail, and your current connections to other email clients aren't affected." (The earlier note quoted this as "IMAP access is always enabled over OAuth"; that wording is not on the page.) The troubleshooting section still suggests: "Use an app password. If you use 2-Step Verification, try signing in with an app password", with the warning "App passwords aren't recommended and are unnecessary in most cases". `[read]` https://support.google.com/mail/answer/7126229, read 2026-11-26
  - "App passwords can only be used with accounts that have 2-Step Verification turned on." The option is missing if 2SV is "set up only for security keys", if "You're logged into a work, school, or another organization account", or if the account has Advanced Protection. Google says app passwords "aren't recommended", and revokes them when the Google Account password is changed. `[read]` https://support.google.com/accounts/answer/185833, read 2026-11-26
  - The date Google ended password-only access for personal accounts is on no page read. The "Less secure apps" page (https://support.google.com/accounts/answer/6010255) now speaks only about Workspace. The earlier "30 May 2022" is `[memory]` **(unverified)**.
  - "The scope for IMAP, POP, and SMTP access is `https://mail.google.com/`"; it must show "full utilization" of that scope or "migrate to the Gmail API and use more granular restricted scopes". `[read]` https://developers.google.com/workspace/gmail/imap/xoauth2-protocol, read 2026-11-26. Restricted-scope apps need a security assessment: "In general, the security assessment must be done once a year" (CASA, no fee charged by Google). `[read]` https://support.google.com/cloud/answer/13463817, read 2026-11-26
- **Google Workspace.**
  - "Starting January 2025, less secure apps, third-party apps, or devices that have you sign in with only your username and password will no longer be supported for Google Workspace accounts. For exact dates, visit Google Workspace Updates." `[read]` https://support.google.com/accounts/answer/6010255, read 2026-11-26. The "1 May 2025" date, "CalDAV, CardDAV, IMAP, SMTP and POP stop working with passwords" and "must use OAuth, or use 2-Step Verification with an app password for email clients that don't support OAuth" come from a search excerpt of https://support.google.com/a/answer/14114704 `[search]`. That URL now answers 301 to knowledge.workspace.google.com, which is not on the allowed list, so it was not read. The wind-down blog (workspaceupdates.googleblog.com) is also blocked.
  - Enforcing security keys for 2SV disables app passwords. `[search]` https://support.google.com/a/answer/9176599 (redirects to knowledge.workspace.google.com, unread)
  - Admin IMAP setting: off, "Allow any mail client", or "Restrict which mail clients users can use (OAuth mail clients only)" with a list of OAuth client IDs. `[search]` https://support.google.com/a/answer/105694 (redirects to knowledge.workspace.google.com, unread)
  - Admins can restrict Gmail scopes (including `mail.google.com`) to trusted apps and block unconfigured third-party apps. `[search]` https://support.google.com/a/answer/7281227 (redirects to knowledge.workspace.google.com, unread)
  - Google's IMAP page also documents `https://www.googleapis.com/auth/gmail.imap_admin` for Workspace domain-wide delegation with a service account. `[read]` https://developers.google.com/workspace/gmail/imap/xoauth2-protocol, read 2026-11-26
- **Outlook.com.**
  - Microsoft's timeline (last updated June 10, 2024): "September 16th, 2024: Basic Authentication no longer available to access any Outlook account"; "After September 16th, users attempting to connect their Microsoft accounts through Basic Authentication will fail to do so". `[read]` https://support.microsoft.com/en-us/office/modern-authentication-methods-now-needed-to-continue-syncing-outlook-email-in-non-microsoft-email-apps-c5d65390-9676-4763-b41f-d7986499a90d, read 2026-11-26
  - Server `outlook.office365.com`, IMAP port 993 (POP 995), SSL/TLS; SMTP `smtp-mail.outlook.com`, port 587, STARTTLS; authentication method listed for all three: "OAuth2/Modern Auth". "POP & IMAP access is disabled by default." "Outlook.com requires the use of Modern Auth / OAuth2." **Contradiction on the same page:** the Password row says "Your Microsoft account password. If your password is not being recognized, or if you want to add your Outlook.com account to a smart device like a home security camera, you may need an app password." `[read]` https://support.microsoft.com/en-us/outlook/pop-imap-and-smtp-settings-for-outlook-com, read 2026-11-26. The linked article "Add your Outlook.com account to another mail app or smart device" does not mention app passwords, and the separate "How to get and use app passwords" article (applies to Microsoft account) describes app passwords for "devices that don't support two-step verification" without naming IMAP, POP or SMTP. `[read]` https://support.microsoft.com/en-us/outlook/add-your-outlook-com-account-to-another-mail-app-or-smart-device and https://support.microsoft.com/en-us/accounts-billing/manage/how-to-get-and-use-app-passwords, read 2026-11-26. No page read says whether an app password works for IMAP login. Treat as not working until tested. **(unverified; live test)**
  - "OAuth2 support for IMAP, POP, and SMTP protocols as described below is available for both Microsoft 365 (which includes Office on the web) and Outlook.com users." Scopes: `https://outlook.office.com/IMAP.AccessAsUser.All`, `POP.AccessAsUser.All`, `SMTP.Send`, plus `offline_access` for refresh tokens. `[read]` https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth, read 2026-11-26 (earlier read from the Microsoft doc source, commit 1deccef)
- **Microsoft 365.**
  - IMAP: "Basic authentication is now disabled in all tenants." "Now no one (you or Microsoft support) can re-enable Basic authentication in your tenant." "We removed the ability to use Basic authentication in Exchange Online for Exchange ActiveSync (EAS), POP, IMAP, ..." The October 1, 2022 date applies to all clouds except Office 365 operated by 21Vianet (March 31, 2023); tenants could re-enable only until December 31, 2022. "The deprecation of basic authentication also prevents the use of app passwords with apps that don't support two-step verification." Developers must "implement secure, Modern authentication experiences". `[read]` https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online, read 2026-11-26
  - SMTP AUTH is **different**: "We also disabled SMTP AUTH in all tenants where it wasn't being used." "Although SMTP AUTH is currently available, Microsoft has announced plans to retire Basic authentication for SMTP AUTH in Exchange Online." The page points to a techcommunity post for the timeline (blocked, so the date is not known here). `[read]` same page. "SMTP AUTH supports modern authentication (Modern Auth) through OAuth in addition to basic authentication"; SMTP AUTH can be switched off per organization and per mailbox; if security defaults is enabled, SMTP AUTH is already disabled. `[read]` https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/authenticated-client-smtp-submission, page last updated 2026-09-16, read 2026-11-26
  - Client-credentials access: "your Entra application must get tenant admin consent for each tenant", with `IMAP.AccessAsApp` / `POP.AccessAsApp` / `SMTP.SendAsApp` application permissions and a service principal registered in Exchange Online (`New-ServicePrincipal`). `[read]` the OAuth page above, read 2026-11-26
  - Delegated flow (`IMAP.AccessAsUser.All`): the OAuth page says nothing about admin consent for it. Entra: "By default, all users are allowed to consent to applications for permissions that don't require administrator consent", and admins can disable or limit user consent. Whether this particular scope is flagged as needing admin consent is **not stated** on any page read. `[read]` https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent, read 2026-11-26. **(unverified; live test with user consent disabled)**
  - Per-mailbox IMAP: "Support for Outlook on the web and MAPI, POP3, and IMAP4 email clients is enabled by default when a user mailbox is created", and an admin can set IMAP to Disabled per mailbox in the Exchange admin center or with `Set-CASMailbox`. `[read]` https://learn.microsoft.com/en-us/Exchange/recipients-in-exchange-online/manage-user-mailboxes/managing-email-apps-for-user-mailboxes, read 2026-11-26

### The OAuth client problem for a self-hosted tool

- OAuth needs a registered client. A self-hosted AGPL tool cannot ship a secret, and a shared public client for Gmail means Google's restricted-scope verification and a security assessment "once a year". `[read]` https://support.google.com/cloud/answer/13463817, read 2026-11-26
- PrivacyBot (UC Berkeley) is the cautionary case: "As of 9.28.21 this project has been depreciated and Google Oauth verification is not supported. You can still run the tool but you need to setup your own instance of Google Oauth credentials." `[read]` https://github.com/privacybot-berkeley/privacybot README, commit 62e89b7
- Operator-registered Google client, External + **Testing**: at most 100 test users, and "Authorizations by a test user will expire seven days from the time of consent", refresh tokens included (exception only for apps requesting just `openid`, email and profile). `[read]` https://support.google.com/cloud/answer/15549945 and https://developers.google.com/identity/protocols/oauth2, read 2026-11-26
- External + **In production**, unverified: apps for a "limited audience (fewer than 100 users)" may skip verification; users click through the "unverified app" warning; the cap is "100 new users in total", over the project's lifetime, and is removed only after verification. `[read]` https://support.google.com/cloud/answer/13464323 and https://support.google.com/cloud/answer/15549945, read 2026-11-26
- Google **does** document a **Personal mode**: "Projects configured with a user type of Personal limit authorization requests exclusively to the single Google Account that created the application." Personal mode apps "do not require OAuth app verification, are not subject to the OAuth user cap or 7-day test user token expiration, and do not display the unverified app screen". It is a one-time choice that cannot be changed to External or Internal, and other accounts get a `client_user_mismatch` error. If the account belongs to a Workspace organisation, restricted scopes "might still require configuration by your organization's administrators". This suits a one-Operator instance. `[read]` https://support.google.com/cloud/answer/15549945 and https://support.google.com/cloud/answer/13464323, read 2026-11-26
- Workspace-internal clients "will not be subject to the unverified app screen or the 100-user cap", but only users of that organisation can use them. `[read]` https://support.google.com/cloud/answer/13464323, read 2026-11-26
- Microsoft: register an Entra app that allows personal accounts and/or organisational accounts. For personal Outlook accounts, `email-oauth2-proxy` notes that you need "the Microsoft 365 Developer Programme or … an Azure account (including free accounts)" to create a registration, or else must reuse an existing client ID. Yahoo and AOL "are not currently allowing new client registrations with the OAuth email scope". `[read]` https://github.com/simonrob/email-oauth2-proxy README, commit fac1ffb
- **Gmail API as an alternative.** The `gmail.metadata` scope gives "message metadata such as labels and headers, but not the email body", which matches a headers-only scan and is enforced by Google. But the `q` search parameter "cannot be used when accessing the api using the gmail.metadata scope", and `gmail.metadata` is itself listed under "Restricted scopes". `[read]` https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list and https://developers.google.com/workspace/gmail/api/auth/scopes, read 2026-11-26. `dataclean` and AccountSweep's advanced mode both choose this scope. `[read]` their READMEs
- Ordering of options for Unlist `[analysis]`: (1) Takeout mbox import, no credentials; (2) IMAP with an app password where the provider still offers one (personal Gmail with 2-Step Verification is documented above; iCloud, Fastmail and most independent hosts are `[memory]`, not checked, and Outlook.com, Microsoft 365 and Workspace should not be assumed); (3) OAuth with an Operator-registered client, documented step by step, with Personal mode for a single-Operator Gmail setup and `email-oauth2-proxy` as a drop-in for those who already run it; (4) never a project-owned shared client.

## 5. Prior art

All repositories were cloned and read on 2026-11-26. "Licence" is what the repository states; a missing licence file is noted because it leaves reuse unclear.

### Mailbox scanners that discover Organizations

| Project | Approach | Licence | State | Lesson for Unlist |
|---|---|---|---|---|
| [tmaeder/eraser](https://github.com/tmaeder/eraser) (35bd73a, 2026-11-10) | Rust. IMAP `EXAMINE` + `BODY.PEEK[HEADER.FIELDS …]`, groups `From:` by registrable domain, excludes freemail domains and the user's own, finds privacy contacts from its broker database or the company's privacy page, sends GDPR / FADP / CCPA requests over SMTP, does RFC 8058 one-click and `mailto:` unsubscribes, tracks replies. Its broker database includes 500+ European and Swiss entries imported from `datenanfragen/data` | README says "MIT"; **no LICENSE file** | Active | The closest existing tool. Reuse its ideas: headers-only scan, never guess contacts, keep list, dry run, per-provider send pacing. Its gaps: no DMARC/DKIM check (spoofed mail becomes a "company"), hardcoded suffix list, no evidence grading beyond list / not list, no mbox import |
| [Iioneua/AccountSweep](https://github.com/Iioneua/AccountSweep) (b182bb7, 2026-11-21) | Rust tool plus an agent skill. Fixed Gmail "query pack" for sign-ups, resets, receipts, security alerts; reads sender, subject, date only; PSL + alias table; breach check against HIBP; revokes sessions in a browser | MIT OR Apache-2.0 | Pre-alpha: "Nothing is usable yet" | Query pack and alias table as contributor-editable data files; confidence + reason codes per grouping; `gmail.metadata` for a provable headers-only scan. Its SPEC is a good checklist |
| [zoubaiba/dataclean](https://github.com/zoubaiba/dataclean) (cb7ca6e, 2026-11-18) | Flask. Intends Gmail API with `gmail.metadata`, reading `From`, `Date`, `List-Unsubscribe`, to produce Art. 17 requests | None stated | Stub: the scan function returns hardcoded sample data | Nothing to reuse. Confirms the `gmail.metadata` idea is in the air |
| [falknerj0823/unsubvault](https://github.com/falknerj0823/unsubvault) (604b2cc, 2026-10-28) | Python + Postgres. Read-only scan of mail with an unsubscribe header; sends subject, sender and first 500 characters to a chosen (possibly local) model; classifies senders; "Verify a sender" uses the provider's signature check, domain age (RDAP) and DNS policy; broker opt-out checklist | MIT | Pre-alpha | Sender verification with provider `Authentication-Results` plus RDAP age is worth copying. LLM-first classification is what Unlist wants to avoid as a requirement |
| [privacybot-berkeley/privacybot](https://github.com/privacybot-berkeley/privacybot) (62e89b7, 2021-10-01) | Flask + React. Gmail OAuth; sends CCPA deletion emails to a fixed broker list | None stated | Abandoned in 2021 over Google OAuth verification | Do not depend on a project-owned Google OAuth client |
| [victorfiji/gdprhelper](https://github.com/victorfiji/gdprhelper) (706d5c5, 2020-03-13) | Python script that emails GDPR requests to a given address; no discovery | None stated | Dead; relied on Gmail "less secure apps" | None |

Mine / SayMine, Unroll.me and Deseat.me are closed-source and were not examined. `[memory]`

### Bulk-unsubscribe tools

| Project | Approach | Licence | Lesson |
|---|---|---|---|
| [schellevis/bulk-unsubscribe](https://github.com/schellevis/bulk-unsubscribe) (c7d82e6) | Python web app. IMAP or Fastmail JMAP; scans for `List-Unsubscribe`; groups by `List-ID`, fallback `From:`; one-click POST, HTTP link or `mailto:` with explicit confirmation; "only posts to HTTPS URLs whose host resolves to public IP addresses" | None stated; self-described as LLM-drafted, personal use | SSRF guard on one-click POST targets is necessary in a self-hosted server. `List-Id` as subscription key |
| [danthegoodman1/BulkUnsubscribe](https://github.com/danthegoodman1/BulkUnsubscribe) (775706f, 2024) | TypeScript, Gmail API, hosted service with self-host option | None stated | Shows the hosted-OAuth route and its verification burden |
| [elie222/inbox-zero](https://github.com/elie222/inbox-zero) (2784eff) | Large AI email assistant; Gmail and Outlook APIs; bulk unsubscribe among many features | AGPL-3.0 **plus additional terms** restricting commercial use and use by organisations of 5+ | The added terms make it not plainly AGPL; do not copy code without legal review `[analysis]` |
| [planetaryescape/list-unsubscribe](https://github.com/planetaryescape/list-unsubscribe) (edf6c3a) | Rust crate: parses RFC 2369 + RFC 8058 headers into `OneClick` / `Mailto` / `HttpLink` | MIT OR Apache-2.0 | Directly reusable if Unlist is written in Rust; otherwise a compact reference for the parse rules |

### The OAuth problem

- [simonrob/email-oauth2-proxy](https://github.com/simonrob/email-oauth2-proxy) (fac1ffb, 2026-11-19), **Apache-2.0**. A local proxy that "intercepts the traditional IMAP/POP/SMTP authentication commands and transparently replaces them with the appropriate SASL (X)OAuth 2.0 commands and credentials". Supports auth-code, device-code, client-credentials and ROPC flows, and headless operation once tokens are cached. `[read]` README
- It ships no client credentials: "you will need to insert your own client credentials for each one". It documents reusing the client ID of an existing open-source mail client, "with care and restraint as access through reused tokens will be associated with the token owner rather than your own client". `[read]` README
- What Unlist can take `[analysis]`: (a) recommend it as an optional sidecar, so Unlist itself can speak plain IMAP `LOGIN` to `localhost`; (b) its `emailproxy.config` as a table of per-provider authorisation URLs, token URLs and scopes; (c) Apache-2.0 code may be included in an AGPL-3.0 work. Reusing another client's ID is a terms-of-service risk Unlist should not automate.

### GDPR request tooling and data

- **Datenanfragen.de** (datarequests.org). `datenanfragen/data` is **CC0 1.0**: 3,069 company records with `name`, `runs`, `web`, `email`, `address`, `required-elements`, `suggested-transport-medium`, `relevant-countries`, plus supervisory authorities and request templates. `[read]` commit b27fb25. The website and letter generator are MIT. `[read]` https://github.com/datenanfragen/website (92dc2c6), https://github.com/datenanfragen/letter-generator
- Datenanfragen has no mailbox discovery. Its app's IMAP feature is "Import requests from email folder", for tracking answers to requests already sent. `[read]` `components-package/src/App/i18n/en.json`, commit 92dc2c6
- **YourDigitalRights.org**, GPL-3.0. Sends GDPR and CCPA erasure requests from a web form; the user picks the organization by domain. No mailbox scan. `[read]` https://github.com/your-digital-rights/yourdigitalrights.org (cloned via `opt-out-eu/opt-out`), commit 16e6159
- **JustDeleteMe**, MIT. 2,671 services with deletion URLs, difficulty and a `domains` array. Useful for domain → service matching and as an alternative action when an account can be self-deleted. `[read]` commit b75bc14
- **Data Rights Protocol** (Consumer Reports), Apache-2.0. A machine-to-machine protocol for rights requests, US-centric. Relevant later as a transport, not for discovery. `[read]` https://github.com/consumer-reports-innovation-lab/data-rights-protocol, commit ca1f837
- See `docs/research/organization-lists.md` for the licence analysis of these datasets.

### What is missing everywhere

`[analysis]` No project found does all of the following, which is the space Unlist would occupy:

1. Organization identity from the **authenticated** `From:` domain, with ESP and platform domains recognised.
2. Evidence graded by type (transaction, account, policy notice, marketing), with schema.org markup as the high-precision path.
3. mbox / Takeout import alongside IMAP.
4. Domain → legal entity through subscribable Organization Lists rather than a built-in database.
5. Working well with no LLM, and treating one as an optional refinement.

## Not verified

State after the 2026-11-26 verification pass. The full per-claim record is in the [Verification log](#verification-log).

**Hosts that could not be read.** support.google.com/a/answer/14114704, /105694, /9176599 and /7281227 (Workspace admin pages) answer 301 to knowledge.workspace.google.com, which the proxy refuses (403), so they were not read. Never reachable: workspaceupdates.googleblog.com, techcommunity.microsoft.com, mailchimp.com, twilio.com, docs.aws.amazon.com, help.klaviyo.com, ftc.gov, eur-lex.europa.eu, support.mozilla.org. datatracker.ietf.org was not fetched (the RFC Editor pages and texts sufficed). Everything still tagged `[search]` rests on search-engine excerpts of those pages.

**Specific open points.**

1. ~~RFC 9477 and RFC 9989~~ **Resolved:** both exist and were read. RFC 9477 is Experimental (Independent Submission, September 2023); RFC 9989 is Standards Track (May 2026) and obsoletes RFC 7489 and RFC 9091. RFC 7489 is also listed as obsoleted by RFC 9990 and 9991. RFC 9989 was read for its status and §4.10, not clause by clause against RFC 7489's alignment text.
2. Whether Gmail's IMAP server supports CONDSTORE or QRESYNC: not documented on any developer page, and the sample `CAPABILITY` line lists neither. **Live `CAPABILITY` test needed.**
3. Takeout specifics: that it writes mbox at all (no Google page read says so), the mbox variant, one file or several, the `From ` separator format, and whether `X-GM-THRID` appears in Takeout files (it is documented only as an IMAP attribute). **Needs a real Takeout export.**
4. Whether Gmail categories appear in IMAP `X-GM-LABELS`, and the label strings Takeout uses for them. **Live test.**
5. Property names in Gmail's `Authentication-Results` (`header.i` versus `header.d`; RFC 8601 examples use both) and the `authserv-id` values of the major providers. **Live test on real headers.**
6. Outlook.com app passwords for IMAP: Microsoft's pages contradict each other (see the provider table). **Live test with a real Outlook.com account.**
7. Outlook.com sender rules: threshold and requirements confirmed; the exact enforcement date ("May 2025") and the "unsubscribe is a recommendation" statement remain `[search]` (techcommunity.microsoft.com blocked). November 2026 forum reports of rejections of small senders were not checked.
8. ~~Yahoo's February 2024 start date~~ **Resolved:** confirmed on senders.yahooinc.com.
9. The date Google ended password-only sign-in for personal Gmail accounts (30 May 2022 from `[memory]`): on no readable page.
10. ~~Google "Personal mode"~~ **Resolved:** exists and is documented (support.google.com/cloud/answer/15549945 and 13464323).
11. Microsoft 365: whether `IMAP.AccessAsUser.All` needs admin consent by default is not stated on any page read (**live test**). Per-mailbox IMAP disablement is **resolved** (documented). New: the SMTP AUTH Basic-auth retirement date (on a blocked techcommunity page).
12. ESP specifics beyond the excerpts: SendGrid's default return-path without domain authentication, ESP fingerprint headers (`X-SG-EID`, `X-Mailgun-Sid`, `X-MC-User`, `Feedback-ID: ...:AmazonSES`), and typical `List-Id` values at Mailchimp. Hosts blocked.
13. How common schema.org email markup is in real mailboxes. Google's registration rules (hundreds of messages a day to Gmail for weeks) limit it to established senders but give no figure; measure it on a real mailbox before building on it.
14. GDPR Art. 13(1)(a), e-Commerce Directive Art. 5 and 6, and German DDG §5 wording on sender and controller identification. Only GDPR Art. 4(7) and the US CAN-SPAM postal-address rule were seen in search excerpts. Hosts blocked.
15. `tmaeder/eraser` licence: the README says MIT, but the repository has no LICENSE file and no `license` field in `Cargo.toml`. Ask the author before reusing code.
16. Mine / SayMine, Unroll.me and Deseat.me were not examined; they are closed-source.
17. None of the heuristics in this note (keyword rules, the bulk / transactional / personal split, evidence grades) was tested on real mail. They are design proposals.
18. New: Google Workspace. Whether app passwords still work for Workspace accounts, and the exact date password-only access ended (Google's readable page says "Starting January 2025"; "1 May 2025" is a search excerpt). Admin settings (IMAP restriction, OAuth client allow-list, security-key enforcement) are `[search]` only. **A Workspace test account is needed.**
19. New: app-password availability at iCloud, Fastmail and other independent hosts, and Yahoo / AOL OAuth registration being closed (from the `email-oauth2-proxy` README): not checked against provider pages.

## Verification log

Second pass, 2026-11-26, using www.rfc-editor.org, support.google.com, developers.google.com, learn.microsoft.com, support.microsoft.com and senders.yahooinc.com. Pages were saved and read as text; every cited quote below was matched against the saved text. A page that redirected to a host outside the allowed list was recorded as unreadable and not routed around.

### Corrected

| # | Section | Said before | Says now | Source |
|---|---|---|---|---|
| C1 | Answer 3; bulk-sender rules | Gmail and Yahoo both apply to senders of "about 5,000+ messages a day" | Gmail: 5,000+/day. Yahoo publishes **no threshold**: "We will not specify a volume threshold" | https://senders.yahooinc.com/faqs/ |
| C2 | Answer 3; signal row 3 | Gmail and Yahoo require `List-Unsubscribe-Post` (RFC 8058) | Gmail requires RFC 8058 one-click (`mailto:` does not count). Yahoo requires a one-click-capable header, RFC 8058 POST "highly recommended", `mailto:` "acceptable" | https://support.google.com/a/answer/14229414, https://senders.yahooinc.com/best-practices/ |
| C3 | Feedback-ID / RFC 9477 | RFC 9477 (2023) "status and details not confirmed" | Experimental, Independent Submission, September 2023, "Complaint Feedback Loop Address Header"; both headers must be in a valid DKIM signature's `h=` | https://www.rfc-editor.org/rfc/rfc9477 |
| C4 | PSL, DMARCbis | "this method should replace reliance on a public suffix list" quoted from draft-41 as DMARCbis wording; RFC 9989 number from a search excerpt | RFC 9989 (Standards Track, May 2026) obsoletes RFC 7489 and RFC 9091; §4.10 defines the DNS Tree Walk; the quoted sentence is RFC 9989's description of what RFC 7489 suggested | https://www.rfc-editor.org/rfc/rfc9989, https://www.rfc-editor.org/info/rfc7489 |
| C5 | DMARC (RFC 7489) | RFC 7489 presented as the current DMARC spec | Still correct as text, but obsoleted by RFC 9989 (and 9990, 9991) | https://www.rfc-editor.org/info/rfc7489 |
| C6 | Gmail personal row | "IMAP access is always enabled over OAuth" | "Starting January 2025, the option to choose "Enable IMAP" or "Disable IMAP" won't be available. IMAP access is always turned on in Gmail" | https://support.google.com/mail/answer/7126229 |
| C7 | Workspace row; Answer 9 | Password-only ended 1 May 2025; app password "only if the admin permits" | Google's readable page says only "Starting January 2025 ... For exact dates, visit Google Workspace Updates". App-password page lists "a work, school, or another organization account" as a reason the option is missing. Admin pages unreadable, so both stay unconfirmed | https://support.google.com/accounts/answer/6010255, https://support.google.com/accounts/answer/185833 |
| C8 | Microsoft 365 row; Answer 9 | "Basic auth and app passwords are dead" for Microsoft 365 as a whole | IMAP: yes, dead. SMTP AUTH: Basic still available (page updated 2026-09-16), disabled where unused, retirement announced with a date on a blocked page | https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online, https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/authenticated-client-smtp-submission |
| C9 | Microsoft 365 bullet | "The deprecation of basic authentication also prevents the use of app passwords" (truncated) | "... prevents the use of app passwords with apps that don't support two-step verification" | same deprecation page |
| C10 | Outlook.com row | App passwords "No in effect" | Contradiction reported exactly: settings page says OAuth2/Modern Auth for IMAP/POP/SMTP and also "you may need an app password"; no page says whether an app password works for IMAP. Marked unproven | https://support.microsoft.com/en-us/outlook/pop-imap-and-smtp-settings-for-outlook-com |
| C11 | Gmail categories | "Updates often collects low-priority emails such as order confirmations and reminders"; operators "work only when inbox categories are enabled" | "Updates: Automated confirmations, notifications, statements, and reminders that may not need immediate attention"; search help: "If you use inbox categories, find emails under one of the categories"; archived mail does not appear in categories | https://support.google.com/mail/answer/3094499, https://support.google.com/mail/answer/7190 |
| C12 | Takeout; Answer 8 | "Takeout exports Gmail in MBOX format", attributed to the Google Takeout page | That page confirms only `X-Gmail-Labels` and "your download file"; it does not name mbox. Claim kept as `[search]` | https://support.google.com/accounts/answer/3024190 |
| C13 | Takeout | `X-GM-THRID` treated as present in Takeout | Documented by Google only as an IMAP fetch attribute | https://developers.google.com/workspace/gmail/imap/imap-extensions |
| C14 | Gmail markup | Markup "placed anywhere in the HTML body"; registration needs authentication | Confirmed "anywhere inside the `<body>`"; added: registration also needs "order of hundreds of emails a day minimum to Gmail" for weeks, and markup is removed on forwarding | https://developers.google.com/workspace/gmail/markup/getting-started, https://developers.google.com/gmail/markup/registering-with-google |
| C15 | Gmail guidelines | One threshold wording | "close to 5,000" (FAQ definition) vs "more than 5,000" (guidelines page); added: not required for forwarded or mailing-list alignment, not applied to Workspace recipients, 48-hour removal recommended | https://support.google.com/a/answer/14229414, https://support.google.com/a/answer/81126 |

### Confirmed against the full page (tag changed to `[read]`)

| # | Claim | Source |
|---|---|---|
| R1 | Gmail: SPF or DKIM for all senders from 1 Feb 2024; SPF+DKIM+DMARC (`p=none` ok) and alignment for bulk senders | https://support.google.com/a/answer/81126 |
| R2 | Gmail bulk sender definition, per primary domain, permanent | https://support.google.com/a/answer/14229414 |
| R3 | Gmail one-click: both headers, one HTTPS URL, `mailto:` insufficient, 1 June 2024 | https://support.google.com/a/answer/14229414 |
| R4 | Gmail transactional exemption and its examples; "can vary"; recipients decide | https://support.google.com/a/answer/14229414 |
| R5 | Gmail enforcement ramp-up from November 2025 | https://support.google.com/a/answer/14229414 |
| R6 | Yahoo requirements, February 2024 start, June 2024 one-click enforcement, 2-day honouring, transactional exemption (open point 8 resolved) | https://senders.yahooinc.com/best-practices/, https://senders.yahooinc.com/faqs/ |
| R7 | Outlook.com 5,000+ threshold and SPF/DKIM/DMARC requirements (not the date) | https://support.microsoft.com/en-us/outlook/fix-ndr-error-550-5-7-515-in-outlook-com |
| R8 | `Feedback-ID` format, 5-15 character SenderId, DKIM by sender-controlled domain | https://support.google.com/mail/answer/6254652 |
| R9 | `X-Auto-Response-Suppress` values | https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxcmail/ced68690-498a-4567-9d14-5c01f974d8b1 |
| R10 | Gmail markup: JSON-LD and Microdata; types Order, ParcelDelivery, Invoice, reservations; registration with Google | https://developers.google.com/workspace/gmail/markup/overview, https://developers.google.com/gmail/markup/reference, https://developers.google.com/gmail/markup/registering-with-google |
| R11 | Gmail search operators `category:*`; `X-GM-RAW` | https://support.google.com/mail/answer/7190, https://developers.google.com/workspace/gmail/imap/imap-extensions |
| R12 | `X-Gmail-Labels` in Takeout downloads | https://support.google.com/accounts/answer/3024190 |
| R13 | Gmail IMAP extensions `X-GM-EXT-1`, `X-GM-MSGID`, `X-GM-THRID`, `X-GM-LABELS`, `\All` special-use | https://developers.google.com/workspace/gmail/imap/imap-extensions |
| R14 | XOAUTH2 for Google and Microsoft; scope `https://mail.google.com/`; `gmail.imap_admin` | https://developers.google.com/workspace/gmail/imap/xoauth2-protocol |
| R15 | Gmail app passwords need 2-Step Verification; conditions when the option is missing; "aren't recommended" | https://support.google.com/accounts/answer/185833 |
| R16 | Restricted scope needs a yearly security assessment | https://support.google.com/cloud/answer/13463817 |
| R17 | Testing: 100 test users, 7-day expiry; unverified cap of 100 new users; internal apps exempt | https://support.google.com/cloud/answer/15549945, https://support.google.com/cloud/answer/13464323, https://developers.google.com/identity/protocols/oauth2 |
| R18 | **Personal mode exists** (open point 10) | https://support.google.com/cloud/answer/15549945, https://support.google.com/cloud/answer/13464323 |
| R19 | `gmail.metadata` is restricted; `q` unusable with it | https://developers.google.com/workspace/gmail/api/auth/scopes, https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list |
| R20 | Outlook.com Basic auth ended 16 September 2024 | https://support.microsoft.com/en-us/office/modern-authentication-methods-now-needed-to-continue-syncing-outlook-email-in-non-microsoft-email-apps-c5d65390-9676-4763-b41f-d7986499a90d |
| R21 | Outlook.com server settings, OAuth2/Modern Auth, POP/IMAP off by default | https://support.microsoft.com/en-us/outlook/pop-imap-and-smtp-settings-for-outlook-com |
| R22 | Microsoft OAuth scopes and "available for both Microsoft 365 and Outlook.com" | https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth |
| R23 | Exchange Online Basic auth disabled in all tenants, cannot be re-enabled (IMAP/POP) | https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online |
| R24 | Client-credentials flow needs tenant admin consent | OAuth page (R22) |
| R25 | User consent can be disabled or limited in Entra | https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent |
| R26 | Per-mailbox IMAP disablement exists (open point 11, first half) | https://learn.microsoft.com/en-us/Exchange/recipients-in-exchange-online/manage-user-mailboxes/managing-email-apps-for-user-mailboxes |
| R27 | Gmail personal: third-party password sign-in unsupported; IMAP always on from January 2025; app password suggested in troubleshooting | https://support.google.com/mail/answer/7126229 |
| R28 | RFC 9989 number, title, Standards Track, May 2026, obsoletes 7489 and 9091 (open point 1) | https://www.rfc-editor.org/rfc/rfc9989 |
| R29 | RFC quotes for RFC 2369, 2919, 3834, 4155, 5321, 5322, 6376, 7162, 7489, 8058, 8601, 3501 and 9051 (about 55 quoted phrases) match the rfc-editor.org text; two wording differences were only case or markup (`multipart/form-data` quoted with single quotes in the RFC; "Organizational Domains" wording matches RFC 7489 §3.1.1). Status: RFC 8058 Standards Track January 2017 (not updated); RFC 3501 obsoleted by RFC 9051; RFC 3834 updated by RFC 5436; RFC 6376 updated by RFC 8301, 8463, 8553, 8616 | https://www.rfc-editor.org/rfc/ and https://www.rfc-editor.org/info/ pages |

### Still unverified, and why

- **Blocked:** Google Workspace admin pages (redirect to knowledge.workspace.google.com), workspaceupdates.googleblog.com, techcommunity.microsoft.com (Outlook.com sender date and unsubscribe recommendation; Exchange SMTP AUTH retirement date), the ESP documentation sites, ftc.gov, eur-lex.europa.eu. These claims keep their tags.
- **Only a live test on a real mailbox or account can settle:** Gmail IMAP CONDSTORE/QRESYNC support; whether categories appear in `X-GM-LABELS`; Takeout mbox variant, file layout and `From ` line; whether `X-GM-THRID` is in Takeout; Gmail's `Authentication-Results` property names and `authserv-id`; whether an Outlook.com app password works for IMAP; whether `IMAP.AccessAsUser.All` needs admin consent in a tenant with user consent disabled; Workspace app-password availability; how common schema.org markup is; the keyword and grading heuristics.
- **Not checked:** app passwords at iCloud, Fastmail and others; GitHub-sourced `[read]` claims (eraser, AccountSweep and similar) were not revisited because the task was limited to the primary web sources.
