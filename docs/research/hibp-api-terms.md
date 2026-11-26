# Have I Been Pwned: API terms and pricing for a self-hosted tool

Research for issue #7. Checked on **2026-11-26**.

## Answer

- **A paid key is needed for the one call Unlist cares about.** Looking up a Subject's email address (`breachedaccount`) needs an HIBP key. The cheapest plan, **Core 1, is US$4.39/month billed yearly (US$52.68/year) or US$5.29 month-to-month, at 10 requests per minute**, which is far more than a household needs. There are no free keys or trials.
- **The breach catalogue is free and keyless** (`/breaches`, `/breach/{name}`, `/latestbreach`, `/dataclasses`), as is Pwned Passwords. HIBP's terms let both be used "for any lawful purpose", including for third parties.
- **Bring-your-own-key is the model the terms require.** The terms bar redistributing a key or reselling the service, and allow querying addresses "supplied by, or relating to, your own users, customers or clients" under any paid plan with email search. An Operator checking consenting Subjects on their own key fits. Unlist must never ship, share or proxy a key, and must not give anyone outside the Operator access to the Operator's HIBP account.
- **Breach and paste data is CC BY 4.0.** Unlist must show a visible attribution with a link to haveibeenpwned.com wherever the data appears, and must send an honest `User-Agent` naming the app (a missing one gets HTTP 403).
- **No clause forbids storing results or scheduled re-checks (Terms of Use read in full, last updated 27 October 2026).** The only storage rule is for the Pro-only k-anonymity search (unmatched suffixes must be discarded). The Permitted Purpose says "on-demand queries ... up to a certain rate limit" and "on-demand" is not defined. HIBP's own docs tell integrators to poll the free latest-breach endpoint and query again only after a new breach appears, which is the pattern in Implications. The terms do bar building a breach search service "substantially the same" as HIBP, giving a third party access to your account or services without HIBP's written agreement, and automating undocumented endpoints.
- **`Domain` links most breaches to an Organization, but not all.** It is the breached site's primary domain, one per breach, and is empty for 55 of the 1,055 catalogue entries (all six stealer-log breaches, spam lists, malware sets and many aggregations, including some that look like Brokers). Match on it first and keep a manual override keyed by the stable `Name`.
- **Sensitive breaches never come back from the email API.** Only the verified address owner (HIBP dashboard) or a verified domain owner (domain search) sees them, so a clean result is not proof of no breach.
- **Stealer-log site lists and privacy-preserving (k-anonymity) email search are Pro only**, from US$379/month, so out of reach for a household. The stealer-log lookup also requires the address's domain to be verified on the account.

