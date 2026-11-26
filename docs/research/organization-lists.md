# Existing EU/UK Organization and Broker lists: can Unlist reuse one?

Research for issue #2. Checked on **2026-11-26**.

## Answer

- **One existing dataset can seed Unlist's official default Organization List: `datenanfragen/data`** (the database behind datarequests.org). It holds 3,069 active records as one JSON file each, with a JSON Schema, and it is **CC0 1.0** (stated in the repository `LICENSE`, on every record page of the live site and on its Open source page), so an AGPL-3.0 project may bundle it, transform it and republish a derived list on any terms. The live site also serves each record as JSON at `https://www.datarequests.org/db/{slug}.json`.
- **Its fields match what Unlist needs.** Every record has a postal address, 2,958 have a privacy email and 216 a web form. Records also carry quirks (identification fields the Organization demands, whether an ID document is needed, preferred transport, free-text notes), a request language, and pointers to request templates in 12 languages. The repo also holds 57 Supervisory Authority records.
- **It is alive but Germany-heavy.** 136 commits landed in the last 12 months. 1,904 records are scoped to Germany, 878 to "all" countries and only 113 to the UK.
- **No list covers EU/UK Brokers well.** No EU or UK Broker registry was found. The Broker lists that exist are US-centric, and the biggest ones (Big Ass Data Broker Opt-Out List, Optery, Privacy Rights Clearinghouse) are **CC BY-NC-SA 4.0**, which cannot go into an AGPL project's official list. datenanfragen marks Broker-like records only through categories (`addresses` 68, `credit agency` 30, `ads` 350).
- **YourDigitalRights.org is not a clean seed.** It claims 41,000+ Organizations, but contact emails are only served through a key-protected API, the data is labelled GPL-3.0, and it is enriched from a Crunchbase snapshot.
- **JustDeleteMe (MIT, 2,671 sites, 6,204 domains) is a useful second list**, for matching domains to Organizations and for account-deletion links. It does not hold privacy contacts.
- **Recommendation:** seed the official list from `datenanfragen/data`, publish Unlist's own list as CC0 so fixes can flow back upstream, and add an Unlist-maintained CC0 overlay for EU/UK Brokers. Treat NC-licensed lists as optional third-party subscriptions at most.
- **Remaining gaps:** a Broker flag, EU/UK Broker coverage, UK and non-German depth, domain keys for matching, per-record "last verified" dates, and personal data inside records.

