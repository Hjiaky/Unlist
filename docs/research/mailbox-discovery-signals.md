# Which signals in a mailbox reliably identify an Organization and an account?

Research for issue #6. Checked on **2026-11-26**.

## Answer

1. **Identity key:** the registrable domain (Public Suffix List, both sections) of the `From:` address, counted only when the mailbox provider's own `Authentication-Results` shows a DMARC pass or an aligned DKIM `d=`. Header-only, no LLM.
2. **Do not key on the rest:** `Return-Path`, an unaligned DKIM `d=`, the `List-Id` namespace and `Feedback-ID` usually name the email service provider (ESP), not the brand. Use them to detect "sent through an ESP". If `From:` itself sits on a shared ESP or platform domain, fall back to display name plus `List-Unsubscribe` host and flag for review.
3. **Why headers are now dependable:** Gmail and Yahoo (from February 2024) and Outlook.com (2025) require bulk senders (about 5,000+ messages a day) to pass SPF, DKIM and DMARC with `From:` alignment, and Gmail and Yahoo require `List-Unsubscribe` + `List-Unsubscribe-Post` (RFC 8058) on marketing mail. Transactional mail is exempt from the unsubscribe rule.
4. **Bulk versus personal:** any `List-*` header, `Precedence: bulk|list|junk`, or `Auto-Submitted` other than `no` marks a message as not written by a person. These prove the Organization holds the address and mails it. They do not prove an account.
5. **Account evidence, strongest first:** schema.org `Order` / `Invoice` / `ParcelDelivery` / `*Reservation` markup in the HTML body, then order, receipt, invoice and shipping mail, then welcome, verification, password-reset, security and policy notices, then newsletters. Subject and local-part keyword rules cover most of it without an LLM.
6. **Domain is not the legal entity:** an Access Request or Removal Request must reach the GDPR controller. Map domain to Organization through Organization Lists (`datenanfragen/data` has `web` and `runs`, JustDeleteMe has `domains`), then the Organization's own privacy page. Never guess an address.
7. **Cheap IMAP scan:** `EXAMINE` (read-only) plus `UID FETCH … BODY.PEEK[HEADER.FIELDS (…)]` reads chosen headers without setting `\Seen`. Incremental scans need only `UIDVALIDITY` and the highest UID seen. CONDSTORE and QRESYNC matter only for tracking flag changes and expunges.
8. **mbox:** there is no authoritative spec. RFC 4155 only registers the media type, and four variants (mboxo, mboxrd, mboxcl, mboxcl2) differ in `From ` quoting. Header signals only need correct message splitting. Google Takeout exports Gmail as mbox with an `X-Gmail-Labels` header per message.
9. **Login today:** Gmail personal = app password (needs 2-Step Verification) or OAuth. Google Workspace = OAuth, or app password if the admin allows; password-only ended 1 May 2025. Outlook.com = OAuth2 only since 16 September 2024. Microsoft 365 = OAuth only; Basic auth and app passwords are dead. A Takeout mbox needs no credentials at all.
10. **Prior art:** `tmaeder/eraser` already does a headers-only IMAP scan, groups by registrable domain and sends GDPR requests. Nothing found combines authenticated-domain identity, graded account evidence and shareable Organization Lists. `email-oauth2-proxy` (Apache-2.0) is the reference for the OAuth problem.

**Confidence warning.** The research sandbox could reach GitHub, package registries and a web-search tool, and nothing else. rfc-editor.org, datatracker.ietf.org, support.google.com, developers.google.com, learn.microsoft.com, support.microsoft.com, the ESP documentation sites and eur-lex.europa.eu were all blocked. RFC text was read in full from Ubuntu's `doc-rfc` packages (snapshot 2023-01-21), so RFCs published or amended later were not read. Every Google, Microsoft, Yahoo and ESP claim comes from search-engine excerpts of the official page, not from the page itself. The list of what could not be verified is at the [end](#not-verified).

## Verification

| Tag | Meaning |
|---|---|
| `[read]` | Read directly on 2026-11-26: RFC text from the Ubuntu `doc-rfc_20230121` packages (identical to the rfc-editor.org `.txt`), or a clone of the project's own GitHub repo at the commit named. |
| `[search]` | Taken from search-engine excerpts or summaries of the live official page on 2026-11-26. Wording may be paraphrased; the page was not read in full. |
| `[memory]` | Not confirmed in this session. From memory, **(unverified)**. |
| `[analysis]` | My own reasoning from the verified facts. A design judgement, not a sourced fact. |