**Confidence note (updated 2026-11-26 after a verification pass).** The Terms of Use (<https://haveibeenpwned.com/TermsOfUse>), API documentation (<https://haveibeenpwned.com/API/v3>), pricing page (<https://haveibeenpwned.com/Subscription>), OpenAPI document, FAQs and privacy page were fetched and read in full on 2026-11-26, and the live `/api/v3/breaches` catalogue (1,055 breaches) was fetched and counted. Claims resting on those pages are now `[read]`. `support.haveibeenpwned.com`, `troyhunt.com`, `brand.haveibeenpwned.com` and `api.pwnedpasswords.com` are not reachable from the research environment, so claims whose only source is one of those stay `[search]` or `[memory]`. See [Verification](#verification) and the [Verification log](#verification-log).

## Verification

Each claim carries one of these tags.

| Tag | Meaning |
|---|---|
| `[read]` | The source file or page was fetched and read directly (HIBP pages: read in full on 2026-11-26). |
| `[search]` | Taken from search-engine excerpts or summaries of a page that could not be fetched (support.haveibeenpwned.com, troyhunt.com). Wording may be paraphrased; the page was not read in full. |
| `[memory]` | Not confirmed. From memory, unverified. |

## 1. Endpoints, plans, prices and rate limits

Base URL is `https://haveibeenpwned.com/api/v3` `[read]` (<https://haveibeenpwned.com/API/v3>). An OpenAPI 3.1 document is published at <https://haveibeenpwned.com/openapi.json> and an interactive reference at <https://haveibeenpwned.com/scalar/> `[read]`. Where the OpenAPI text and the HTML docs differ, the OpenAPI text says the account search accepts "email address, username, or phone number"; the HTML docs describe email only.

### Which endpoints need a key

The API docs mark every endpoint that is not free with badges naming the plans that support it `[read]` (<https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/openapi.json>).

| Endpoint | Key | Plan | Source |
|---|---|---|---|
| `GET /breaches` (whole catalogue) | No | Free | `[read]` <https://haveibeenpwned.com/API/v3> (fetched without a key: HTTP 200, 1,055 breaches) |
| `GET /breach/{name}` (one breach) | No | Free | `[read]` same |
| `GET /latestbreach` (most recently added, by `AddedDate`) | No | Free | `[read]` same |
| `GET /dataclasses` (and `/dataclasses/descriptions`) | No | Free | `[read]` same |
| Pwned Passwords `GET /range/{prefix}` | No | Free | `[read]` same |
| `GET /breachedaccount/{email}` | Yes | Core, Pro, High RPM | `[read]` same |
| `GET /pasteaccount/{email}` | Yes ("Requires a valid subscription key, including for this test account") | Core, Pro, High RPM, so **included in Core 1** | `[read]` <https://haveibeenpwned.com/API/v3> (badges), <https://haveibeenpwned.com/openapi.json> ("Available on Core, Pro, and High RPM subscriptions") |
| `GET /breachedaccount/range/{prefix}` (k-anonymity email search, first 6 SHA-1 characters) | Yes | Pro, High RPM | `[read]` <https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/openapi.json> |
| `GET /breacheddomain/{domain}` (domain search; unverified domain gives 403) | Yes | Core and Pro (badge omits High RPM), own verified domains only | `[read]` <https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/openapi.json> |
| `GET /subscribeddomains` | Yes | Core and Pro | `[read]` same |
| `GET /stealerlogsbyemail/{email}` (sites where the address's credentials were captured) | Yes | Pro 1 and up. The address must be on a domain already added and verified on the account | `[read]` <https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/openapi.json> |
| `GET /stealerlogsbywebsitedomain/{domain}`, `/stealerlogsbyemaildomain/{domain}` | Yes | Pro, verified domain, separate unpublished rate limit | `[read]` <https://haveibeenpwned.com/API/v3> |
| `GET /subscription/status` (returns `SubscriptionName`, `Description`, `SubscribedUntil`, `Rpm`, `DomainSearchMaxBreachedAccounts`, `MaxBreachedDomains`, `IncludesStealerLogs`, `IncludesBulkDomainAdd`, `IncludesAutoSubdomainVerification`, `IncludesCustomerDomains`, `IncludesKAnon`) | Yes | Core, Pro, High RPM | `[read]` same. Path confirmed. |

Notes:

- "Authorisation is required for all APIs that enable searching HIBP by email address or domain." The key goes in the `hibp-api-key` request header `[read]` (<https://haveibeenpwned.com/API/v3>). Keys are 32-character hexadecimal strings. The statement that a query-string key does not work was not found on the page and stays `[search]`.
- A stealer-log corpus is also loaded as an ordinary breach flagged `IsStealerLog`, so a Core key still reports that an address is *in* stealer logs. Only the list of websites needs Pro 1 `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/13868920521103-What-subscription-size-do-I-need-to-use-the-API>). The plan page's "Stealer logs are not available on Core plans" `[read]` (<https://haveibeenpwned.com/Subscription>) refers to that website list. The API docs confirm the flag: a breach with `IsStealerLog` "also has the domains that appear in the logs loaded against each email address" and that list is served by the stealer-logs API `[read]`.
- HIBP gives no free trials, sample data or free keys `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/10388846218511-Do-you-provide-free-trials-sample-data-or-free-API-Keys>). A test key works against test addresses on `hibp-integration-tests.com`, such as `account-exists@hibp-integration-tests.com`, and the documented test key is `00000000000000000000000000000000` `[read]` (<https://haveibeenpwned.com/API/v3>). Test keys do not waive subscription requirements on other endpoints (paste search needs a real key even for the test address) `[read]` (<https://haveibeenpwned.com/openapi.json>).
- Authenticated endpoints do not support CORS, so the key must stay server-side `[read]` ("CORS is only supported for non-authenticated APIs", <https://haveibeenpwned.com/API/v3>).

### Plans and prices

The old "Pwned 1 to 5" and "Pwned Ultra" plans were replaced in late March 2026 by **Core**, **Pro** and **High RPM**. Existing subscribers move to the matching new plan at their first renewal after 2 August 2026 `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/15617510034063-What-happened-to-the-old-Pwned-subscription-plans>, <https://www.troyhunt.com/passkeys-k-anonymity-searches-massive-speed-enhancements-bulk-domain-verification-api/>, post dated 30 or 31 March 2026).

All figures below are `[read]` from <https://haveibeenpwned.com/Subscription> as served on 2026-11-26 (the page's own monthly and annual price attributes were checked), in USD, shown as the per-month rate when billed annually. Rate limits are requests per minute (RPM) per key. The page's own text says "Save up to 17% with annual billing".

| Plan | RPM | Per month, billed yearly | Notes |
|---|---|---|---|
| Core 1 | 10 | $4.39 ($52.68/year) | $5.29 if billed monthly. Domain search: 1 domain, up to 25 breached addresses. Includes `/pasteaccount`. |
| Core 2 | 50 | $21.59 ($259.08/year) | $25.99 monthly. Domain search: 3 domains, up to 100 breached addresses. |
| Core 3 | 100 | $36.99 ($443.88/year) | $43.99 monthly. 5 domains, up to 500 addresses. |
| Core 4 | 500 | $159 ($1,908/year) | $189 monthly. 10 domains, unlimited size. |
| Core 5 | 1,000 | $319 ($3,828/year) | $379 monthly. 20 domains, unlimited size. |
| Pro 1 | 1,000 | $379 ($4,548/year) | $449 if billed monthly. 50 domains. Minimum plan for stealer-log website data. |
| Pro 2 | 2,000 | $699 ($8,388/year) | $849 monthly. |
| Pro 3 | 4,000 | $1,299 ($15,588/year) | $1,599 monthly. |
| Pro 4 | 8,000 | $2,499 ($29,988/year) | $2,999 monthly. |
| Pro 5 | 16,000 | $4,599 ($55,188/year) | $5,599 monthly. |
| High RPM 4000 | 4,000 | $1,150 ($13,800/year) | $1,380 monthly. Email search only: the plan page marks "Domain monitoring" and "Stealer log data" as not included. |
| High RPM 8000 / 12000 / 16000 / 24000 | as named | $2,299 / $3,449 / $4,333 / $5,833 | Monthly $2,759 / $4,139 / $5,199 / $6,999. |

- **Core**: direct email search over the API and monitoring of domains you control. "Core plans don't permit domain search on behalf of third parties" `[read]` (<https://haveibeenpwned.com/Subscription>). The same page says "Checking individual email addresses for your own users or customers is permitted on any plan with email search."
- **Pro**: adds customer-domain monitoring, k-anonymity email search, bulk domain verification by API, automatic subdomain verification and stealer-log access `[read]` (<https://haveibeenpwned.com/Subscription>).
- Monthly plans can be cancelled at any time. Charity and education discounts start at Core 4, so they do not help a household `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/13489848213007-Do-you-provide-discounted-subscriptions-for-non-profits-charities-NGOs-and-educational-institutions>).
- Prices are revised each August `[search]` (<https://www.troyhunt.com/passkeys-k-anonymity-searches-massive-speed-enhancements-bulk-domain-verification-api/>).
- **Free domain search**: the plan page lists "Monitor domains with up to 10 breached addresses" under Free, and the plan-limit footnote says only domains with more than 10 breached addresses count toward a plan's domain allowance `[read]` (<https://haveibeenpwned.com/Subscription>). Breaches flagged `IsSubscriptionFree` are searchable on a domain of any size `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/8144327776783-What-subscription-size-do-I-need-to-search-my-domain>). **API access: not included as far as the docs show.** `/breacheddomain` is badged Core and Pro only, and the terms list the "API" and "Domain Name Search" as Paid Services. The Free list also says "Breach monitoring API", which most plausibly means the free catalogue endpoints but is not explained on the page `[read]`. Treat free domain search as dashboard-only.

### Rate-limit behaviour

- Exceeding the limit returns HTTP 429 with a `retry-after` header giving whole seconds to wait (rounded up) `[read]` (<https://haveibeenpwned.com/API/v3>).
- Edge rate-limit responses can contain only a message and may omit `retry-after`, so a client needs its own fallback backoff `[read]` (same page; <https://haveibeenpwned.com/API/Consumers> served the identical page).
- The docs advise not querying "at exactly the rate limit" and adding a short delay `[read]`. The specific example of 95 RPM on a 100 RPM plan is from a support article `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/5744766972431-Why-do-I-keep-getting-HTTP-429-Too-Many-Requests-when-querying-within-the-rate-limit>).
- A missing or invalid key gives HTTP 401 `[read]` (<https://haveibeenpwned.com/API/v3>); keys must be 32-character hex strings.
- **Domain search and the stealer-log domain searches**: no formal rate limit, but "regularly querying it beyond what is practically necessary may result in an HTTP 429", with further defences such as Cloudflare blocks or JavaScript challenges (HTTP 503) `[read]`. The terms repeat that rate limiting "may be added to the domain search API if excessive API requests are made despite no new breaches appearing since the last request" `[read]` (<https://haveibeenpwned.com/TermsOfUse>).

## 2. Acceptable use and terms

Sources are the Terms of Use at <https://haveibeenpwned.com/TermsOfUse> ("last updated on 27 October 2026"; its "summary of changes" box still describes the March 2026 revision) and the acceptable-use and licence sections of <https://haveibeenpwned.com/API/v3>, both `[read]` in full on 2026-11-26. The terms define "Documentation" as the technical specifications and usage requirements on the website and "expressly incorporate" it by reference, so the API page's acceptable-use list is part of the contract `[read]`. HIBP says the terms are the same for every user of the public services and are not negotiable `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/7607875008783-Can-I-make-changes-to-the-terms-of-use>).

### Querying other household members' addresses

- No clause limits email search to addresses the key holder owns `[read]`. Ownership has to be proven only for **domain** search (<https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/TermsOfUse>).
- The terms define the "Permitted Purpose" as "running on-demand queries of email addresses and domain names for breaches and pastes up to a certain rate limit as outlined in the Documentation" `[read]` (<https://haveibeenpwned.com/TermsOfUse>, Definitions). A person may not "access or use our Services or HIBP Data ... for any purpose other than the Permitted Purpose".
- The terms state: "nothing in this clause prevents you, under any Paid Service that includes email address search, from querying individual email addresses supplied by, or relating to, your own users, customers or clients and displaying the results to them within your own product or service (including as part of a paid offering), provided you comply with the restrictions on substantially similar services, solicitation and attribution" `[read]`. The plan page repeats that this is permitted "on any plan with email search" `[read]` (<https://haveibeenpwned.com/Subscription>).
- The barred use, exact wording `[read]`: "use our Services to query email addresses or domains belonging to individuals or organisations in a way that would disadvantage them or be construed as solicitation, including querying email addresses that were not submitted to you by the person who uses them (for example, purchased, scraped or third-party lists) in order to contact or market to them on the basis of the results. Following up with a person who submitted their own address for checking, where this was disclosed at the time of submission, isn't solicitation".
- **Third-party access** `[read]`: "Unless otherwise agreed in writing by us, you must not give a third-party access to your account or Services", and the account holder is "responsible for all activities which occur using your account". Showing results to Subjects inside Unlist is covered by the clause above; handing a Subject, or another household, the key or a login to the Operator's HIBP account is not.
- HIBP's own website lets anyone search any address. Its privacy model rests on hiding sensitive breaches from public search, not on restricting who searches `[read]` (<https://haveibeenpwned.com/privacy>, <https://haveibeenpwned.com/FAQs>).

Reading (not legal advice): an Operator checking Subjects who agreed to it, on the Operator's own key, is inside the terms, provided results are shown to the Subject or Operator with attribution, not used to market to them, and the key stays with the Operator. The terms do not require consent as such, but their solicitation carve-out turns on the address being "submitted ... by the person who uses" it, so recording each Subject's agreement is the safest design (and GDPR may require a basis for it).

### Storing and caching results

- **No clause on storing or caching direct email-search results exists** in the Terms of Use or the API page, both read in full `[read]`. The terms contain no retention, deletion or caching rule for the Core-eligible endpoints. They do say "It is your responsibility to ensure you have appropriate backup measures" and that HIBP is not liable for loss of Subscriber Data.
- The only explicit discard rule concerns the Pro-only k-anonymity search: suffixes that do not match the address being searched must be discarded and "you must not retain, store, aggregate, analyse, or otherwise use those suffixes for any other purpose" `[read]` (<https://haveibeenpwned.com/TermsOfUse>, <https://haveibeenpwned.com/API/v3>). It does not apply to direct email search.
- The terms bar building or running "a breach database, breach search engine or similar service that provides substantially the same functionality as the Services" `[read]` (<https://haveibeenpwned.com/TermsOfUse>). The clause was added in March 2026. A household's stored results for its own Subjects are not that (analysis). A feature that lets anyone look up arbitrary addresses would be, and so would republishing HIBP data as a searchable set.
- The terms also bar making "the Services, your API Key or HIBP Data available to a third party as a product in its own right" `[read]`. Mirroring the catalogue as a public service would fall under this for paid data. For the free catalogue endpoints this restriction is lifted (next section) but the substantially-similar-service ban still applies.
- The breach and paste data is licensed CC BY 4.0, which itself permits copying and storing with attribution `[read]` (<https://haveibeenpwned.com/API/v3>).
- The terms also say the free catalogue endpoints (`/breaches`, `/breach/{name}`, `/latestbreach`, `/dataclasses`) and Pwned Passwords "may be used for any lawful purpose, including within commercial products and for the benefit of third parties" `[read]`.

### Open-source tools where each user supplies their own key

- The paid licence is "non-exclusive, non-transferable and revocable" for the Subscription Period, to use "our API solely via the provided API Key", and is "subject to your ongoing compliance with these Terms and our Documentation" `[read]` (<https://haveibeenpwned.com/TermsOfUse>).
- The terms bar redistributing "your API Key or other login details" to any other party, and bar reselling or sublicensing the services, the key or HIBP data "as a product in its own right" `[read]` (<https://haveibeenpwned.com/TermsOfUse>).
- Troy Hunt's post introducing keys describes this exact case for an open-source script: "users of the script will need to go through the enrolment process to get their own key" (<https://www.troyhunt.com/authentication-and-the-have-i-been-pwned-api/>, 2019).
- The CC BY licence text in the docs says "you're welcome to use the public API to build other services, but you must identify Have I Been Pwned as the source of the data" `[read]` (<https://haveibeenpwned.com/API/v3>).

Reading: an open-source tool that calls the API with the Operator's own key is the supported pattern. A project-wide shared key, or a hosted relay that fronts one key for many households, would breach the terms.

### Automated periodic re-checks

- **No clause prohibits scheduled, automated or periodic queries** `[read]`. The only automation language in the terms is about account creation by bots and about subscription auto-renewal. The Permitted Purpose is "on-demand queries ... up to a certain rate limit", and the per-key limit is the control HIBP documents.
- "On-demand" is **not defined** anywhere in the terms' Definitions `[read]`, so whether HIBP reads it as excluding unattended scheduled polling is a judgement, not a fact. The docs point the other way: they say it is "most efficient to monitor for new breaches before performing other actions", that "issuing queries over and over again when no new breaches have been loaded since the last query is usually sub-optimal", and (for domain search) to "aggressively query the unauthenticated most recent breach API (it's heavily cached at Cloudflare) and once a new breach is seen, query the domain search API for each of your domains" `[read]` (<https://haveibeenpwned.com/API/v3>). That is exactly the design in [Implications](#implications-for-unlist), so a poll-then-recheck loop matches HIBP's own guidance. A tight loop re-querying addresses with no new breach would not.
- The acceptable-use list in the API docs names these as abuse `[read]`: querying the data for purposes intended to harm breach victims; deliberately limiting service availability; deliberately circumventing acceptable-use measures; not properly identifying the user agent; impersonating other user agents; services fraudulently representing the HIBP name or brand; misrepresenting the data source; not adhering to the CC BY licence; **"Automating the consumption of other APIs not explicitly documented on this page"**; bringing HIBP into disrepute (<https://haveibeenpwned.com/API/v3>).

### Attribution and licence

- Breach and paste data is under the **Creative Commons Attribution 4.0 International** licence `[read]` (<https://haveibeenpwned.com/API/v3>, "License - breach & paste APIs").
- "Clear and visible attribution with a link to haveibeenpwned.com should be present anywhere data from the service is used including when searching breaches or pastes and when representing breach descriptions. It doesn't have to be overt" `[read]` (<https://haveibeenpwned.com/API/v3>).
- The terms bar displaying results "to any person other than yourself without clear and visible attribution to Have I Been Pwned, including a hyperlink to haveibeenpwned.com, in accordance with the Creative Commons Attribution 4.0 licence and our brand usage guidelines", and say "Attribution isn't required for Pwned Passwords" `[read]` (<https://haveibeenpwned.com/TermsOfUse>). The breach model also has an `Attribution` field ("Sometimes requested by the party that provides the data to HIBP"); 130 of the 1,055 catalogue entries have a non-null value `[read]`, so show it where present.
- Brand and logo rules are at <https://brand.haveibeenpwned.com/> (not reachable from the research environment; not reviewed).

### User-Agent

- Authenticated endpoints "require both the hibp-api-key and user-agent headers". A missing user agent "can result in an HTTP 403 response" `[read]` (<https://haveibeenpwned.com/openapi.json>, <https://haveibeenpwned.com/API/v3>).
- The value "should accurately describe the nature of the API consumer such that it can be clearly identified in the request", otherwise the request may be blocked. The format shown is `user-agent: [your app name]` `[read]` (<https://haveibeenpwned.com/API/v3>). Impersonating other user agents is listed as abuse.
- The unauthenticated catalogue, data-class and Pwned Passwords endpoints accept requests without it, but identifying the app is recommended `[read]` (<https://haveibeenpwned.com/API/v3>).

## 3. Breach metadata and sensitive breaches

### The breach model

All `[read]` from <https://haveibeenpwned.com/API/v3> unless noted, and checked against the live `/breaches` response (all 1,055 entries carry every field below, including `Attribution` and `DisclosureUrl`). The docs warn that attributes may be added without a new API version, so parsers must ignore unknown fields.

| Attribute | Meaning |
|---|---|
| `Name` | Pascal-cased identifier, unique and **stable**. Use as the key. |
| `Title` | Display name. Can change. |
| `Domain` | "The domain of the primary website the breach occurred on". The docs suggest using it to find other assets tied to that site. |
| `BreachDate` | Date only (ISO 8601). Not always accurate; a guide only. |
| `AddedDate` | When HIBP loaded the breach. `/latestbreach` is ordered by it. |
| `ModifiedDate` | Last change to the record; equals or exceeds `AddedDate`. |
| `PwnCount` | Number of email addresses loaded. |
| `Description` | Description of the incident, as HTML markup (emphasis, strong, hyperlinks). |
| `DataClasses` | Alphabetical string array, e.g. "Email addresses", "Passwords". New classes appear over time. |
| `LogoPath` | URI of a PNG logo. |
| `Attribution` | "Sometimes requested by the party that provides the data to HIBP." Nullable (null on 925 of 1,055 entries). |
| `DisclosureUrl` | Link to disclosure details, or null. |
| `IsVerified` | False means the data may not be from the named site, but HIBP judged much of it legitimate. |
| `IsFabricated` | Data unlikely to be from the named site, though it holds real addresses. |
| `IsSensitive` | Sensitive breach: "Public account and hash-range searches exclude sensitive breaches. Verified-domain searches can return them." 96 of 1,055 entries are flagged. |
| `IsRetired` | Data permanently removed; no longer returned. |
| `IsSpamList` | A spam list, not a security compromise. |
| `IsMalware` | Sourced from a malware campaign, not a compromised service. |
| `IsStealerLog` | Sourced from infostealer logs. Site domains per address are available only through the Pro stealer-log API. |
| `IsSubscriptionFree` | Only affects domain search when the subscription is too small. No effect on email search. |

`GET /breachedaccount/{email}` details:

- `?truncateResponse=false` returns the full breach model. By default only the breach `Name` is returned ("reducing the response body size by approximately 98%") `[read]`, which can then be joined to a locally cached `/breaches` catalogue.
- Unverified breaches are included unless `IncludeUnverified=false`. A `Domain` query parameter filters to one breached domain `[read]`.
- **HTTP 404 means no publicly disclosable result**, with an empty body. The docs say "A 404 does not prove an account has never appeared in a breach" `[read]` (<https://haveibeenpwned.com/API/v3>).
- Paste records carry `Source`, `Id`, `Title`, `Date`, `EmailCount` `[read]` (`Source` values include Pastebin, Pastie, Slexy, Ghostbin, QuickLeak, JustPaste, AdHocUrl, OptOut, PermanentOptOut).

### Is `Domain` enough to link a breach to an Organization?

Mostly, not fully. The API facts above are sourced; the consequences below are analysis.

- It works for the common case: one breached site, one primary domain, matched against an Organization's known domains.
- **It can be empty.** Mozilla Monitor drops breaches where `Domain === ""`, along with retired, spam-list, fabricated and unverified ones `[read]` (<https://github.com/mozilla/blurts-server/blob/main/src/utils/hibp.ts>). In the live catalogue, 55 of 1,055 entries have an empty `Domain` `[read]`: all 6 stealer-log breaches, 7 spam lists (one also flagged malware), 10 malware sets, and 33 others with no such flag that are aggregations, scrapes or leaked databases (5 of the 55 are also flagged sensitive). Some of those 33 are exactly the Broker-like sets Unlist cares about (for example `PDL`, `NationalPublicData`, `Experian2020`, `NotAcxiom`, `MC2Data`, `DataEnrichment`), so an empty `Domain` is a reason for a manual override, not for discarding the breach.
- **No entry carries more than one domain**: no `Domain` value in the catalogue contains a comma or space `[read]`.
- **It is one domain per breach.** An Organization may run several domains, may have been renamed or acquired, or may be defunct. Matching needs registrable-domain comparison against *all* of an Organization's domains, not string equality.
- **The breached party is not always who holds the Listing.** When a vendor or processor is breached, `Domain` names the vendor, and the Subject may never have dealt with it directly.
- **Aggregator and enrichment breaches are the interesting ones for Unlist.** When the breached party is itself a Broker, the breach is direct evidence that a Broker held the Subject's data.
- `IsSpamList`, `IsMalware`, `IsStealerLog` and `IsFabricated` breaches should not be linked to an Organization as a data holder at all.

### Sensitive breaches

- "The public API will not return email addresses from any breaches flagged as sensitive or retired" `[read]` (<https://haveibeenpwned.com/API/v3>). The OpenAPI text for the paid account and k-anonymity searches says the same, so a paid key does not change it.
- A sensitive breach "can only be searched by the verified owner of the email address being searched for", by signing in to the dashboard, which "involves verifying you can receive an email to the entered address" `[read]` (<https://haveibeenpwned.com/FAQs>, <https://haveibeenpwned.com/privacy>). The dashboard sign-in page lists "Searching for your email address in sensitive breaches" `[read]` (<https://haveibeenpwned.com/API/Key>).
- The **domain search API does return sensitive breaches**, because it can only be called after proving control of the domain `[read]` (<https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/privacy>).
- Sensitive breaches still appear in the free `/breaches` catalogue with `IsSensitive: true` (96 of 1,055) `[read]`. Only the per-address membership is withheld.

## 4. Pwned Passwords

- **Range API**: `GET https://api.pwnedpasswords.com/range/{first 5 hex characters of the hash}` `[read]` (<https://haveibeenpwned.com/API/v3>; the hostname is written there, but `api.pwnedpasswords.com` itself is not reachable from the research environment and was not called). The response is one line per hash sharing that prefix: the remaining suffix, a colon, and the number of times it appears (typically about 800 lines). Matching is done locally, so the password and its full hash never leave the machine `[read]`. Pwned Passwords uses 5 characters; the Pro email k-anonymity search uses 6.
- **SHA-1 by default, NTLM with `?mode=ntlm`**; any other `mode` value returns SHA-1. Suffixes are 35 characters for SHA-1 and 27 for NTLM. The prefix is not case-sensitive. Every one of the 16^5 prefixes returns HTTP 200 `[read]` (<https://haveibeenpwned.com/API/v3>).
- **Padding**: send the request header `Add-Padding: true` and every response holds a random number of lines between 800 and 1,000. Padded entries always have a count of 0 and can be discarded. This hides the response size from a network observer `[read]` (<https://haveibeenpwned.com/API/v3>).
- **No key, no rate limit, no licence or attribution requirement**: "There is no rate limit on the Pwned Passwords API", and "there is no licencing or attribution requirements on the Pwned Passwords API, although it is welcomed" `[read]` (<https://haveibeenpwned.com/API/v3>). The OpenAPI text adds that a user-agent header is recommended `[read]`.
- **Terms**: "Pwned Passwords (including the range API and downloadable hash sets) and the unauthenticated breach catalogue endpoints (including /breaches, /breach/{name}, /latestbreach and /dataclasses) may be used for any lawful purpose, including within commercial products and for the benefit of third parties. The third-party, resale and Permitted Purpose restrictions in these Terms don't apply to them; the restriction on building a substantially similar service continues to apply." `[read]` (<https://haveibeenpwned.com/TermsOfUse>)
- **Offline copy**: the official `haveibeenpwned-downloader` is a .NET global tool that fetches every hash range, SHA-1 or NTLM (`--ntlm`), into one file (`--single`) or a directory of range files. It verifies each range against `Content-MD5` and re-downloads only changed ranges on later runs using ETags. It needs the .NET 11 SDK to install `[read]` (<https://github.com/HaveIBeenPwned/PwnedPasswordsDownloader>). The full SHA-1 set is tens of gigabytes `[memory]`. The docs page says the downloader is "freely available from GitHub" `[read]`.

Pwned Passwords checks passwords, not addresses. It matters to Unlist only if Unlist ever handles a Subject's passwords, which a removal tool has no reason to do.

## 5. Alternatives and complements

| Option | Cost and access | Terms | Fit |
|---|---|---|---|
| **HIBP breach catalogue alone** (`/breaches`, `/latestbreach`) | Free, no key | Any lawful purpose; CC BY 4.0 attribution `[read]` (<https://haveibeenpwned.com/TermsOfUse>, <https://haveibeenpwned.com/API/v3>) | Tells which Organizations were breached, when, and what data classes leaked. Says nothing about a given Subject. Works with no key. |
| **HIBP Notify Me and dashboard** | Free per person after email verification | Manual. Automating the website's dashboard would fall under "Automating the consumption of other APIs not explicitly documented" `[read]` (<https://haveibeenpwned.com/API/v3>); that the NotifyMe page itself says so was not found, so this is analysis. Stealer-log entries that captured an address are viewable in the dashboard `[read]` (<https://haveibeenpwned.com/API/Key>) | The only route to a Subject's **sensitive breaches** and **stealer-log sites** without Pro. Each Subject does it themselves. |
| **HIBP domain search** | Free in the dashboard for a domain with up to 10 breached addresses; Core 1 covers 25 `[read]` (<https://haveibeenpwned.com/Subscription>). API access needs a paid plan (see section 1) | Must prove control of the domain `[read]` | For a household with its own mail domain: one call covers every alias and includes sensitive breaches. |
| **Mozilla Monitor** | Free hosted service, per Mozilla account | No public API. "Breach data is powered by haveibeenpwned.com". Code is MPL-2.0 `[read]` (<https://github.com/mozilla/blurts-server>) | A hosted alternative for a Subject, not a data source for Unlist. It calls HIBP's enterprise k-anonymity API with a 6-character SHA-1 prefix and an enterprise key `[read]` (<https://github.com/mozilla/blurts-server/blob/main/src/utils/hibp.ts>), so self-hosting its code does not remove the need for HIBP access. |
| **XposedOrNot** | Free keyless `GET /v1/check-email/{email}`: 2 per second, 25 per hour, 100 per day, per IP. Paid plans from $9/month `[read]` (<https://github.com/XposedOrNot/XposedOrNot-API>) | "The free API above is for personal and low-volume use". API code is MIT. No terms-of-use page or data licence was found | A possible no-cost fallback for Operators without an HIBP key. Its dataset differs from HIBP's and its coverage was not assessed. Sends the full address to a third party. |
| Commercial breach APIs (LeakCheck, DeHashed, Enzoic, SpyCloud) | Paid | Not reviewed | `[memory]` Several return raw leaked credentials, which raises legal and ethical problems. Not recommended. |

HIBP also publishes an MCP server at `https://haveibeenpwned.com/mcp` `[read]` (<https://haveibeenpwned.com/Docs/MCP>). Public breach, data-class and Pwned Passwords tools need no sign-in; address, domain, paste and stealer-log tools need OAuth and follow the normal plan rules. Its own terms were not separately reviewed.

## Implications for Unlist

1. **Make the breach check optional and bring-your-own-key.** The Operator pastes their own HIBP key into the instance. Never bundle, share or relay a key. State the cost plainly in the setup text: Core 1, about US$53 a year.
2. **Ship a keyless mode.** Fetch the free `/breaches` catalogue and flag Organizations the instance already knows that have been breached, with date and data classes. This needs no key and carries the most permissive terms.
3. **Keep key usage tiny and stay close to HIBP's own guidance.** The terms do not define "on-demand" and do not forbid scheduled checks, and the docs recommend monitoring the free latest-breach endpoint and querying only after a new breach is seen. Poll the free `/latestbreach` (or `/breaches`) on a schedule. Re-query each Subject's addresses with the key only when a breach with a newer `AddedDate` appears, plus once when an address is added. Do not re-query addresses on a timer when no new breach has appeared. A household of five with four addresses each is 20 calls, two minutes at 10 RPM.
4. **Respect the rate limit in code.** Throttle to just under the plan's RPM (read it from the subscription status endpoint), honour `retry-after` on 429, and back off with a default when the header is missing.
5. **Send an honest `User-Agent`** naming Unlist and its version on every call, including the keyless ones.
6. **Attribute visibly.** Wherever breach data is displayed, show "Data from Have I Been Pwned" linking to <https://haveibeenpwned.com>, and note CC BY 4.0. If a catalogue snapshot is ever committed to the repository (fixtures, seed data), carry the attribution with it; CC BY data alongside AGPL-3.0 code is fine as long as the attribution is kept.
7. **Store results for the instance's own Subjects only.** The terms impose no storage or retention rule on direct email-search results, so Unlist may keep them. Do not add any feature that looks up arbitrary addresses for people outside the household, that republishes HIBP data as a searchable set, or that gives anyone other than the Operator access to the Operator's HIBP account or key. Never use results to market to Subjects.
8. **Link breaches to Organizations by `Domain`, with overrides.** Compare registrable domains against every domain an Organization is known by. Key stored links on `Name`, not `Title`. Leave breaches flagged spam list, malware, stealer log or fabricated unlinked. A breach with an empty `Domain` is unlinked by default, but allow a manual override, because some Broker-like breaches (for example `PDL`, `NationalPublicData`) have no domain. The Organization List format should allow several domains per Organization and an optional list of HIBP breach `Name`s.
9. **Treat a breach at a Broker as evidence of a Listing.** It is a strong reason to send that Broker an Access Request or Removal Request.
10. **Be honest about blind spots in the UI.** A clean result does not cover sensitive breaches or stealer-log sites. Point each Subject to HIBP's free Notify Me dashboard for those, and suggest domain search to households with their own mail domain.
11. **Disclose the data flow.** A direct email search sends the Subject's full address to HIBP. The k-anonymity search that avoids this starts at US$379 a month. Record each Subject's agreement before their addresses are checked.
12. **Never scrape.** Do not call the website's own search endpoints as a keyless fallback; the acceptable-use rules name "Automating the consumption of other APIs not explicitly documented on this page" as abuse.
13. **Skip Pwned Passwords** unless Unlist starts handling passwords.
14. **Glossary gap.** "Breach" is not yet a term in `GLOSSARY.md`. If this feature goes ahead it needs a definition, and its relation to Organization and Listing settled.

## Open items

State after the 2026-11-26 verification pass. Everything from `haveibeenpwned.com` is now read; what remains is limited to hosts that were not reachable.

- Whether HIBP reads "on-demand" as excluding unattended scheduled polling. The term is undefined in the Terms of Use, so only HIBP can answer; the design in Implications follows its documented guidance. Ask HIBP support if the Operator's instance will poll more often than once per new breach.
- Claims that rest only on `support.haveibeenpwned.com` or `troyhunt.com` (not reachable): no free keys or trials, plan renaming dates (March and 2 August 2026), annual August price revisions, charity-discount threshold, the `IsSubscriptionFree` explanation, the 95 RPM example, the Troy Hunt 2019 open-source key post, the k-anonymity and padding blog posts. These stay `[search]`.
- The brand and attribution guidelines at `brand.haveibeenpwned.com` (not reachable; the terms say attribution must follow them).
- `api.pwnedpasswords.com` was not called (host not allowed); its behaviour is as documented on `haveibeenpwned.com`.
- The full SHA-1 download size (`[memory]`), and XposedOrNot's terms of use and data coverage.
- Prices were read on 2026-11-26 and HIBP revises them each August `[search]`.

## Verification log

Pass of 2026-11-26. Pages read in full: <https://haveibeenpwned.com/TermsOfUse>, <https://haveibeenpwned.com/API/v3> (the `/API/Consumers` URL served an identical page), <https://haveibeenpwned.com/Subscription> (including the per-plan monthly and annual price attributes in its HTML), <https://haveibeenpwned.com/openapi.json>, <https://haveibeenpwned.com/FAQs>, <https://haveibeenpwned.com/privacy>, <https://haveibeenpwned.com/API/Key>, <https://haveibeenpwned.com/Docs/MCP>, and the live `https://haveibeenpwned.com/api/v3/breaches` catalogue (1,055 entries, counted with a script). The Scalar page is a 2.6 KB shell that loads the OpenAPI document, so the OpenAPI document was read instead. No host refused or served a challenge.

Counts (approximate, grouped claims): about 45 confirmed and re-tagged `[read]`; 12 corrected or materially extended (table below); 14 still unverified (list at the end).

### Corrected or materially changed

| Section | Said | Now says | Source |
|---|---|---|---|
| Answer, storage and scheduling | "No clause was found" that forbids storing or scheduled re-checks (excerpt-level) | Confirmed absent in the full terms. "On-demand" is undefined. The docs actively recommend polling `/latestbreach` and re-querying only after a new breach. Added the clause bars giving a third party access to the account or services, and that domain search may be rate limited if queried repeatedly with no new breach | <https://haveibeenpwned.com/TermsOfUse>, <https://haveibeenpwned.com/API/v3> |
| 1, endpoint table, `/pasteaccount` | Badge not seen; Core assumed from memory | Badged Core, Pro, High RPM, so included in Core 1. Needs a real key even for test addresses | <https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/openapi.json> |
| 1, endpoint table, `/breacheddomain`, `/subscribeddomains` | "Core and up" | Badged Core and Pro only (High RPM has no domain monitoring) | same |
| 1, endpoint table, `/stealerlogsbyemail` | Pro 1 and up | Same, plus the address's domain must already be verified on the account | same |
| 1, free domain search | Unknown whether API access is included | Free tier is dashboard monitoring of domains with up to 10 breached addresses; the domain-search API is badged Core and Pro, and the terms list the API and Domain Name Search as Paid Services. Treated as dashboard-only. The Free list's "Breach monitoring API" is unexplained on the page | <https://haveibeenpwned.com/Subscription>, <https://haveibeenpwned.com/TermsOfUse> |
| 1, plans | Only some monthly prices given | All monthly and annual prices added; every previously stated annual figure and RPM was correct | <https://haveibeenpwned.com/Subscription> |
| 2, solicitation | Paraphrase from a search summary | Exact wording quoted, including that following up with a person who submitted their own address, disclosed at submission, is not solicitation | <https://haveibeenpwned.com/TermsOfUse> |
| 2, third parties | Not mentioned | "Unless otherwise agreed in writing by us, you must not give a third-party access to your account or Services." Added to Answer and Implications 7 | <https://haveibeenpwned.com/TermsOfUse> |
| 3, `Attribution` field | "Seen only via third-party mirrors" | Present in the official docs and in all 1,055 live entries; non-null on 130. Show it where present | <https://haveibeenpwned.com/API/v3>, live `/breaches` |
| 3, empty `Domain` | Qualitative | 55 of 1,055 entries are empty, including Broker-like sets (`PDL`, `NationalPublicData`, `Experian2020`, `NotAcxiom`); Implication 8 now allows a manual override | live `/breaches` |
| 3, sensitive breaches | Quote "will not return any accounts" and a source of NotifyMe | Docs wording is "will not return email addresses from any breaches flagged as sensitive or retired"; owner-only search is stated in the FAQs and privacy page; 96 of 1,055 flagged | <https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/FAQs>, <https://haveibeenpwned.com/privacy> |
| 5, Notify Me row | Automating it "would be" undocumented-API abuse, cited to NotifyMe and a Troy Hunt post | The acceptable-use clause supports this, but the NotifyMe page does not say it; relabelled as analysis | <https://haveibeenpwned.com/API/v3> |
| Open items and confidence warning | Said the pages could not be opened | Rewritten for the post-pass state | n/a |

### Confirmed, `[search]` or `[memory]` changed to `[read]`

Base URL; OpenAPI and reference URLs; free status of `/breaches`, `/breach/{name}`, `/latestbreach`, `/dataclasses` and Pwned Passwords; `/breachedaccount` plans; k-anonymity email search plans and 6-character prefix; subscription status path and fields; stealer-log plan; test key value and test addresses; CORS; core plan prices, RPM and domain limits; plan feature split (Core versus Pro); 429 and `retry-after` behaviour including edge responses without it; 401 on missing or invalid key; Terms of Use "last updated 27 October 2026"; Permitted Purpose wording; "your own users, customers or clients" wording; non-redistribution of keys and no resale as a product; "substantially the same" ban; no storage rule other than k-anonymity discard; CC BY 4.0 and the attribution wording; Terms and docs wording that attribution is not required for Pwned Passwords; User-Agent requirement and 403; the breach model and the paste model; `truncateResponse` default (name only); `IncludeUnverified` and `Domain` filters; 404 meaning; sensitive-breach handling in public search and domain search; Pwned Passwords range endpoint and host, SHA-1 default, `mode=ntlm`, suffix lengths 35 and 27, padding header and 800 to 1,000 lines with zero counts; no key, rate limit or attribution for Pwned Passwords; the "any lawful purpose" clause for Pwned Passwords and the catalogue endpoints (and that the catalogue endpoints are named in it); description is HTML.

### Remaining unverified, and why

- Claims whose only source is `support.haveibeenpwned.com` or `troyhunt.com` (host not on the allowed list): no free trials or keys; plan renaming in March 2026 and migration after 2 August 2026; August price revisions; charity and education discount threshold; `IsSubscriptionFree` explanation; the 95 RPM example; that a query-string key does not work; the 2019 open-source-script quote; the padding and SHA-1 blog posts. Left as `[search]`.
- `brand.haveibeenpwned.com` brand and logo rules (host not allowed).
- `api.pwnedpasswords.com` was not called; a request to it was refused by the session's permission layer because the host is not on the allowed list, and was not retried or routed around. Its documented behaviour is read from `haveibeenpwned.com`.
- Full download size of the SHA-1 set `[memory]`; XposedOrNot terms and coverage; commercial breach APIs (not in scope).
- Whether HIBP interprets "on-demand" as excluding unattended scheduled polling: undefined in the terms, so not resolvable by reading.