**Confidence note (updated 2026-11-26 after a verification pass).** The first pass could only reach GitHub. In the second pass these hosts were read: www.datarequests.org, privacyrights.org (including its xlsx download), ico.org.uk (including the dataset zip), www.cnil.fr and www.creativecommons.org, so sections 1, 7 and 13 and the CNIL part of 14 are now primary-source. **yourdigitalrights.org** answered every request with a Cloudflare "Attention Required" challenge (HTTP 403, twice, a few minutes apart), so section 2's live-site claims stay unread. `data.gouv.fr` (the CNIL dataset's actual home), cppa.ca.gov, the other state registries, incogni.com and joindeleteme.com are not reachable, so sections 8, 11 and the licence and column details of 14 stay `[search]` or `[memory]`. `www.gnu.org` could not be read, so MIT and Apache-2.0 compatibility statements stay `[memory]`. See [Verification](#verification), [Could not verify](#could-not-verify) and the [Verification log](#verification-log).

## Verification

Each claim carries one of these tags.

| Tag | Meaning |
|---|---|
| `[read]` | Read directly on 2026-11-26: either in a clone of the project's own GitHub repo, at the commit named in that section (counts computed from the cloned files), or on the publisher's own live page or download, named in that claim. |
| `[search]` | Taken from search-engine excerpts or summaries of a primary page that could not be fetched. Wording may be paraphrased; the page was not read in full. |
| `[memory]` | Not confirmed in this session. From memory, unverified. |
| `[analysis]` | My own licence reasoning. Not legal advice. |

## Comparison

"Bundle" means shipping the data inside Unlist's repo or official list. "Derived list" means republishing a transformed copy as an Organization List. "Runtime" means an instance fetches it from the publisher's URL.

| Dataset | Entries and EU/UK relevance | Contact fields | Format | Freshness | Licence | AGPL-3.0 project may… |
|---|---|---|---|---|---|---|
| [datenanfragen/data](#1-datenanfragendata-datarequestsorg) | 3,069 Organizations under GDPR. DE-heavy; 113 UK-scoped | Privacy email, postal address, web form, phone, fax, PGP, quirks, language, templates | One JSON file per record, JSON Schema | Active; last commit 2026-11-25 | CC0 1.0 | Bundle, derive, runtime. No conditions |
| [YourDigitalRights.org](#2-yourdigitalrightsorg) | "41,000+" Organizations worldwide; ~8,600 of 41,861 domains on EU/UK TLDs | Domain, name, email, privacy policy URL (via API) | Key-protected JSON API; domain-only CSV in repo | Active; last commit 2026-08-14 | Code GPL-3.0; data labelled GPL-3.0; Crunchbase-enriched | Not without asking. Derived list would be GPL-3.0 at best (unsure) |
| [Data Broker Watch](#3-data-broker-watch-databrokerswatchorg) | 770 Brokers, mostly US; site claims 1,000+ | Domain, email, opt-out URL, address | CSV in repo | Repo stale since 2024-09 | GPL-3.0 | Bundle as a separate GPL-3.0 file; data is old |
| [JustDeleteMe](#4-justdeleteme) | 2,671 web services, global | Deletion URL, difficulty, notes, 481 emails, 6,204 domains | Single `sites.json` | Active; last commit 2026-11-24 | MIT | Bundle and derive, keeping the MIT notice |
| [Big Ass Data Broker Opt-Out List](#5-big-ass-data-broker-opt-out-list-badbool) | ~52 Brokers, "primarily U.S.-based" | Opt-out links and emails in prose | One Markdown README | Updated 2026-10-31 | CC BY-NC-SA 4.0 | Not bundle. Third-party subscription at most |
| [Optery directory](#6-optery-data-brokers-directory) | 956 Brokers, overwhelmingly US | Website, email (807), opt-out URL (509), type | JSON, CSV, Markdown | Refreshed 2026-04-21 | CC BY-NC-SA 4.0 | Not bundle. Third-party subscription at most |
| [Privacy Rights Clearinghouse database](#7-privacy-rights-clearinghouse-data-broker-database) | 750 US-registered Brokers | Privacy-policy links, registry contact data | XLSX download, 3,336 registry rows for 750 groups | Collected April 2025 | CC BY-NC-SA 4.0 | Not bundle |
| [US state registries](#8-us-state-broker-registries-california-vermont-texas-oregon) | CA, VT, TX, OR. US law only | Name, email, website, address, opt-out method | CA: CSV. Others: search pages | Annual registration | No licence found | Unverified |
| [Data Rights Protocol / Permission Slip](#9-consumer-reports-permission-slip-and-the-data-rights-protocol) | 9 businesses in the open directory, mostly test entries | API endpoint, technical and business email | JSON | Last commit 2025-12-12 | Spec Apache-2.0; directory has no licence file | Not useful as a seed |
| [DuckDuckGo broker files](#10-duckduckgo-personal-information-removal-broker-files) | 97 US people-search sites | Opt-out URL, scripted scan and opt-out steps | One JSON per Broker | Active; 2026-11-25 | Apache-2.0 | Bundle and derive with attribution; no EU/UK value |
| [Incogni and DeleteMe lists](#11-incogni-and-deleteme-published-lists) | Incogni 420+ Brokers with US/EU/CA tags | Name, website, category only | HTML pages | Maintained | None stated; proprietary | Not reusable |
| [Data Rights Finder](#12-data-rights-finder-uk) | 46 Organizations, 36 UK | DPO and per-right contact email and address | One JSON per Organization | Dead since 2019-07 | ODbL | Bundle as a separate ODbL list; too small and old |
| [ICO register of fee payers](#13-ico-register-of-fee-payers-uk) | All UK fee-paying controllers | Name, address, DPO contact where supplied | Daily dataset download (zipped CSV, about 1.47 million rows) | Daily | OGL v3.0, excluding personal data | Enrichment only; the CSV holds personal data |
| [CNIL DPO list](#14-cnil-list-of-organisations-with-a-dpo-france) | French Organizations with a DPO | DPO contact means: email, URL, phone, address | Open data on data.gouv.fr | "Regularly" | Not confirmed | Unverified; enrichment only |
| [IAB Europe TCF Global Vendor List](#15-iab-europe-tcf-global-vendor-list) | Ad-tech vendors active in the EU/UK | Privacy-policy URL per language; no email | JSON | Weekly | Not confirmed | Unverified |

## Licence reasoning used above

All of this is `[analysis]`.

- An Organization List is a data file fetched from a URL. It is a separate work from Unlist's AGPL-3.0 code, so the list's licence does not have to be AGPL. What matters is whether the project can legally publish the list and whether every Operator can legally use it.
- **CC0** places no conditions. The CC0 text also waives database rights, naming Directive 96/9/EC `[read]` (<https://github.com/datenanfragen/data/blob/b27fb253dce9b8a7d22ba8b92bf2c2c3e4988d00/LICENSE>). Creative Commons' FAQ agrees: CC0 "may be used on databases", waiving "all copyright and related rights in the database and its contents", and "the CC0 Public Domain Dedication is GPL-compatible and acceptable for software" `[read]` (<https://creativecommons.org/faq/>).
- **MIT** and **Apache-2.0** allow bundling and derived lists if the copyright and licence notices travel with the data. Both are compatible with GPLv3-family licences `[memory]`: the FSF licence list at <https://www.gnu.org/licenses/license-list.html> could not be read in the verification pass (host unreachable), so this rests on my recollection of that page and on the permissive texts.
- **GPL-3.0** data may sit beside AGPL-3.0 code, and the two licences allow combining `[read]`: AGPL-3.0 section 13 gives "permission to link or combine any covered work with a work licensed under version 3 of the GNU General Public License into a single combined work", with the GPLv3 part staying under GPLv3 (this repository's `LICENSE`, lines 553-560). A list derived from GPL-3.0 data stays GPL-3.0, so it could not be released as CC0 or merged into a CC0 list `[analysis]`.
- **CC BY-NC-SA 4.0** forbids commercial use and forces the same licence on adaptations. Creative Commons says contributions to BY-NC-SA 4.0 adaptations may only be licensed under BY-NC-SA 4.0 (or later or ported versions) or a "BY-NC-SA Compatible License", and "Currently, no non-CC licenses have been designated as compatible with BY-NC-SA 4.0" `[read]` (<https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/>). Its FAQ adds that a remix "for commercial purposes" cannot incorporate NC material, and that under 4.0 the NC term applies to any use restricted by copyright or database right "even if the database is not publicly shared" `[read]` (<https://creativecommons.org/faq/>). AGPL-3.0 allows commercial use and forbids added restrictions (`LICENSE` line 451, "You may not impose any further restrictions") `[read]`, so NC data cannot be part of the project or its official list `[analysis]`. A household Operator subscribing to a separate, clearly labelled NC list may be non-commercial use, but CC's definition ("primarily intended for or directed toward commercial advantage or monetary compensation") "does not turn on the type of user", CC says it "cannot advise you on what is and is not commercial use", and a commercial host of Unlist could not use it `[read]` (FAQ), `[analysis]` for the application. PRC invites commercial users to ask for other terms (section 7).
- **ODbL** requires a derived database to stay ODbL. Merging ODbL records into the official list would make the whole list ODbL. `[memory]` (the FSF list and the ODbL text were not read in the verification pass).
- Where a page states no licence, assume all rights reserved. Names and domains of Organizations are facts, but the EU database right can protect a substantial extraction from a list even when the facts are free. Unsure how a court would treat any specific case.

## 1. datenanfragen/data (datarequests.org)

Clone of <https://github.com/datenanfragen/data> at commit `b27fb253dce9b8a7d22ba8b92bf2c2c3e4988d00`, dated 2026-11-25.

**What it covers**

- The README describes "a directory of contact information and privacy-related data on companies (and other organizations) under the scope of the EU GDPR", a directory of supervisory authorities, request templates and suggested companies `[read]` (<https://github.com/datenanfragen/data/blob/b27fb253dce9b8a7d22ba8b92bf2c2c3e4988d00/README.md>).
- It only accepts Organizations the GDPR applies to: an EU establishment or deliberate processing of data of people in the EU `[read]` (same README, "Companies we are interested in").
- Counts from the clone `[read]`: 3,069 records in `companies/`, 117 in `obsolete-records/`, 57 in `supervisory-authorities/` (<https://github.com/datenanfragen/data/tree/b27fb253dce9b8a7d22ba8b92bf2c2c3e4988d00/companies>).
- `relevant-countries` counts `[read]`: `de` 1,904, `all` 878, `at` 139, `gb` 113, `ch` 88, `fr` 71, `it` 54, `es` 54, `nl` 48, `be` 35. Every other country has under 30. The schema allows EU and EEA states plus `gb` and `ch` (<https://github.com/datenanfragen/data/blob/b27fb253dce9b8a7d22ba8b92bf2c2c3e4988d00/schema.json>).
- Country in the last address line `[read]`: Germany 2,004, USA 240, UK 184, France 96, Netherlands 80, Ireland 70.
- Categories `[read]`: commerce 505, ads 350, church 320, public body 280, finance 261, entertainment 260, telecommunication 215, school 149, social media 135, travel 129, insurance 120, health 107, utility 76, addresses 68, political party 43, collection agency 42, nonprofit 42, credit agency 30.

**Fields** `[read]` (all from `schema.json`, link above; counts are records with the field set)

- Required: `slug`, `relevant-countries`, `name`, `address`, `sources`, `quality`.
- Contact: `email` 2,958, `address` 3,069, `webform` 216, `phone` 2,208, `fax` 1,303, `web` 2,784, `pgp-fingerprint` 13.
- Quirks: `required-elements` 434 (identification fields the Organization needs), `needs-id-document` 33, `suggested-transport-medium` 2,055 (email 2,010, webform 34, letter 11), `comments` 119.
- Language: `request-language` 789 (de 567, en 216). The README says it is normally left unset `[read]`.
- Templates: `custom-access-template` 505, `custom-erasure-template` 319. Nearly all point at two template families: tracking companies (182 access) and the Protestant church (316 access, 316 erasure).
- `runs` 956: other brands and services the same controller is responsible for.
- `quality`: verified 2,665, scraped 310, tested 94. "Tested" means someone successfully sent a request with the record.
- There is no domain list, no Broker flag and no "last verified" date.

**Request templates** `[read]`

- `templates/` holds 87 text files in 12 languages: de 22, cs 7, en 7, es 7, fr 7, hr 7, it 7, nl 7, el 6, pt 6, sv 3, ro 1 (<https://github.com/datenanfragen/data/tree/b27fb253dce9b8a7d22ba8b92bf2c2c3e4988d00/templates>).
- English has access, erasure, rectification, objection, admonition (reminder), complaint and a tracking-specific access template. They cite Art. 15 and Art. 17 GDPR and use placeholders such as `{id_data}` and `{runs_list}`.

**Company packs** `[read]`

- `company-packs/` has `all.json`, `de.json` and `at.json` only. Germany has an `address-brokers` pack of 13 and `credit-agencies` of 7; Austria has 6 and 4. There is no UK pack (<https://github.com/datenanfragen/data/tree/b27fb253dce9b8a7d22ba8b92bf2c2c3e4988d00/company-packs>).
- Pack changes need archived sources in the commit message, because a listing changes how many requests an Organization receives `[read]` (README, "Company packs").

**Maintenance and freshness** `[read]`

- 136 commits in the 12 months to 2026-11-26, 24 in the last three. 100 were authored as "Community contributions for the Datenanfragen.de project", which are edits suggested through the website.
- 72 records were added in those 12 months. 175 distinct records were touched, leaving aside one bulk phone-format commit (`20655aa`, 495 files). That is about 6% of records per year, so most records have not been rechecked recently.
- CI validates every record against the schema (README, "Testing records").
- Slugs are permanent. Removed records move to `obsolete-records/` with a reason and an optional redirect, so a subscriber can follow acquisitions and mergers (README, "Obsolete records").
- Records may contain personal data, such as an email address containing a person's name (README, "Data sources", pointing to <https://github.com/datenanfragen/data/issues/1287>).

**Format and access**

- Plain JSON files in git `[read]`. The website's deploy script clones this repo and copies records to `static/db`, schemas to `static/` and templates to `static/templates` `[read]` (<https://github.com/datenanfragen/website/blob/92dc2c6/deploy.sh>).
- **Live per-record JSON `[read]`**: `GET https://www.datarequests.org/db/{slug}.json` returns HTTP 200 `application/json` with the same fields as the repo record (checked on `1und1`: `slug`, `relevant-countries`, `categories`, `name`, `runs`, `address`, `phone`, `fax`, `email`, `web`, `sources`, `suggested-transport-medium`, `quality`). Every company page links to its JSON and to "suggest a change" (<https://www.datarequests.org/company/1und1/>). There is no directory index: `/db/` returns 404, so bulk access means the git repo or fetching each slug. Slugs come from the live listing <https://www.datarequests.org/company/>.
- The live listing holds 3,127 distinct company slugs, which is the 3,069 active records plus 58 of the 117 `obsolete-records` (checked against the clone at `b27fb25`), so the website still lists some obsolete entries `[read]`.
- Search on the site runs on a Typesense server at `search.datenanfragen.de` `[read]` (<https://github.com/datenanfragen/website/blob/92dc2c6/src/Utility/search.ts>). Its terms for third-party use were not found: the live site has no terms page for the data (`/license`, `/about`, `/license-notices` all return 404; "License notices" links to the Open source page).

**Licence**

- `LICENSE` is CC0 1.0 Universal `[read]` (link above).
- "by contributing, you agree for your work to be released under a Creative Commons CC0 1.0 Universal license" `[read]` (README, "Contributing").
- "we warmly welcome you to use the data for your own projects!" `[read]` (README, first paragraph).
- The website string for record pages reads "This database is licensed under a CC0 1.0 Universal license." `[read]` (<https://github.com/datenanfragen/website/blob/92dc2c6/src/i18n/en.json>, key `cdb-cc0-explanation`). The live record page carries that exact text linked to <https://creativecommons.org/publicdomain/zero/1.0/deed.en> `[read]` (<https://www.datarequests.org/company/1und1/>).
- The live Open source page lists the repositories with their licences: "data CC0 — The data behind the project. This includes our company and supervisory authority databases but also the sample letters", while the website, backend and letter generator are MIT `[read]` (<https://www.datarequests.org/open-source/>).
- The live Contribute page says new companies are submitted through the site, corrections through a "suggest a change" button on each company page, or directly through the GitHub repository, and a country is officially supported once the database holds ten companies from it. It states no licence for contributions; the CC0 contribution rule is the README's `[read]` (<https://www.datarequests.org/contribute/>).
- Verdict `[analysis]`: bundle, derived list and runtime fetch are all allowed with no conditions. Attribution is not required but is good manners.

## 2. YourDigitalRights.org

Clone of <https://github.com/your-digital-rights/yourdigitalrights.org> at commit `16e6159`, dated 2026-08-14. The live site and API were not reachable. In the verification pass <https://yourdigitalrights.org/>, `/terms` and `/privacy` each returned HTTP 403 with a Cloudflare "Attention Required!" challenge page, on two attempts a few minutes apart. Nothing was routed around, so its live data licence, API and terms remain unread.

**What it covers**

- A service by the nonprofit Conscious Digital that sends erasure and access requests under GDPR, CCPA and other laws `[read]` (<https://github.com/your-digital-rights/yourdigitalrights.org/blob/16e6159/README.md>).
- The About page strings claim "41,000+ Companies in our database" and "1,000+ Data brokers tracked through DataBrokersWatch.org" `[read]` (<https://github.com/your-digital-rights/yourdigitalrights.org/blob/16e6159/lang/en.json>, keys `about.stat3*`, `about.stat4*`).
- The repo contains `prod-domains.csv` with 41,861 domains and no other column `[read]`. 5,877 are on `.co.uk`, `.uk` or `.org.uk`, and about 8,600 in total are on EU or UK country TLDs. Most are `.com` (21,388) (<https://github.com/your-digital-rights/yourdigitalrights.org/blob/16e6159/prod-domains.csv>). The file arrived in a commit titled "chore: commit all local changes" (`e798807`, 2026-02-14) and no code references it, so it looks accidental.

**Fields and API** `[read]`

- The site reads Organizations from `https://api.yourdigitalrights.org/domains` and `/domains/<domain>`, sending an `X-API-Key` header (<https://github.com/your-digital-rights/yourdigitalrights.org/blob/16e6159/src/utils/domains.js>).
- The front end uses `name`, `url`, `email`, `privacyPolicy`, `description`, `headquarters`, `industries` and similar profile fields. Records are keyed by bare domain. No postal address, web form, language or quirk field was seen.
- An older route, `/api/companies`, reads a Google Sheet and returns `name`, `email`, `url`, `searchTerms` (<https://github.com/your-digital-rights/yourdigitalrights.org/blob/16e6159/src/pages/api/companies.js>). Whether it still works was not checked.
- Request templates (erasure, access, reminder, escalation) live in the code, not the data (<https://github.com/your-digital-rights/yourdigitalrights.org/tree/16e6159/src/email-templates>).

**Maintenance** `[read]`

- 127 commits in the 12 months to 2026-11-26. Organizations can be added through a form on the site (commit `16e6159` message).
- The About page thanks Crunchbase "for providing a snapshot of their company database which we use to enrich our list of organizations" `[read]` (`lang/en.json`, line 87).

**Licence**

- The repo `LICENSE` is GPL-3.0 `[read]` (<https://github.com/your-digital-rights/yourdigitalrights.org/blob/16e6159/LICENSE>).
- The `/api/companies` route wraps its payload as `{"License": "GNU General Public License v3.0", "Organizations": [...]}` `[read]` (`companies.js`, link above). That is the only statement found about the data's licence.
- No published terms for the keyed domains API were found in the repo.
- Verdict `[analysis]`, unsure: the full contact data is not published as a file, the API needs a key, and part of the data comes from Crunchbase, whose terms may limit redistribution. Do not bundle or scrape it. If Conscious Digital agrees to share an export, it would most likely be GPL-3.0, which cannot be merged into a CC0 list.

## 3. Data Broker Watch (databrokerswatch.org)

Clone of <https://github.com/your-digital-rights/data-brokers> at commit `e87edeb`, dated 2024-09-18. Same publisher as YourDigitalRights.org.

- `backend/data/data-brokers-merged.csv` has 770 rows with columns including `Domain`, `Categories`, `Privacy Policy`, `Opt-Out Method`, `Opt Out URL`, `Phone Number`, `US Only`, `Email`, `Name`, `Address` `[read]` (<https://github.com/your-digital-rights/data-brokers/tree/e87edeb/backend/data>).
- The inputs are a California registry snapshot (433 rows, "Date Added" values from 2020), a privacyrights.org sheet, and Clearbit and email-spider merges `[read]` (same folder and `backend/notebooks`).
- The last commit is a dependency bump from September 2024 `[read]`. The live site may be fresher than the repo; this was not checked.
- Licence: GPL-3.0 `[read]` (<https://github.com/your-digital-rights/data-brokers/blob/e87edeb/LICENSE>).
- Verdict `[analysis]`: usable as a separate GPL-3.0 file, but the data is US-focused and years old. Clearbit-derived columns may carry their own restrictions (unsure).

## 4. JustDeleteMe

Clone of <https://github.com/jdm-contrib/jdm> at commit `b75bc14`, dated 2026-11-24.

- "A directory of direct links to delete your account from web services" `[read]` (<https://github.com/jdm-contrib/jdm/blob/b75bc14/README.md>).
- `_data/sites.json` holds 2,671 entries `[read]` (<https://github.com/jdm-contrib/jdm/blob/b75bc14/_data/sites.json>).
- Fields `[read]`: `name`, `url` (deletion page), `difficulty` (easy 1,354, hard 852, medium 272, impossible 178, limited 15), `domains` (6,204 in total), `notes` (2,246), `email` (481), `email_subject` (78), `email_body` (112), plus per-language `url_xx` and `notes_xx` (<https://github.com/jdm-contrib/jdm/blob/b75bc14/CONTRIBUTING.md>).
- The emails are account-deletion or support addresses, not privacy or DPO contacts. There is no postal address, jurisdiction or GDPR field.
- It is global with no EU/UK flag. `limited` marks sites that only delete for people covered by a privacy law `[read]` (CONTRIBUTING.md).
- 369 commits in the 12 months to 2026-11-26 `[read]`.
- Licence: MIT, "Copyright (c) 2013-2020 Robb Lewis, The JDM Contrib Team, & various contributors" `[read]` (<https://github.com/jdm-contrib/jdm/blob/b75bc14/LICENSE>).
- Verdict `[analysis]`: bundle or derive freely, keeping the MIT notice. Best used as a second list that maps domains to Organizations and offers a self-service deletion link before a Removal Request is sent.

## 5. Big Ass Data Broker Opt-Out List (BADBOOL)

Clone of <https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List> at commit `5e85266`, dated 2026-10-31.

- A single `README.md` of prose, with about 52 entries (count of `###` headings) under People Search Sites, Special Circumstances and marketing opt-outs `[read]` (<https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List/blob/5e85266/README.md>).
- "this list is primarily U.S.-based since it is a volunteer project based in the U.S." `[read]` (same file). The words "GDPR" and "Europe" do not appear. The Acxiom entry gives links for France, Italy and Spain and an email for Austria, Germany and Switzerland.
- Each entry gives find-yourself and opt-out links, sometimes an email or phone number, and notes on ID demands and fees. Nothing is machine-readable.
- "started in September 2017 and was most recently updated on October 31, 2026" `[read]`. One person maintains it and takes corrections by email or pull request.
- Licence: CC BY-NC-SA 4.0 `[read]` (<https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List/blob/5e85266/LICENSE.md>).
- Verdict `[analysis]`: cannot be bundled or turned into part of the official list. A hand-converted list would itself have to be CC BY-NC-SA and credited.

## 6. Optery data brokers directory

Clone of <https://github.com/optery/optery-data-brokers-directory> at commit `b32a893`, dated 2026-04-21.

- 956 Brokers in `data/data-brokers.json`, also as CSV and Markdown `[read]` (<https://github.com/optery/optery-data-brokers-directory/tree/b32a893/data>).
- Fields with counts `[read]`: `title` and `website` 956, `type` 953, `email` 807, `opt_out_url` 509, `description` 450, `opt_out_guide_url` 118, `optery_support_tier`.
- Types `[read]`: People Search Site 386, Marketing 285, B2B Lead Generation 127, Business Search 72, Profile Data Broker 46, Phone Directory 37.
- There is no country or jurisdiction field. "gdpr" appears 8 times in the whole file and `.co.uk` 7 times, so it is overwhelmingly US `[read]`.
- "Generated on: 2026-04-21"; maintained by Optery, a commercial removal service `[read]` (<https://github.com/optery/optery-data-brokers-directory/blob/b32a893/README.md>).
- Licence: CC BY-NC-SA 4.0, "For commercial licensing inquiries, contact: support@optery.com" `[read]` (<https://github.com/optery/optery-data-brokers-directory/blob/b32a893/LICENSE.md>).
- Verdict `[analysis]`: same as BADBOOL. Technically the easiest Broker file to convert, but it could only ever be an optional third-party list under BY-NC-SA.

## 7. Privacy Rights Clearinghouse Data Broker Database

Read on 2026-11-26 from <https://privacyrights.org/data-brokers>, <https://privacyrights.org/resources-tools/reports/why-are-hundreds-data-brokers-not-registering-states> (posted 20 June 2025, with the Electronic Frontier Foundation) and the spreadsheet it links, <https://privacyrights.org/sites/default/files/2025-05/Data_Broker_Full_Registry_2025.xlsx.xlsx> (673,814 bytes; parsed as untrusted data, not executed).

- It merges registry data collected in early April 2025 from five registries: California Privacy Protection Agency, California Attorney General (legacy, 2019-2024), Vermont, Texas and Oregon, into 750 unique Broker groups `[read]`. So "five state registries" means four states plus California's two registries. The report notes California's registry alone had grown by nearly 100 registrations, to 522, by publication.
- **Download**: one XLSX with a sheet "Data Brokers" (3,336 registry rows, 750 distinct `GroupUUID_Combined` values) and a sheet "About_this_export" `[read]`. Rows per `RegistrySource`: Oregon 1,060, Vermont 981, California AG 549, California CPPA 496, Texas 250 (more rows than unique Brokers per registry; this is why the per-state counts below, from search, could not be matched).
- **Columns** `[read]`: `GroupUUID_Combined`, `Name`, `RegistrySource`, `WebsiteURL`, `PrivacyPolicyURL`, `OptOutURL`, `AlternateOptOutURLs`, `AdditionalWebsiteURL`, `Email`, `Phone`, `ContactPerson`, `ContactPersonTitle`, `AlternateContactPersons`, `Address`, `AddressLine4`, `City`, `County`, `State`, `ZipCode`, `Country`, `DataCategories`, and tri-state `Collects*` flags (Names, Addresses, DOB, POB, MMN, BiometricData, SSNGovID, OtherInfo, MinorsData, ReproductiveHealthData, EmploymentData, NetworkData, CommercialData; 1 collects, 0 does not, 2 not mentioned). Populated: `Email` 2,449 rows, `OptOutURL` 1,583, `PrivacyPolicyURL` 1,900.
- **Licence** `[read]`: "We're making this entire database freely available under Creative Commons CC-BY-NC-SA 4.0 licensing for researchers, policymakers, advocates, and the public. Please credit Privacy Rights Clearinghouse when using this data. For commercial uses or if the CC-BY-NC-SA 4.0 license terms don't work for your specific implementation, please reach out to us directly through our contact form." The site footer also says content is CC BY-NC-SA 4.0 unless otherwise noted.
- **Scope**: no EU/UK scope. `Country` is United States on 2,988 rows, blank on 346, Singapore 1, Canada 1 `[read]`.
- The per-state counts quoted in section 8 (Vermont 441, Texas 226, Oregon 275) are not on these pages and stay `[search]`.
- Verdict `[analysis]`: not bundleable because of NC. A commercial-use grant could be requested, but nothing in the data would help with EU/UK contacts.

## 8. US state Broker registries (California, Vermont, Texas, Oregon)

None reachable. All `[search]` unless tagged.

- **California.** The California Privacy Protection Agency publishes the registry with a "Download CSV" button, and each entry has contact information and request metrics (<https://cppa.ca.gov/data_broker_registry>). A 2020 snapshot of the older Attorney General registry, kept in the Data Broker Watch repo, has the columns `Data Broker Name`, `Email Address`, `Website URL`, `Physical Address` and how to opt out under the CCPA `[read]` (<https://github.com/your-digital-rights/data-brokers/blob/e87edeb/backend/data/data-brokers-california.csv>). BADBOOL says California's DROP portal now reaches "500+ registered data brokers" with one request `[read]` (BADBOOL README).
- **Vermont.** Brokers register yearly with the Secretary of State and give name, physical, email and web addresses and their opt-out method (<https://sos.vermont.gov/corporations/other-services/data-brokers>, <https://legislature.vermont.gov/statutes/section/09/062/02446>). PRC counted 441 registered in April 2025 `[search]`; its spreadsheet has 981 Vermont rows, so the figures are not comparable without more reading.
- **Texas and Oregon.** Both run searchable registries (<https://www.sos.texas.gov/statdoc/data-brokers.shtml>, <https://dfr.oregon.gov/business/licensing/data-broker-registry>). PRC counted 226 and 275 in April 2025. No bulk download was found.
- These registries exist because of US state law. A US Broker with no EU/UK activity is outside GDPR, and the opt-out routes listed are CCPA-style, not Art. 15 or Art. 17 contacts.
- No licence or reuse terms were found for any of them.
- Verdict `[analysis]`, unsure: usable as a checklist of Broker names to research, since the same groups (Acxiom, Experian, Oracle and so on) often have EU/UK entities. Not a source of EU/UK contacts.

## 9. Consumer Reports Permission Slip and the Data Rights Protocol

Clones of <https://github.com/datarightsprotocol/data-rights-protocol> at `ca1f837` (2025-08-08) and <https://github.com/datarightsprotocol/drp-service-directory> at `ef850c5` (2025-12-12).

- The Data Rights Protocol is an API specification for sending rights requests to businesses, now at version 1.0 `[read]` (<https://github.com/datarightsprotocol/data-rights-protocol/blob/ca1f837/README.md>).
- It "encodes the rights as specified in the California Consumer Privacy act"; GDPR is left to "future iterations" `[read]` (same file, sections 1.02 and 3.01).
- It is a closed network. Agents and businesses are listed in two JSON directories run by the operators, and the earlier `/.well-known/data-rights.json` discovery endpoint was removed `[read]` (same file, section on the security model and changelog).
- The directory holds 9 business entries and 4 agents. Most businesses are OneTrust or Transcend test instances; real ones include Home Depot, Wendy's and Dentsu `[read]` (<https://github.com/datarightsprotocol/drp-service-directory/tree/ef850c5/businesses>).
- Fields: `id`, `name`, `api_base`, `supported_actions`, `web_url`, `technical_contact`, `business_contact` `[read]` (<https://github.com/datarightsprotocol/drp-service-directory/blob/ef850c5/README.md>).
- Licence: the spec is Apache-2.0 `[read]`. The directory repo has no licence file `[read]`.
- Permission Slip's own list of Organizations is not published. Consumer Reports says it has identified over 100 Brokers `[search]` (<https://innovation.consumerreports.org/introducing-permission-slip-plus>).
- Verdict `[analysis]`: nothing to seed from. Worth watching as a future transport that could replace email for some Organizations.

## 10. DuckDuckGo Personal Information Removal broker files

Blobless clone of <https://github.com/duckduckgo/apple-browsers> at commit `b5d698d`, dated 2026-11-25.

- 99 JSON files, 97 of them real Brokers, under `SharedPackages/DataBrokerProtectionCore/Sources/DataBrokerProtectionCore/BundleResources/JSON/` `[read]` (<https://github.com/duckduckgo/apple-browsers/tree/b5d698d/SharedPackages/DataBrokerProtectionCore/Sources/DataBrokerProtectionCore/BundleResources/JSON>).
- Each file has `name`, `url`, `optOutUrl`, `mirrorSites`, scripted `steps` for scanning and opting out, and a `schedulingConfig` with re-scan intervals `[read]`.
- All are US people-search sites. No file name uses an EU or UK country domain `[read]`.
- Licence: Apache-2.0, "Copyright (c) 2025 Duck Duck Go, Inc." `[read]` (<https://github.com/duckduckgo/apple-browsers/blob/b5d698d/LICENSE.md>).
- Verdict `[analysis]`: licence-compatible, but it describes web-form automation for US sites. Useful later as a model for parent and mirror-site relationships and re-check intervals.

## 11. Incogni and DeleteMe published lists

Not reachable. All `[search]`.

- Incogni publishes a table with Name, Website, Data sensitivity, Category and Coverage columns, where Coverage holds region codes such as `US/EU/CA` (<https://blog.incogni.com/data-brokers-incogni-covers/>). Incogni's blog cites 420+ Brokers. No contact details are in the table.
- DeleteMe's help pages list supported countries, including the UK and several EU states, and refer to a "country-specific data broker list" (<https://help.joindeleteme.com/hc/en-us/articles/15250115925011-DeleteMe-International-for-Businesses>). No public per-country list was found.
- No licence was found on either. Assume all rights reserved.
- Verdict `[analysis]`: not reusable as data. Incogni's EU-tagged rows are the best public hint of which Brokers a commercial service treats as EU-relevant, so they can guide what Unlist researches independently.

## 12. Data Rights Finder (UK)

Clone of <https://github.com/datarightsfinder/data> at commit `569c81c`, dated 2019-07-26.

- 46 JSON records named by company number: 36 `gb`, plus a few from Sweden, the US, Ireland, Austria, Denmark and Luxembourg `[read]` (<https://github.com/datarightsfinder/data/tree/569c81c>).
- A joint project of Open Rights Group and IF, funded by the ICO, that started with financial services `[search]` (<https://www.openrightsgroup.org/press-releases/online-tool-helps-public-find-out-how-data-is-being-used-by-fintech-companies/>).
- Fields `[read]`: organisation name, company number and country, privacy notice URL, `dataProtectionOfficer` with postal and email contact, and a `rights` block with separate contact details and observations for access, rectification, erasure, restriction, portability and objection, plus data categories collected.
- No commit since July 2019 `[read]`.
- Licence: "All contributions are licensed under the Open Database License" `[read]` (<https://github.com/datarightsfinder/data/blob/569c81c/README.md>). There is no licence file.
- Verdict `[analysis]`: too small and old to seed from. Its per-right contact model is a good schema reference.

## 13. ICO register of fee payers (UK)

Read on 2026-11-26 from <https://ico.org.uk/about-the-ico/what-we-do/register-of-fee-payers/>, <https://ico.org.uk/about-the-ico/what-we-do/register-of-fee-payers/download-the-register/> and the dataset it links, <https://ico.org.uk/media2/cfnc5zdf/register-of-data-controllers-2026-11-25.zip> (78.6 MB zip, one 282 MB CSV, parsed as untrusted data, not executed).

- The ICO publishes the controller's name and address, registration reference, level of fee paid, registration and expiry dates, other trading names, and "the contact details for the Data Protection Officer (DPO) if we have been told of one. The DPO name will also be published if they have consented to this." There are "more than one million fee payers" `[read]`.
- **Download**: "The dataset is updated daily. If you are re-using the information, use the latest version." `[read]` The file name carries the date (2026-11-25).
- **Licence** `[read]`: "The data is made available under the terms of the ICO's copyright and re-use statement. While the dataset is available for re-use under the Open Government Licence, the licence does not apply to personal data in the dataset. When processing any personal data, please be aware of your obligations under the General Data Protection Regulation and Data Protection Act." The site footer names Open Government Licence v3.0 for text content.
- **Columns** `[read]`: `Registration_number`, `Organisation_name`, `Organisation_address_line_1` to `_5`, `Organisation_postcode`, `Public_authority`, `Start_date_of_registration`, `End_date_of_registration`, `Trading_names`, `Payment_tier`, `DPO_or_Person_responsible_for_DP_` with `Title`, `First_name`, `Last_name`, `Organisation`, `Email`, `Phone`, `Address_line_1` to `_5`, `Postcode`, and `Public_register_entry_URL`.
- **Size and fill** `[read]`: 1,469,678 rows; 131,014 have a DPO email, 49,131 name a DPO or responsible person, 446,411 list trading names, 51,724 are public authorities. Payment tier: Tier 1 1,339,171, Tier 2 123,120, Tier 3 7,387.
- **Personal data is in the file itself**: many rows are sole traders whose `Organisation_name` is a person's name and whose address is a home address (the first rows are examples), beyond the named DPO fields.
- Verdict `[analysis]`: a possible enrichment source for UK postal addresses and DPO emails, but only 9% of rows carry a DPO email, it is too large to be a default list, and any named person's details are outside the OGL grant. An Operator-side lookup (fetch, filter on demand, do not republish) is safer than bundling.

## 14. CNIL list of organisations with a DPO (France)

Partly read. <https://www.cnil.fr/fr/opendata> (its "Open CNIL" page) was read on 2026-11-26; the dataset's own page on data.gouv.fr is not reachable, so licence and columns are still unconfirmed.

- The Open CNIL page lists the dataset as "Délégué(e)s à la protection des données (DPD/DPO): Liste des organismes disposant d'un DPO et coordonnées publiques" and links to <https://www.data.gouv.fr/fr/datasets/organismes-ayant-designe-un-e-delegue-e-a-la-protection-des-donnees-dpd-dpo/> `[read]`. It says the CNIL's open data, "publiées sur le portail data.gouv.fr, sont accessibles et réutilisables gratuitement" `[read]`. No licence name appears on the CNIL page.
- That the data holds the name and professional contact details of organisations that have designated a DPO, with email, URL, phone or postal address as declared, remains `[search]` (<https://www.data.gouv.fr/datasets/5c926a7a634f410578005c68>).
- The licence is therefore still not confirmed. French public open data normally uses the Licence Ouverte `[memory]`.
- Verdict `[analysis]`, unsure: a strong candidate for enriching French Organizations. Check the licence and columns on the data.gouv.fr dataset page first. Other regulators may publish similar DPO registers; none was checked.

## 15. IAB Europe TCF Global Vendor List

- The list is published as JSON at `https://vendor-list.consensu.org/v3/vendor-list.json` `[read]` (<https://github.com/InteractiveAdvertisingBureau/GDPR-Transparency-and-Consent-Framework/blob/master/TCFv2/IAB%20Tech%20Lab%20-%20Consent%20string%20and%20vendor%20list%20formats%20v2.md>).
- Each vendor has a `urls` array with `langId`, `privacy` (privacy-policy URL) and `legIntClaim`, plus data-retention periods `[read]` (same spec). There is no email or postal address.
- The spec says consent tools must load the list server-side, not directly from client code `[read]`. The reuse terms and vendor count were not confirmed.
- Verdict `[analysis]`, unsure: a current roster of ad-tech Organizations active in the EU/UK, many of them Brokers in Unlist's sense. Useful for finding gaps in the `ads` category, not for contacts.

## Smaller or dead ends

- **PrivacyBot** (<https://github.com/privacybot-berkeley/privacybot>, commit `62e89b7`, 2021-10-01): a CSV of about 466 US Brokers and people-search sites with a privacy email and the identifiers each needs. The README says "PROJECT NO LONGER SUPPORTED" and there is no licence file `[read]`. Not reusable.
- **visible-cx/databroker_remover** (<https://github.com/visible-cx/databroker_remover>, commit `6af72a9`, 2025-12-09): MIT tool that emails "60+ data brokers". The repo lists 58 Broker names; the email addresses are supplied through configuration, not committed `[read]`.
- **My Data Done Right** (Bits of Freedom, mydatadoneright.eu): an EU request generator with its own database of Organizations `[search]` (<https://www.bitsoffreedom.nl/2018/10/25/my-data-done-right-launched/>). No public data repo was found; Bits of Freedom's GitHub organisation shows only archived, unrelated repos `[read]` (<https://github.com/bitsoffreedom>).
- **PersonalData.IO wiki** (<https://wiki.personaldata.io>): a Wikibase about personal data and Organizations `[search]`. Its contact coverage and licence were not found.

## Recommendation

1. **Seed the official default Organization List from `datenanfragen/data`.** It is the only source that is EU-scoped, machine-readable, maintained and free of licence conditions. Map `email`, `address`, `webform`, `required-elements`, `needs-id-document`, `suggested-transport-medium`, `request-language`, `comments`, `runs` and `quality` straight across. Keep `slug` as the stable upstream ID and follow `obsolete-records` redirects.
2. **Publish Unlist's official list as CC0, not AGPL.** `[analysis]` The list is data, not part of the program. CC0 keeps it mergeable with upstream, whose contribution terms require CC0, so corrections Unlist Operators make can be offered back to datenanfragen. Any other licence on Unlist's list would block that.
3. **Rebuild from upstream on a schedule instead of forking once.** Fetch the git repo, convert, and publish. Upstream changes weekly, and its slugs and obsolete-record mechanism make diffs safe.
4. **Reuse the request templates.** The Art. 15 and Art. 17 templates in `templates/` are CC0 and exist in 12 languages. They are a ready starting point for Access Requests and Removal Requests.
5. **Reuse the Supervisory Authority records.** The 57 records in `supervisory-authorities/` are CC0 and cover the Complaint path.
6. **Maintain a separate CC0 "EU/UK Brokers" overlay inside the Unlist project.** Start from datenanfragen's `addresses` (68) and `credit agency` (30) records and the German and Austrian `address-brokers` packs, mark them as Brokers, then add researched UK and other national Brokers with sources.
7. **Offer a JustDeleteMe-derived list (MIT) as an optional second subscription** for domain matching and self-service deletion links.
8. **Do not bundle BADBOOL, Optery or PRC data.** If Operators ask for US Brokers, document how to subscribe to a third-party conversion under CC BY-NC-SA, and keep it out of the project's own files.
9. **Ask before touching YourDigitalRights data.** Its domain coverage (41,861 domains, about 5,900 UK) would fill datenanfragen's biggest hole, but only a written grant from Conscious Digital would make it usable, and GPL-3.0 data would need to stay in its own list.

## Gaps that remain

- **Broker flag.** No reusable EU dataset says "this Organization is a Broker". datenanfragen's categories are, by its own schema, "purposefully fairly vague". Unlist has to curate this itself.
- **EU/UK Broker coverage.** No EU or UK registry of Brokers was found `[search]`. A March 2026 market study published by the European Data Protection Board is focused on Brokers operating in Belgium (<https://www.edpb.europa.eu/our-work-tools/our-documents/support-pool-experts-projects/data-brokers-market-study_en>) `[search]`; it was not read.
- **Country depth outside Germany.** 62% of datenanfragen records are scoped to Germany. The UK has 113 scoped records and no company pack. France, Italy, Spain and the Netherlands have 48 to 71 each.
- **Domain keys.** datenanfragen has one `web` URL per record (2,784 of 3,069) and no domain list, so matching a sender domain or a breach to an Organization is weak. JustDeleteMe and YourDigitalRights are both keyed by domain.
- **Freshness per record.** There is no "last verified" field. Unlist would have to derive it from git history, and only about 6% of records were touched in the last year.
- **Unverified records.** 310 records are `scraped`, which the site itself flags as unverified. Unlist should mark or exclude them.
- **Personal data in the list.** Some records hold named people's addresses. Redistributing them makes each list publisher answerable for that data. The upstream guidance is in issue #1287.
- **Web-form-only Organizations.** Only 216 records have a web form and 34 prefer it. Organizations that refuse email need a manual step that no list automates for the EU/UK.

## Could not verify

State after the 2026-11-26 verification pass. Resolved: PRC licence, download format and columns (section 7); ICO columns, licence wording and download (section 13); live datarequests.org JSON and licence (section 1); the "fifth" PRC registry (California has two); the GPL-3.0 and AGPL-3.0 combining statement (now read from the AGPL text).

- **yourdigitalrights.org.** Every request got a Cloudflare challenge (HTTP 403). The live data licence, API terms and Crunchbase terms are unread. Whether the "GPL v3" label on the old `/api/companies` payload is the intended licence for the whole dataset, whether that route still responds, and what terms govern the keyed domains API: ask Conscious Digital.
- **CNIL DPO dataset.** The licence name and column list are on data.gouv.fr, which is not reachable. Only the CNIL's "freely reusable" statement was read.
- **Other non-GitHub sites not on the pass's allowed list**: the CPPA registry CSV header, entry count and terms of use; the Vermont, Texas and Oregon registries; Incogni's and DeleteMe's terms; PRC's per-state counts (441, 226, 275), which are `[search]` and do not match the spreadsheet's row counts.
- **datarequests.org.** No terms of use for the per-record JSON or for the Typesense search server were found on the live site; the CC0 licence on the data is stated, but there is no published rate-limit or usage policy. Prefer the git repository for bulk use.
- **Whether databrokerswatch.org is fresher than its repo.**
- **"No EU/UK Broker registry exists."** This is an absence of search results plus one secondary blog saying so, not a check of each member state's law.
- **Licence compatibility statements tagged `[memory]`.** www.gnu.org could not be read (connection reset three times, then no DNS resolution from the fetch tool), so the claims that MIT and Apache-2.0 are compatible with GPLv3-family licences and the ODbL share-alike reading are still from memory and my own reading. Creative Commons' pages were read and confirm the NC and SA statements, and the AGPL text confirms GPLv3 combination. Get a licence review before shipping third-party data other than CC0.
- **My Data Done Right and PersonalData.IO.** Neither could be opened. Whether either publishes reusable contact data is unknown.
- **IAB Global Vendor List terms and size.**
- **Other national DPO registers** (beyond the ICO and CNIL) were not searched for.

## Verification log

Pass of 2026-11-26. Read: <https://www.datarequests.org/> (home, `/company/`, a record page and its JSON, `/contribute/`, `/open-source/`), <https://privacyrights.org/data-brokers>, the PRC report page and its XLSX, <https://ico.org.uk/about-the-ico/what-we-do/register-of-fee-payers/> and `/download-the-register/` and the dataset zip, <https://www.cnil.fr/fr/opendata>, and (for licence compatibility) <https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/> and <https://creativecommons.org/faq/>. **<https://yourdigitalrights.org/> was unreachable**: HTTP 403 with a Cloudflare "Attention Required!" challenge page on `/`, `/terms` and `/privacy`, repeated after a wait. **<https://www.gnu.org/> was unreachable** (connection closed mid-exchange three times; the fetch tool could not resolve the host). Neither was routed around. The datarequests.org live company listing was compared with a shallow clone of `datenanfragen/data` at `b27fb25`. Downloads were parsed as data, never executed.

Counts (approximate, grouped claims): about 9 confirmed, 15 corrected or extended (table below), about 12 still unverified (list below and "Could not verify").

| Section | Said | Now says | Source |
|---|---|---|---|
| Answer, bullet 1; section 1 licence | CC0 from the repo only | Also confirmed on the live site: record pages say "This database is licensed under a CC0 1.0 Universal license" and the Open source page lists "data CC0". Recommendation unchanged | <https://www.datarequests.org/company/1und1/>, <https://www.datarequests.org/open-source/> |
| 1, format and access | Per-record JSON under `/db/` "inferred from the deploy script, not observed" | Observed: `https://www.datarequests.org/db/{slug}.json` returns 200 JSON; `/db/` has no index (404) | <https://www.datarequests.org/db/1und1.json> |
| 1, counts | 3,069 records | Repo count confirmed; the live listing shows 3,127 slugs = 3,069 active + 58 obsolete records still listed | <https://www.datarequests.org/company/> vs clone |
| 1, contribution and terms | Terms for third-party use not checked | Contribute page read (submit form, "suggest a change", GitHub; ten companies to support a country); no terms or licence page for the data or search server exists on the site (404s) | <https://www.datarequests.org/contribute/> |
| 2, YourDigitalRights live site | Not reachable | Still unreadable: Cloudflare challenge, 403 | <https://yourdigitalrights.org/> |
| 7, PRC licence and download | `[search]`; "format unverified"; columns not found | Read. CC BY-NC-SA 4.0 with a commercial-contact route; XLSX with 3,336 rows, 750 groups, 34 columns (listed in section 7) incl. `Email`, `OptOutURL`, `PrivacyPolicyURL`; US-only addresses. Verdict (not bundleable) unchanged | <https://privacyrights.org/resources-tools/reports/why-are-hundreds-data-brokers-not-registering-states> and its XLSX |
| 7/8, "the fifth registry was not identified" | Four found | Five registry sources are named: CA CPPA, CA Attorney General (legacy), VT, TX, OR | same |
| 8, Vermont "441 counted by PRC" | `[search]` | Still `[search]`; the spreadsheet's Vermont row count is 981, so the numbers are not comparable | PRC XLSX |
| 13, ICO | `[search]`; columns and DPO email unconfirmed | Read. 26 columns including `DPO_or_Person_responsible_for_DP_Email`; 1,469,678 rows, 131,014 with a DPO email; OGL with the explicit carve-out "the licence does not apply to personal data in the dataset"; the file itself contains sole traders' names and home addresses. Recommendation: enrichment by on-demand lookup only | <https://ico.org.uk/about-the-ico/what-we-do/register-of-fee-payers/download-the-register/>, dataset zip |
| 14, CNIL | `[search]`; licence not confirmed | CNIL's page read: dataset exists on data.gouv.fr and CNIL open data is "accessibles et réutilisables gratuitement". Licence name and columns are on data.gouv.fr, unreachable. Dataset URL corrected to the slug the CNIL page links | <https://www.cnil.fr/fr/opendata> |
| Licence reasoning, GPL-3.0 with AGPL-3.0 | `[memory]` | `[read]` from AGPL-3.0 section 13 | repository `LICENSE` |
| Licence reasoning, CC0 | CC0 text from repo | Also CC's FAQ: CC0 on databases waives all rights; GPL-compatible | <https://creativecommons.org/faq/> |
| Licence reasoning, CC BY-NC-SA 4.0 | Reading from memory | Confirmed and sharpened: no non-CC licence is compatible with BY-NC-SA 4.0; commercial remix cannot include NC material; NC applies even to private use of a database under 4.0; NC turns on purpose, not user type, and CC will not advise, so "household use is non-commercial" is weaker than the file said | CC compatible-licences page and FAQ |
| Licence reasoning, MIT and Apache-2.0 vs GPLv3 family | `[memory]` | Still `[memory]`; gnu.org unreadable | n/a |
| Licence reasoning, ODbL | analysis | Still analysis; flagged `[memory]` | n/a |
| Confidence warning, Verification table, Could not verify | Said only GitHub was reachable | Rewritten for the post-pass state | n/a |

### Remaining unverified, and why

- yourdigitalrights.org: live data licence, API, terms (Cloudflare challenge). Crunchbase terms.
- data.gouv.fr (CNIL DPO dataset licence and columns): host not on the allowed list.
- cppa.ca.gov, Vermont, Texas and Oregon registries, incogni.com, joindeleteme.com, databrokerswatch.org freshness, mydatadoneright.eu, wiki.personaldata.io, the EDPB market study, IAB terms: hosts not on the allowed list.
- gnu.org license list: MIT, Apache-2.0 and ODbL compatibility with AGPL-3.0 stay from memory and my reading.
- Typesense search terms and any rate limit for datarequests.org `/db/` (none published on the pages read).