## Signals ranked by reliability and cost

"Body" means the scan must download the message body, not just headers. "LLM" means a language model is needed for acceptable results. Reliability is for the stated purpose only. `[analysis]` for every ranking; the facts behind each row are sourced in the sections below.

| # | Signal | What it tells Unlist | Reliability | Body? | LLM? | Cost and caveats |
|---|---|---|---|---|---|---|
| 1 | `From:` registrable domain, with DMARC pass or aligned DKIM `d=` in the provider's `Authentication-Results` | Which Organization (as a domain) sent it | High | No | No | One header fetch. Trust only the provider's own topmost `Authentication-Results`. Old mail may predate DMARC. |
| 2 | schema.org `Order`, `Invoice`, `ParcelDelivery`, `*Reservation` (JSON-LD or microdata) | A transaction happened; merchant name; order number | High when present | Yes (HTML part) | No | Present on a minority of mail (prevalence unverified). Fetch bodies only for candidates. |
| 3 | `List-Unsubscribe` + `List-Unsubscribe-Post: List-Unsubscribe=One-Click` | Marketing or subscribed mail; a one-click removal route exists | High for "bulk marketing" | No | No | Says nothing about an account. Mandatory for bulk marketing at Gmail and Yahoo since 2024. |
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

- **Gmail.** Since 1 February 2024 every sender to Gmail accounts must authenticate with SPF or DKIM. Bulk senders must have SPF, DKIM and DMARC. For direct mail the `From:` domain must align with the SPF or the DKIM domain. `[search]` https://support.google.com/a/answer/81126
- A bulk sender is one that sends "close to 5,000 messages or more to personal Gmail accounts within a 24-hour period", counted per primary domain, and the status is permanent once reached. `[search]` https://support.google.com/a/answer/14229414
- Marketing and subscribed messages from bulk senders must support one-click unsubscribe: `List-Unsubscribe-Post: List-Unsubscribe=One-Click` plus a `List-Unsubscribe` header with one HTTPS URL, per RFC 8058. `mailto:` and plain URL links do not satisfy the requirement. Senders that already had an unsubscribe link had until 1 June 2024. `[search]` https://support.google.com/a/answer/14229414
- **Transactional mail is excluded** from the one-click requirement. Google's examples: "password reset messages, reservation confirmations, and form submission confirmations". Google adds that the promotional / transactional line "can vary" and that recipients decide the nature of a message. `[search]` same FAQ
- Gmail said it was "ramping up its enforcement on non-compliant traffic" from November 2025, including temporary and permanent rejections. `[search]` same FAQ
- **Yahoo.** Bulk senders must use SPF and DKIM and publish a DMARC policy (at least `p=none`) that passes, with `From:` aligned to SPF or DKIM (relaxed is fine). Marketing and subscribed mail needs a `List-Unsubscribe` header supporting one-click; the RFC 8058 POST method is "highly recommended" and `mailto:` is accepted. Requests must be honoured within 2 days. One-click enforcement began in June 2024. `[search]` https://senders.yahooinc.com/best-practices/ and https://senders.yahooinc.com/faqs/
- **Outlook.com (consumer).** Senders of 5,000+ messages a day must pass SPF and DKIM and publish DMARC (at least `p=none`) aligned with the `From:` domain. Enforcement started in May 2025. A functional unsubscribe link is a recommendation, not a requirement. `[search]` https://techcommunity.microsoft.com/blog/microsoftthreatprotectionblog/strengthening-email-ecosystem-outlook%E2%80%99s-new-requirements-for-high%E2%80%90volume-senders/4399730 and https://support.microsoft.com/en-us/outlook/fix-ndr-error-550-5-7-515-in-outlook-com
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
- `X-Auto-Response-Suppress` is a Microsoft header (values `DR`, `NDR`, `RN`, `NRN`, `OOF`, `AutoReply`, `All`, `None`) asking Exchange not to send automatic replies. Automated senders set it; people do not. `[search]` https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxcmail/ced68690-498a-4567-9d14-5c01f974d8b1

### Feedback-ID and CFBL-Address

