# Have I Been Pwned: API terms and pricing for a self-hosted tool

Research for issue #7. Checked on **2026-11-26**.

## Answer

- **A paid key is needed for the one call Unlist cares about.** Looking up a Subject's email address (`breachedaccount`) needs an HIBP key. The cheapest plan, **Core 1, is US$4.39/month billed yearly (US$52.68/year) or US$5.29 month-to-month, at 10 requests per minute**, which is far more than a household needs. There are no free keys or trials.
- **The breach catalogue is free and keyless** (`/breaches`, `/breach/{name}`, `/latestbreach`, `/dataclasses`), as is Pwned Passwords. HIBP's terms let both be used "for any lawful purpose", including for third parties.
- **Bring-your-own-key is the model the terms require.** The terms bar redistributing a key or reselling the service, and allow querying addresses "supplied by, or relating to, your own users, customers or clients". An Operator checking consenting Subjects on their own key fits. Unlist must never ship, share or proxy a key.
- **Breach and paste data is CC BY 4.0.** Unlist must show a visible attribution with a link to haveibeenpwned.com wherever the data appears, and must send an honest `User-Agent` naming the app (a missing one gets HTTP 403).
- **No clause was found that forbids storing results or scheduled re-checks.** The stated control is the rate limit. The terms do bar building a breach search service "substantially the same" as HIBP, and automating undocumented endpoints.
- **`Domain` links most breaches to an Organization, but not all.** It is the breached site's primary domain, one per breach, and is empty for aggregated lists, stealer logs and similar. Match on it first and keep a manual override keyed by the stable `Name`.
- **Sensitive breaches never come back from the email API.** Only the verified address owner (HIBP dashboard) or a verified domain owner (domain search) sees them, so a clean result is not proof of no breach.
- **Stealer-log site lists and privacy-preserving (k-anonymity) email search are Pro only**, from US$379/month, so out of reach for a household.

**Confidence warning.** `haveibeenpwned.com` and `troyhunt.com` could not be opened from the research environment (blocked by its network policy). Everything attributed to those sites below comes from web-search excerpts of the live pages retrieved on 2026-11-26, not from reading the pages in full. See [Verification](#verification) for what that means per claim. Read the Terms of Use in full before shipping.

## Verification

Each claim carries one of these tags.

| Tag | Meaning |
|---|---|
| `[read]` | The source file was fetched and read directly. |
| `[search]` | Taken from search-engine excerpts or summaries of the live page on 2026-11-26. Wording may be paraphrased; the page was not read in full. |
| `[memory]` | Not confirmed in this session. From memory, unverified. |

## 1. Endpoints, plans, prices and rate limits

Base URL is `https://haveibeenpwned.com/api/v3/` `[memory]`. An OpenAPI document is published at <https://haveibeenpwned.com/openapi.json> and a reference at <https://haveibeenpwned.com/scalar/> `[search]`.

### Which endpoints need a key

The API docs mark every endpoint that is not free with badges naming the plans that support it `[search]` (<https://haveibeenpwned.com/API/v3>).

| Endpoint | Key | Plan | Source |
|---|---|---|---|
| `GET /breaches` (whole catalogue) | No | Free | `[search]` <https://haveibeenpwned.com/API/v3> |
| `GET /breach/{name}` (one breach) | No | Free | `[search]` same |
| `GET /latestbreach` (most recently added, by `AddedDate`) | No | Free | `[search]` same |
| `GET /dataclasses` | No | Free | `[search]` same |
| Pwned Passwords `GET /range/{prefix}` | No | Free | `[search]` same |
| `GET /breachedaccount/{email}` | Yes | Core, Pro, High RPM | `[search]` same |
| `GET /pasteaccount/{email}` | Yes ("a subscription key is required, including for test addresses") | Badge not seen; Core assumed `[memory]` | `[search]` <https://haveibeenpwned.com/scalar/> |
| `GET /breachedaccount/range/{prefix}` (k-anonymity email search) | Yes | Pro, High RPM | `[search]` <https://haveibeenpwned.com/scalar/>, <https://www.troyhunt.com/passkeys-k-anonymity-searches-massive-speed-enhancements-bulk-domain-verification-api/> |
| `GET /breacheddomain/{domain}` (domain search; unverified domain gives 403) | Yes | Core and up, own verified domains only | `[search]` <https://haveibeenpwned.com/API/v3> |
| `GET /subscribeddomains` | Yes | Core and up | `[search]` same |
| `GET /stealerlogsbyemail/{email}` (sites where the address's credentials were captured) | Yes | Pro 1 and up | `[search]` same, <https://support.haveibeenpwned.com/hc/en-au/articles/12029246540175-What-stealer-log-information-can-I-access-with-a-Pro-or-High-RPM-subscription> |
| `GET /stealerlogsbywebsitedomain/{domain}`, `/stealerlogsbyemaildomain/{domain}` | Yes | Pro, verified domain, separate unpublished rate limit | `[search]` <https://haveibeenpwned.com/API/v3> |
| Subscription status (returns `SubscriptionName`, `SubscribedUntil`, `Rpm`, `IncludesStealerLogs`, `IncludesKAnon`) | Yes | Core, Pro, High RPM | `[search]` same. Path `subscription/status` is `[memory]`. |

Notes:

- "Authorisation is required for all APIs that enable searching HIBP by email address or domain." The key goes in the `hibp-api-key` request header and does not work as a query-string parameter `[search]` (<https://haveibeenpwned.com/API/v3>).
- A stealer-log corpus is also loaded as an ordinary breach flagged `IsStealerLog`, so a Core key still reports that an address is *in* stealer logs. Only the list of websites needs Pro 1 `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/13868920521103-What-subscription-size-do-I-need-to-use-the-API>). The plan page's "stealer logs are not available on Core" refers to that website list.
- HIBP gives no free trials, sample data or free keys `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/10388846218511-Do-you-provide-free-trials-sample-data-or-free-API-Keys>). A test key works against test addresses on `hibp-integration-tests.com`, such as `account-exists@hibp-integration-tests.com` `[search]` (<https://www.troyhunt.com/hibp-demo-querying-the-api-and-the-free-test-key/>, <https://support.haveibeenpwned.com/hc/en-au/articles/6253088497807-How-can-I-get-troubleshooting-support-for-an-unexplainable-problem-with-the-API>). The all-zeros key value is `[memory]`.
- Authenticated endpoints do not support CORS, so the key must stay server-side `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/7635406134287-Why-do-I-get-a-cross-origin-resource-sharing-CORS-exception-when-calling-an-authenticated-API-from-the-browser>).

### Plans and prices

The old "Pwned 1 to 5" and "Pwned Ultra" plans were replaced in late March 2026 by **Core**, **Pro** and **High RPM**. Existing subscribers move to the matching new plan at their first renewal after 2 August 2026 `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/15617510034063-What-happened-to-the-old-Pwned-subscription-plans>, <https://www.troyhunt.com/passkeys-k-anonymity-searches-massive-speed-enhancements-bulk-domain-verification-api/>, post dated 30 or 31 March 2026).

All figures below are `[search]` from <https://haveibeenpwned.com/Subscription>, in USD, shown as the per-month rate when billed annually. Rate limits are requests per minute (RPM) per key.

| Plan | RPM | Per month, billed yearly | Notes |
|---|---|---|---|
| Core 1 | 10 | $4.39 ($52.68/year) | $5.29 if billed monthly. Domain search: 1 domain, up to 25 breached addresses. |
| Core 2 | 50 | $21.59 | Domain search: 3 domains, up to 100 breached addresses. |
| Core 3 | 100 | $36.99 | |
| Core 4 | 500 | $159 | |
| Core 5 | 1,000 | $319 | |
| Pro 1 | 1,000 | $379 ($4,548/year) | $449 if billed monthly. Minimum plan for stealer-log website data. |
| Pro 2 | 2,000 | $699 | |
| Pro 3 | 4,000 | $1,299 | |
| Pro 4 | 8,000 | $2,499 | |
| Pro 5 | 16,000 | $4,599 | |
| High RPM 4000 | 4,000 | $1,150 ($13,800/year) | Email search only, no domain monitoring. |
| High RPM 8000 / 12000 / 16000 / 24000 | as named | $2,299 / $3,449 / $4,333 / $5,833 | |

- **Core**: direct email search over the API and monitoring of domains you control. No domain search on behalf of third parties `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/15617510034063-What-happened-to-the-old-Pwned-subscription-plans>).
- **Pro**: adds customer-domain monitoring, k-anonymity email search, bulk domain verification by API, automatic subdomain verification and stealer-log access `[search]` (same).
- Monthly plans can be cancelled at any time. Charity and education discounts start at Core 4, so they do not help a household `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/13489848213007-Do-you-provide-discounted-subscriptions-for-non-profits-charities-NGOs-and-educational-institutions>).
- Prices are revised each August `[search]` (<https://www.troyhunt.com/passkeys-k-anonymity-searches-massive-speed-enhancements-bulk-domain-verification-api/>).
- **Free domain search**: a domain with up to 10 breached addresses can be searched with no subscription, for any number of domains. Breaches flagged `IsSubscriptionFree` are searchable on a domain of any size `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/8144327776783-What-subscription-size-do-I-need-to-search-my-domain>). Whether that free tier includes API access or only the dashboard was not confirmed.

### Rate-limit behaviour

- Exceeding the limit returns HTTP 429 with a `retry-after` header giving whole seconds to wait `[search]` (<https://haveibeenpwned.com/API/v3>).
- Some rate-limit responses come from the edge and may omit `retry-after`, so a client needs its own fallback backoff `[search]` (<https://haveibeenpwned.com/API/Consumers>).
- HIBP advises running slightly below the limit, for example 95 RPM on a 100 RPM plan `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/5744766972431-Why-do-I-keep-getting-HTTP-429-Too-Many-Requests-when-querying-within-the-rate-limit>).
- A missing or invalid key gives HTTP 401 `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/5744740926735-Why-do-all-requests-return-HTTP-401-Unauthorised>).

## 2. Acceptable use and terms

Sources are the Terms of Use at <https://haveibeenpwned.com/TermsOfUse> (search excerpt shows "last updated 27 October 2026") and the acceptable-use and licence sections of <https://haveibeenpwned.com/API/v3>. All `[search]`. HIBP says the terms are the same for every user of the public services and are not negotiable (<https://support.haveibeenpwned.com/hc/en-au/articles/7607875008783-Can-I-make-changes-to-the-terms-of-use>).

### Querying other household members' addresses

- No clause was found that limits email search to addresses the key holder owns. Ownership has to be proven only for **domain** search (<https://haveibeenpwned.com/API/v3>).
- The terms define the "Permitted Purpose" as "running on-demand queries of email addresses and domain names for breaches and pastes up to a certain rate limit as outlined in the Documentation" (<https://haveibeenpwned.com/TermsOfUse>).
- The terms state that nothing "prevents you, under any Paid Service that includes email address search, from querying individual email addresses supplied by, or relating to, your own users, customers or clients" and showing them the results, subject to the rules on substantially similar services, solicitation and attribution (<https://haveibeenpwned.com/TermsOfUse>).
- What is barred is querying in ways that disadvantage the people concerned or amount to solicitation, for example checking purchased or scraped lists and then marketing to those people. Paraphrased from a search summary; the exact clause was not retrieved (<https://haveibeenpwned.com/TermsOfUse>).
- HIBP's own website lets anyone search any address. Its privacy model rests on hiding sensitive breaches from public search, not on restricting who searches (<https://haveibeenpwned.com/privacy>, <https://haveibeenpwned.com/FAQs>).

Reading: an Operator checking Subjects who agreed to it, on the Operator's own key, is inside the terms. Consent is not something the HIBP terms were seen to require, but it is the right thing for Unlist to record anyway (and GDPR may require a basis for it).

### Storing and caching results

- **No clause on storing or caching direct email-search results was found** in any excerpt of the terms or the API docs. This is an absence in excerpts, not a confirmed absence in the full text.
- The only explicit discard rule concerns the Pro-only k-anonymity search: results that do not match the address being searched "must be immediately discarded and not stored or further processed" (<https://haveibeenpwned.com/API/v3>).
- The terms bar building or running "a breach database, breach search engine or similar service that provides substantially the same functionality as the Services" (<https://haveibeenpwned.com/TermsOfUse>). A household's stored results for its own Subjects are not that. A feature that lets anyone look up arbitrary addresses would be.
- The breach and paste data is licensed CC BY 4.0, which itself permits copying and storing with attribution (<https://haveibeenpwned.com/API/v3>).

### Open-source tools where each user supplies their own key

- The paid licence is "non-exclusive, non-transferable and revocable" and tied to the key issued to the subscriber (<https://haveibeenpwned.com/TermsOfUse>).
- The terms bar redistributing "your API Key or other login details" to any other party, and bar reselling or sublicensing the services, the key or HIBP data "as a product in its own right" (<https://haveibeenpwned.com/TermsOfUse>).
- Troy Hunt's post introducing keys describes this exact case for an open-source script: "users of the script will need to go through the enrolment process to get their own key" (<https://www.troyhunt.com/authentication-and-the-have-i-been-pwned-api/>, 2019).
- The CC BY licence text in the docs says the public API may be used "to build other services" provided HIBP is identified as the source (<https://haveibeenpwned.com/API/v3>).

Reading: an open-source tool that calls the API with the Operator's own key is the supported pattern. A project-wide shared key, or a hosted relay that fronts one key for many households, would breach the terms.

### Automated periodic re-checks

- No clause prohibiting scheduled queries was found. The Permitted Purpose is bounded by the rate limit, and the per-key limit is the control HIBP documents (<https://haveibeenpwned.com/TermsOfUse>, <https://haveibeenpwned.com/API/v3>).
- The word "on-demand" in the Permitted Purpose was not defined in any excerpt. It is unconfirmed whether HIBP reads it as excluding scheduled polling. A cheap design that avoids the question is in [Implications](#implications-for-unlist).
- The acceptable-use list in the API docs names these as abuse (paraphrased from a search summary): using data to harm breach victims; degrading availability; deliberately circumventing acceptable-use controls; not identifying the user agent accurately or impersonating another; misrepresenting the source of the data; ignoring the CC BY terms; **automating other, undocumented APIs**; conduct that damages the service's reputation (<https://haveibeenpwned.com/API/v3>).

### Attribution and licence

- Breach and paste data is under the **Creative Commons Attribution 4.0 International** licence (<https://haveibeenpwned.com/API/v3>).
- "Clear and visible attribution with a link to haveibeenpwned.com should be present anywhere data from the service is used", including breach or paste search results and breach descriptions. It need not be overt, but the interface showing HIBP data must clearly attribute the source (<https://haveibeenpwned.com/API/v3>).
- The terms require attribution when results are shown to anyone other than yourself, and say "Attribution isn't required for Pwned Passwords" (<https://haveibeenpwned.com/TermsOfUse>).
- Brand and logo rules are at <https://brand.haveibeenpwned.com/> (not reviewed).

### User-Agent

- Authenticated endpoints "require both the hibp-api-key and user-agent headers". A missing user agent can return HTTP 403 (<https://haveibeenpwned.com/scalar/>, <https://haveibeenpwned.com/API/v3>).
- The value "should accurately describe the nature of the API consumer such that it can be clearly identified in the request", otherwise the request may be blocked. The format shown is `user-agent: [your app name]` (<https://haveibeenpwned.com/API/v3>).
- The unauthenticated catalogue, data-class and Pwned Passwords endpoints accept requests without it, but identifying the app is recommended (<https://haveibeenpwned.com/API/v3>).

## 3. Breach metadata and sensitive breaches

### The breach model

All `[search]` from <https://haveibeenpwned.com/API/v3> unless noted. The docs warn that attributes may be added without a new API version, so parsers must ignore unknown fields.

| Attribute | Meaning |
|---|---|
| `Name` | Pascal-cased identifier, unique and **stable**. Use as the key. |
| `Title` | Display name. Can change. |
| `Domain` | "The domain of the primary website the breach occurred on". The docs suggest using it to find other assets tied to that site. |
| `BreachDate` | Date only (ISO 8601). Not always accurate; a guide only. |
| `AddedDate` | When HIBP loaded the breach. `/latestbreach` is ordered by it. |
| `ModifiedDate` | Last change to the record. `[read]` field present in Mozilla's client, see section 5. |
| `PwnCount` | Number of email addresses loaded. |
| `Description` | Description of the incident. Contains HTML markup `[memory]`. |
| `DataClasses` | Alphabetical string array, e.g. "Email addresses", "Passwords". New classes appear over time. |
| `LogoPath` | URI of a PNG logo. |
| `Attribution` | Optional credit for the breach source. Nullable. Seen only via third-party mirrors of the spec. |
| `DisclosureUrl` | Link to disclosure details, or null. |
| `IsVerified` | False means the data may not be from the named site, but HIBP judged much of it legitimate. |
| `IsFabricated` | Data unlikely to be from the named site, though it holds real addresses. |
| `IsSensitive` | Sensitive breach. See below. |
| `IsRetired` | Data permanently removed; no longer returned. |
| `IsSpamList` | A spam list, not a security compromise. |
| `IsMalware` | Sourced from a malware campaign, not a compromised service. |
| `IsStealerLog` | Sourced from infostealer logs. Site domains per address are available only through the Pro stealer-log API. |
| `IsSubscriptionFree` | Only affects domain search when the subscription is too small. No effect on email search. |

`GET /breachedaccount/{email}` details:

- `?truncateResponse=false` returns the full breach model `[search]`. By default only the breach `Name` is returned `[memory]`, which can then be joined to a locally cached `/breaches` catalogue.
- Unverified breaches are included unless `IncludeUnverified=false`. A `Domain` query parameter filters to one breached domain `[search]`.
- **HTTP 404 means no publicly disclosable result**, with an empty body. The docs say this does not prove the address was never breached `[search]` (<https://haveibeenpwned.com/scalar/>).
- Paste records carry `Source`, `Id`, `Title`, `Date`, `EmailCount` `[memory]`.

### Is `Domain` enough to link a breach to an Organization?

Mostly, not fully. The API facts above are sourced; the consequences below are analysis.

- It works for the common case: one breached site, one primary domain, matched against an Organization's known domains.
- **It can be empty.** Mozilla Monitor drops breaches where `Domain === ""`, along with retired, spam-list, fabricated and unverified ones `[read]` (<https://github.com/mozilla/blurts-server/blob/main/src/utils/hibp.ts>). Empty domains are expected for credential-stuffing lists, stealer-log corpora, spam lists and other aggregations that have no single source site.
- **It is one domain per breach.** An Organization may run several domains, may have been renamed or acquired, or may be defunct. Matching needs registrable-domain comparison against *all* of an Organization's domains, not string equality.
- **The breached party is not always who holds the Listing.** When a vendor or processor is breached, `Domain` names the vendor, and the Subject may never have dealt with it directly.
- **Aggregator and enrichment breaches are the interesting ones for Unlist.** When the breached party is itself a Broker, the breach is direct evidence that a Broker held the Subject's data.
- `IsSpamList`, `IsMalware`, `IsStealerLog` and `IsFabricated` breaches should not be linked to an Organization as a data holder at all.

### Sensitive breaches

- "The public API will not return any accounts for a breach flagged as sensitive", nor for retired breaches `[search]` (<https://haveibeenpwned.com/API/v3>). This applies to paid keys too.
- A sensitive breach "can only be searched by the verified owner of the email address", by signing in to the HIBP dashboard, which proves receipt of email at that address `[search]` (<https://haveibeenpwned.com/API/v3>, <https://haveibeenpwned.com/NotifyMe>).
- The **domain search API does return sensitive breaches**, because it can only be called after proving control of the domain `[search]` (<https://haveibeenpwned.com/API/v3>).
- Sensitive breaches still appear in the free `/breaches` catalogue with `IsSensitive: true`. Only the per-address membership is withheld `[memory]`.

## 4. Pwned Passwords

- **Range API**: `GET https://api.pwnedpasswords.com/range/{first 5 hex characters of the hash}`. The response is one line per hash sharing that prefix: the remaining suffix, a colon, and the number of times it appears. Matching is done locally, so the password and its full hash never leave the machine `[search]` (<https://haveibeenpwned.com/API/v3>, <https://www.troyhunt.com/understanding-have-i-been-pwneds-use-of-sha-1-and-k-anonymity/>). The hostname is `[memory]`.
- **SHA-1 by default, NTLM with `?mode=ntlm`**. Suffixes are 35 characters for SHA-1 and 27 for NTLM. The prefix is not case-sensitive. Every one of the 16^5 prefixes returns HTTP 200 `[search]` (<https://haveibeenpwned.com/API/v3>).
- **Padding**: send the request header `Add-Padding: true` and every response holds between 800 and 1,000 lines. Padding lines have a count of 0 and must be discarded. This hides the response size from a network observer `[search]` (<https://haveibeenpwned.com/API/v3>, <https://www.troyhunt.com/enhancing-pwned-passwords-privacy-with-padding/>).
- **No key, no rate limit, no licence or attribution requirement**: "There is no rate limit imposed on the Pwned Passwords API, and there are no licensing or attribution requirements associated with its use" `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/15316377846671-I-wish-to-use-the-Pwned-Passwords-API-How-can-I-get-started>).
- **Terms**: "Pwned Passwords (including the range API and downloadable hash sets) and the unauthenticated breach catalogue endpoints may be used for any lawful purpose, including within commercial products and for the benefit of third parties." The third-party, resale and Permitted Purpose restrictions do not apply; the ban on building a substantially similar service still does `[search]` (<https://haveibeenpwned.com/TermsOfUse>).
- **Offline copy**: the official `haveibeenpwned-downloader` is a .NET global tool that fetches every hash range, SHA-1 or NTLM (`--ntlm`), into one file (`--single`) or a directory of range files. It verifies each range against `Content-MD5` and re-downloads only changed ranges on later runs using ETags. It needs the .NET 11 SDK to install `[read]` (<https://github.com/HaveIBeenPwned/PwnedPasswordsDownloader>). The full SHA-1 set is tens of gigabytes `[memory]`.

Pwned Passwords checks passwords, not addresses. It matters to Unlist only if Unlist ever handles a Subject's passwords, which a removal tool has no reason to do.

## 5. Alternatives and complements

| Option | Cost and access | Terms | Fit |
|---|---|---|---|
| **HIBP breach catalogue alone** (`/breaches`, `/latestbreach`) | Free, no key | Any lawful purpose; CC BY 4.0 attribution `[search]` (<https://haveibeenpwned.com/TermsOfUse>) | Tells which Organizations were breached, when, and what data classes leaked. Says nothing about a given Subject. Works with no key. |
| **HIBP Notify Me and dashboard** | Free per person after email verification | Manual. Automating it would be "automating undocumented APIs" `[search]` (<https://haveibeenpwned.com/NotifyMe>, <https://www.troyhunt.com/experimenting-with-stealer-logs-in-have-i-been-pwned/>) | The only route to a Subject's **sensitive breaches** and **stealer-log sites** without Pro. Each Subject does it themselves. |
| **HIBP domain search** | Free for a domain with up to 10 breached addresses; Core 1 covers 25 `[search]` (<https://support.haveibeenpwned.com/hc/en-au/articles/8144327776783-What-subscription-size-do-I-need-to-search-my-domain>) | Must prove control of the domain | For a household with its own mail domain: one call covers every alias and includes sensitive breaches. |
| **Mozilla Monitor** | Free hosted service, per Mozilla account | No public API. "Breach data is powered by haveibeenpwned.com". Code is MPL-2.0 `[read]` (<https://github.com/mozilla/blurts-server>) | A hosted alternative for a Subject, not a data source for Unlist. It calls HIBP's enterprise k-anonymity API with a 6-character SHA-1 prefix and an enterprise key `[read]` (<https://github.com/mozilla/blurts-server/blob/main/src/utils/hibp.ts>), so self-hosting its code does not remove the need for HIBP access. |
| **XposedOrNot** | Free keyless `GET /v1/check-email/{email}`: 2 per second, 25 per hour, 100 per day, per IP. Paid plans from $9/month `[read]` (<https://github.com/XposedOrNot/XposedOrNot-API>) | "The free API above is for personal and low-volume use". API code is MIT. No terms-of-use page or data licence was found | A possible no-cost fallback for Operators without an HIBP key. Its dataset differs from HIBP's and its coverage was not assessed. Sends the full address to a third party. |
| Commercial breach APIs (LeakCheck, DeHashed, Enzoic, SpyCloud) | Paid | Not reviewed | `[memory]` Several return raw leaked credentials, which raises legal and ethical problems. Not recommended. |

HIBP also publishes an MCP server (<https://haveibeenpwned.com/Docs/MCP>, seen in search results, not reviewed).

## Implications for Unlist

1. **Make the breach check optional and bring-your-own-key.** The Operator pastes their own HIBP key into the instance. Never bundle, share or relay a key. State the cost plainly in the setup text: Core 1, about US$53 a year.
2. **Ship a keyless mode.** Fetch the free `/breaches` catalogue and flag Organizations the instance already knows that have been breached, with date and data classes. This needs no key and carries the most permissive terms.
3. **Keep key usage tiny and avoid the "on-demand" question.** Poll the free `/latestbreach` (or `/breaches`) on a schedule. Re-query each Subject's addresses with the key only when a breach with a newer `AddedDate` appears, plus once when an address is added. A household of five with four addresses each is 20 calls, two minutes at 10 RPM.
4. **Respect the rate limit in code.** Throttle to just under the plan's RPM (read it from the subscription status endpoint), honour `retry-after` on 429, and back off with a default when the header is missing.
5. **Send an honest `User-Agent`** naming Unlist and its version on every call, including the keyless ones.
6. **Attribute visibly.** Wherever breach data is displayed, show "Data from Have I Been Pwned" linking to <https://haveibeenpwned.com>, and note CC BY 4.0. If a catalogue snapshot is ever committed to the repository (fixtures, seed data), carry the attribution with it; CC BY data alongside AGPL-3.0 code is fine as long as the attribution is kept.
7. **Store results for the instance's own Subjects only.** Do not add any feature that looks up arbitrary addresses for people outside the household, or that republishes HIBP data as a searchable set.
8. **Link breaches to Organizations by `Domain`, with overrides.** Compare registrable domains against every domain an Organization is known by. Key stored links on `Name`, not `Title`. Leave breaches with an empty `Domain`, and those flagged spam list, malware, stealer log or fabricated, unlinked. The Organization List format should allow several domains per Organization and an optional list of HIBP breach `Name`s.
9. **Treat a breach at a Broker as evidence of a Listing.** It is a strong reason to send that Broker an Access Request or Removal Request.
10. **Be honest about blind spots in the UI.** A clean result does not cover sensitive breaches or stealer-log sites. Point each Subject to HIBP's free Notify Me dashboard for those, and suggest domain search to households with their own mail domain.
11. **Disclose the data flow.** A direct email search sends the Subject's full address to HIBP. The k-anonymity search that avoids this starts at US$379 a month. Record each Subject's agreement before their addresses are checked.
12. **Never scrape.** Do not call the website's own search endpoints as a keyless fallback; the acceptable-use rules name automating undocumented APIs as abuse.
13. **Skip Pwned Passwords** unless Unlist starts handling passwords.
14. **Glossary gap.** "Breach" is not yet a term in `GLOSSARY.md`. If this feature goes ahead it needs a definition, and its relation to Organization and Listing settled.

## Open items

These could not be confirmed and should be checked against the live pages before the feature ships.

- The full text of <https://haveibeenpwned.com/TermsOfUse>: the exact solicitation clause, the definition of "on-demand", and whether any clause covers storing or caching results.
- Whether `/pasteaccount` is included in Core (badge not seen).
- Whether free domain search (10 or fewer breached addresses) includes API access.
- The default of `truncateResponse`, the subscription status path, the test key value and the Pwned Passwords hostname, all from memory.
- All prices, which HIBP revises each August.
- XposedOrNot's terms of use and data coverage.