- `Feedback-ID` is defined by Gmail's Feedback Loop, not by an RFC. Format: `Feedback-ID: a:b:c:SenderId`. `a`, `b`, `c` are optional campaign or customer identifiers. `SenderId` is mandatory, 5 to 15 characters, chosen by the sender and stable across its mail stream. The mail must be DKIM-signed by a domain the sender controls. `[search]` https://support.google.com/mail/answer/6254652
- Use for Unlist `[analysis]`: when an ESP sets it, `SenderId` names the ESP and the other fields name the ESP's customer. It is an ESP fingerprint and sometimes a stable per-brand token, not an identity.
- RFC 9477 (2023) defines `CFBL-Address` and `CFBL-Feedback-ID`, a sender-published complaint address. Both must be covered by a valid DKIM signature. `[search]` https://www.rfc-editor.org/rfc/rfc9477. Not in the RFC snapshot read here; status and details not confirmed.

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
- DMARC is what binds them: it "authenticates use of the RFC5322.From domain by requiring that it match (be aligned with) an Authenticated Identifier". RFC 7489 is Informational, an Independent Submission, March 2015. `[read]` https://www.rfc-editor.org/rfc/rfc7489 §3.1
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
- DMARCbis, the Standards Track successor to RFC 7489, replaces the PSL with a "DNS Tree Walk" for DMARC's own purposes: "this method should replace reliance on a public suffix list". `[read]` draft-ietf-dmarc-dmarcbis-41 §4.10, https://github.com/ietf-wg-dmarc/draft-ietf-dmarc-dmarcbis commit 9491807. A search excerpt says it was published as RFC 9989. `[search]` https://datatracker.ietf.org/doc/draft-ietf-dmarc-dmarcbis/. This does not affect Unlist: the tree walk needs live DNS and answers a different question. The PSL remains the right offline tool for grouping.

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

- Gmail's email markup accepts schema.org data as **JSON-LD or Microdata**, placed anywhere in the HTML body. `[search]` https://developers.google.com/workspace/gmail/markup/overview
- Supported types include `Order`, `ParcelDelivery`, `Invoice`, `FlightReservation`, `LodgingReservation`, and bus, train, rental-car, restaurant and event reservations. `[search]` https://developers.google.com/gmail/markup/reference
- To have Gmail act on the markup, senders must register with Google, and mail "must be authenticated using DKIM or SPF" with the authenticated domain matching `From:`. `[search]` https://developers.google.com/gmail/markup/registering-with-google
- For Unlist `[analysis]`: a `<script type="application/ld+json">` block with `"@type": "Order"` (or the Microdata equivalent) is an unambiguous, language-independent transaction marker, and its `merchant` / `seller` / `provider` / `reservationFor` objects often carry the Organization's name. Parsing needs the `text/html` part only. Fetch it with `BODY.PEEK[<part>]` for candidate messages rather than for the whole mailbox.
- How many senders embed this markup is unknown. `[memory]` **(unverified)**: common at large retailers, airlines and booking sites, rare elsewhere. Treat it as a high-precision, low-recall signal.
- **Gmail's own categories.** Gmail search has `category:primary|social|promotions|updates|forums|reservations|purchases`. "Updates often collects low-priority emails such as order confirmations and reminders." The operators work only when inbox categories are enabled. `[search]` https://support.google.com/mail/answer/7190 and https://support.google.com/mail/answer/3094499
- Takeout writes each message's labels to `X-Gmail-Labels` (below). Third-party reports show category labels in it, for example `Category Forums`. `[search]` https://support.mozilla.org/en-US/questions/1336844. Over IMAP the same search is reachable with `X-GM-RAW`. Whether categories also appear in `X-GM-LABELS` was not confirmed. `[memory]` **(unverified)**

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

- Takeout exports Gmail in MBOX format. "When you export your mail from Gmail, each message's labels are preserved in a special X-Gmail-Labels header in your download file." `[search]` https://support.google.com/accounts/answer/3024190
- The export can be limited to chosen labels. `[search]` https://support.google.com/mail/thread/27077156
- Third-party reports: the value is a comma-separated label list, for example `X-Gmail-Labels: Important,Trash,Opened,Category Forums`, and an `X-GM-THRID` header is also present. `[search]` https://support.mozilla.org/en-US/questions/1336844. Not confirmed by a Google page.
- Which mbox variant Takeout writes, whether it emits one file or several, and the exact shape of its `From ` line were not confirmed. `[memory]` **(unverified)**: a single `All mail Including Spam and Trash.mbox` when all mail is selected, with `>From ` quoting.
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
- **Scan each message once.** Gmail exposes labels as folders, so the same message appears in several. `X-GM-MSGID` is a message id that is the same across folders; `X-GM-LABELS` returns a message's labels; `X-GM-RAW` runs Gmail search syntax. Support is advertised as `X-GM-EXT-1` in `CAPABILITY`. `[search]` https://developers.google.com/workspace/gmail/imap/imap-extensions. RFC 6154 defines the `\All` special-use attribute for an all-messages mailbox. `[read]` https://www.rfc-editor.org/rfc/rfc6154 §2. On Gmail, scan the `\All` folder and skip `\Junk` and `\Trash`.
- Whether Gmail's IMAP server supports CONDSTORE or QRESYNC was not confirmed; Google's sample `CAPABILITY` line lists neither. `[search]` same page. **(unverified)**
- **OAuth over IMAP.** The standard SASL mechanism is `OAUTHBEARER` (RFC 7628). `[read]` https://www.rfc-editor.org/rfc/rfc7628. Google and Microsoft both document `XOAUTH2`: `AUTHENTICATE XOAUTH2 <base64("user=" user ^A "auth=Bearer " token ^A ^A)>`. `[read]` Microsoft doc source, https://github.com/MicrosoftDocs/office-developer-exchange-docs `docs/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth.md`, commit 1deccef; `[search]` https://developers.google.com/workspace/gmail/imap/xoauth2-protocol

### What each provider allows today

| Account | Password only | App password | OAuth 2.0 over IMAP | Other gates |
|---|---|---|---|---|
| **Gmail, personal** (`@gmail.com`) | No | **Yes**, if 2-Step Verification is on. Not offered when 2SV uses security keys only, or with Advanced Protection | **Yes**, scope `https://mail.google.com/` (a restricted scope) | IMAP toggle removed; "IMAP access is always enabled over OAuth" |
| **Google Workspace** (work, school) | No, since 1 May 2025 | Only if the admin permits; needs 2SV; disabled when the admin enforces security keys | **Yes**, unless the admin blocks or restricts third-party app access or IMAP | Admin can turn IMAP off, or allow only listed OAuth client IDs |
| **Outlook.com, Hotmail, Live** (personal Microsoft account) | No, since 16 September 2024 | **No** in effect: Basic authentication is gone and app passwords are Basic authentication. One Microsoft page still mentions app passwords (see below) | **Yes**, scope `https://outlook.office.com/IMAP.AccessAsUser.All` + `offline_access` | POP/IMAP is off by default and must be enabled in Outlook.com settings |
| **Microsoft 365 / Exchange Online** (work, school) | No. Basic auth is disabled in all tenants and cannot be re-enabled | **No** | **Yes**: delegated (auth code or device code) or app-only (client credentials, admin-registered service principal) | Tenant admin controls user consent; may require admin consent |

Sources, row by row:

- **Gmail personal.**
  - Password-only sign-in by third-party apps is no longer supported; Google's wind-down post also says that for personal Gmail the IMAP on/off setting is removed and "IMAP access is always enabled over OAuth and your current connections will not be impacted". `[search]` https://workspaceupdates.googleblog.com/2023/09/winding-down-google-sync-and-less-secure-apps-support.html and https://support.google.com/accounts/answer/6010255
  - "App passwords can only be used with accounts that have 2-Step Verification turned on." The option is missing if 2SV is "set up only for security keys", the account is "a work, school, or another organization account", or it has Advanced Protection. Google says app passwords "aren't recommended". `[search]` https://support.google.com/accounts/answer/185833
  - "the scope for IMAP, POP, and SMTP access is `https://mail.google.com/`". It is a restricted scope; an app that requests it from the public needs restricted-scope verification, including a CASA security assessment, renewed about yearly. `[search]` https://developers.google.com/workspace/gmail/imap/xoauth2-protocol and https://support.google.com/cloud/answer/13463817
- **Google Workspace.**
  - "Starting May 1, 2025, Google Workspace accounts no longer support less secure apps, third-party apps, or devices that ask you to sign in to your Google Account with your username and password." CalDAV, CardDAV, IMAP, SMTP and POP stop working with passwords. Users "must use OAuth, or use 2-Step Verification with an app password for email clients that don't support OAuth". `[search]` https://support.google.com/a/answer/14114704
  - Enforcing security keys for 2SV disables app passwords. `[search]` https://support.google.com/a/answer/9176599
  - Admin IMAP setting: off, "Allow any mail client", or "Restrict which mail clients users can use (OAuth mail clients only)" with a list of OAuth client IDs. `[search]` https://support.google.com/a/answer/105694
  - Admins can restrict Gmail scopes (including `mail.google.com`) to trusted apps and block unconfigured third-party apps. `[search]` https://support.google.com/a/answer/7281227
- **Outlook.com.**
  - Timeline ending 16 September 2024, after which "users attempting to connect their Microsoft accounts through Basic Authentication will fail to do so". `[search]` https://support.microsoft.com/en-us/office/modern-authentication-methods-now-needed-to-continue-syncing-outlook-email-in-non-microsoft-email-apps-c5d65390-9676-4763-b41f-d7986499a90d
  - Server `outlook.office365.com`, port 993, TLS; "Outlook.com requires OAuth2/Modern Auth"; POP and IMAP are disabled by default. The same page still suggests an app password "if your password is not being recognized". The two statements conflict. `[search]` https://support.microsoft.com/en-us/outlook/pop-imap-and-smtp-settings-for-outlook-com. Treat app passwords as not working for IMAP until tested. **(partly unverified)**
  - "OAuth2 support for IMAP, POP, and SMTP protocols as described below is available for both Microsoft 365 (which includes Office on the web) and Outlook.com users." Scopes: `https://outlook.office.com/IMAP.AccessAsUser.All`, plus `offline_access` for refresh tokens. `[read]` Microsoft doc source, commit 1deccef
- **Microsoft 365.**
  - Basic authentication "is now disabled in all tenants" and "no one (you or Microsoft support) can re-enable" it. Permanent disablement began 1 October 2022, with a one-time re-enable that ended 31 December 2022. "The deprecation of basic authentication also prevents the use of app passwords". Developers "need to implement secure, Modern authentication". `[search]` https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online
  - Client-credentials access needs tenant admin consent and a service principal registered in Exchange Online with `New-ServicePrincipal`. `[read]` Microsoft doc source, commit 1deccef
  - With user consent set to "Do not allow user consent", users cannot grant an app access themselves; an admin must. `[search]` https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent
  - Per-mailbox IMAP disablement by admins was not checked. `[memory]` **(unverified)**

### The OAuth client problem for a self-hosted tool

- OAuth needs a registered client. A self-hosted AGPL tool cannot ship a secret, and a shared public client for Gmail means Google's restricted-scope verification and yearly security assessment. `[search]` https://support.google.com/cloud/answer/13463817
- PrivacyBot (UC Berkeley) is the cautionary case: "As of 9.28.21 this project has been depreciated and Google Oauth verification is not supported. You can still run the tool but you need to setup your own instance of Google Oauth credentials." `[read]` https://github.com/privacybot-berkeley/privacybot README, commit 62e89b7
- Operator-registered Google client, External + **Testing**: at most 100 listed test users, and "a refresh token expiring in 7 days". `[search]` https://developers.google.com/identity/protocols/oauth2 and https://support.google.com/cloud/answer/15549945
- External + **In production**, unverified: usable by up to 100 users who click through the "unverified app" warning. `[search]` https://support.google.com/cloud/answer/13464323
- Google also describes a **Personal mode**: "restricted exclusively to the creator's Google Account", no verification, no warning screen, no 7-day expiry, and irreversible. `[search]` https://support.google.com/cloud/answer/15549945. This would suit a one-Operator instance, but the page was not read in full and the feature looks new. Confirm before relying on it.
- Workspace-internal clients have neither the warning nor the cap. `[search]` https://support.google.com/cloud/answer/13464323
- Microsoft: register an Entra app that allows personal accounts and/or organisational accounts. For personal Outlook accounts, `email-oauth2-proxy` notes that you need "the Microsoft 365 Developer Programme or … an Azure account (including free accounts)" to create a registration, or else must reuse an existing client ID. Yahoo and AOL "are not currently allowing new client registrations with the OAuth email scope". `[read]` https://github.com/simonrob/email-oauth2-proxy README, commit fac1ffb
- **Gmail API as an alternative.** The `gmail.metadata` scope gives "message metadata such as labels and headers, but not the email body", which matches a headers-only scan and is enforced by Google. But the `q` search parameter "cannot be used when accessing the api using the gmail.metadata scope", and `gmail.metadata` is itself in Google's restricted-scope table. `[search]` https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list and https://developers.google.com/workspace/gmail/api/auth/scopes. `dataclean` and AccountSweep's advanced mode both choose this scope. `[read]` their READMEs
- Ordering of options for Unlist `[analysis]`: (1) Takeout mbox import, no credentials; (2) IMAP with an app password where the provider still offers one (personal Gmail, iCloud, Fastmail and most independent hosts); (3) OAuth with an Operator-registered client, documented step by step, with `email-oauth2-proxy` as a drop-in for those who already run it; (4) never a project-owned shared client.

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

Items the session could not confirm against the owning source. Each is also marked inline.

**Blocked hosts.** rfc-editor.org and datatracker.ietf.org (RFCs were read from the Ubuntu `doc-rfc` 2023-01-21 snapshot instead, so errata and later updates are unchecked), support.google.com, developers.google.com, workspaceupdates.googleblog.com, learn.microsoft.com, support.microsoft.com, techcommunity.microsoft.com, senders.yahooinc.com, mailchimp.com, twilio.com, docs.aws.amazon.com, help.klaviyo.com, ftc.gov, eur-lex.europa.eu. Everything tagged `[search]` rests on search-engine excerpts of those pages and should be re-read before it drives a design decision or user-facing text.

**Specific open points.**

1. RFC 9477 (`CFBL-Address`) and RFC 9989 (DMARCbis): not in the RFC snapshot. Number, status and "obsoletes RFC 7489" come from search excerpts; the tree-walk text was read in draft-41 only.
2. Whether Gmail's IMAP server supports CONDSTORE or QRESYNC.
3. Takeout specifics: mbox variant, one file or several, the `From ` separator format, and the `X-GM-THRID` header. Only `X-Gmail-Labels` is confirmed by a Google page (via search excerpt).
4. Whether Gmail categories appear in IMAP `X-GM-LABELS`, and the label strings Takeout uses for them.
5. The property names in Gmail's `Authentication-Results` (`header.i` versus `header.d`) and the `authserv-id` values of the major providers.
6. Outlook.com app passwords: Microsoft's notice says Basic authentication fails since 16 September 2024, but its settings page still mentions app passwords. Needs a live test.
7. Outlook.com sender rules: only "May 2025" was confirmed, not the exact day. Search results also showed November 2026 forum reports of Outlook.com rejecting unauthenticated mail from small senders; no official change was found.
8. Yahoo's February 2024 start date for its sender requirements (only the June 2024 one-click enforcement date was confirmed).
9. The date Google ended password-only sign-in for personal accounts (30 May 2022 from memory).
10. Google's "Personal mode" for OAuth clients: seen in one search excerpt only.
11. Microsoft 365 per-mailbox IMAP disablement, and whether `IMAP.AccessAsUser.All` needs admin consent by default.
12. ESP specifics beyond the excerpts: SendGrid's default return-path without domain authentication, ESP fingerprint headers (`X-SG-EID`, `X-Mailgun-Sid`, `X-MC-User`, `Feedback-ID: …:AmazonSES`), and typical `List-Id` values at Mailchimp.
13. How common schema.org email markup is in real mailboxes. This decides whether signal 2 is worth a body fetch; measure it on a real mailbox before building on it.
14. GDPR Art. 13(1)(a), e-Commerce Directive Art. 5 and 6, and German DDG §5 wording on sender and controller identification. Only GDPR Art. 4(7) and the US CAN-SPAM postal-address rule were confirmed by search excerpt.
15. `tmaeder/eraser` licence: the README says MIT, but the repository has no LICENSE file and no `license` field in `Cargo.toml`. Ask the author before reusing code.
16. Mine / SayMine, Unroll.me and Deseat.me were not examined; they are closed-source.
17. None of the heuristics in this note (keyword rules, the bulk / transactional / personal split, evidence grades) was tested on real mail. They are design proposals.
