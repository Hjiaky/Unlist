# Username-check datasets Unlist can use, and their licences

Research for issue #8. Researched 2026-11-26 from shallow clones of the upstream repositories (commit hashes below). Nothing from those repositories was executed and no live username checks were run, so every accuracy figure here is the upstream project's own claim or a count taken from its files. Licence conclusions are a reading of the licence texts, **not legal advice**. Verification pass 2026-11-26: Creative Commons' compatible-licences page, FAQ and 2015 announcement were read in full; the FSF licence list at gnu.org could not be read (see [Verification log](#verification-log)).

## Answer

1. **Use Sherlock's `data.json` as the first subscribed list, fetched at runtime with a bundled snapshot as fallback.** It is MIT (the data file has no separate licence), has the simplest schema (URL template plus one of three detection methods), covers 481 well-known sites, flags 19 as NSFW, and publishes a daily machine-generated list of entries that currently give false positives (45 on 2026-11-25), which Unlist can subscribe to as well.
2. **WhatsMyName closed on 2026-11-09.** Its `wmn-data.json` (691 sites, CC BY-SA 4.0) is frozen at that date and its own README says accuracy will now decay. It is still the strictest schema (a positive *and* a negative signature per site), so it is worth supporting as an optional, unmodified, fetched list, but it cannot be the primary source.
3. **Maigret's `data.json` is the freshest and largest (11,640 entries, MIT, 69 commits to the file in the last 30 days) and the best second list**, but its schema is the most complex (30 shared "engines", activation hooks, protection tags) and most entries are small forums. Import the ranked top-N subset rather than all of it.
4. **Licences:** MIT data (Sherlock, Maigret) may be bundled, converted and fetched freely if the copyright and permission notice is kept. CC BY-SA 4.0 data (WhatsMyName) may be fetched at runtime or bundled *unmodified as a separately licensed file*; a converted or merged copy that Unlist publishes must itself be CC BY-SA 4.0 and cannot be folded into the AGPL-3.0 code.
5. **Write Unlist's own small checker rather than shelling out.** The tools are Python, default to dossier-building behaviour (Maigret extracts profile data and searches recursively by default), and run 20 to 100 parallel requests, which is more than a household self-check from a home IP needs.
6. **Model every result as three states: account exists, no account, unknown.** All three projects document that bot protection (Cloudflare, AWS WAF, captchas), rate limits and site redesigns turn into false results if "unknown" is not separated out.
7. **No project documents the target sites' terms of service.** Maigret documents that home broadband gives good results and datacenter IPs the worst; none documents bans of residential IPs. Keep concurrency low and offer the check per Subject on demand, not on a schedule.
8. Avoid Blackbird (conflicting licence files, the newer one non-commercial), NExfil (unmaintained since 2023) and socialscan (11 platforms, probes registration endpoints) as data sources.

## Comparison

Counts are from the files at the commits listed under "Sources".

| Project | Code licence | Site-data licence | Data file | Entries | Detection in the data | NSFW marking | Last commit seen | Data freshness |
|---|---|---|---|---|---|---|---|---|
| Sherlock | MIT | MIT (same `LICENSE`, no separate data licence) | `sherlock_project/resources/data.json` | 481 | `errorType`: `status_code` 327, `message` 127, `response_url` 27 | `isNSFW: true` on 19 | 2026-11-01 | Last change to the file 2026-05-04; 12 commits to it in 12 months; exclusions list regenerated daily |
| WhatsMyName | none (data-only repo) | CC BY-SA 4.0 | `wmn-data.json` | 691 | Status code **and** body string, for both "exists" and "missing" | `cat: "xx NSFW xx"` on 39 | 2026-11-09 (project closed) | Frozen 2026-11-09; 104 commits to the file in the 12 months before |
| Maigret | MIT | MIT (same `LICENSE`) | `maigret/resources/data.json` | 11,640 (744 disabled) | Effective `checkType`: `message` 7,401, `status_code` 4,144, `response_url` 95 | Tags `porn` 33, `erotic` 14, `webcam` 8; `dating` 48 | 2026-11-25 | 69 commits to the file in 30 days; release v0.6.7 on 2026-11-21 |
| social-analyzer | AGPL-3.0 | AGPL-3.0 (same `LICENSE`) | `data/sites.json` | 999 | Lists of strings with a 0-100 score; shared detections for wiki/forum software | `nsfw: "true"` on 40 | 2026-11-08 | File last changed 2022-05-23 |
| Blackbird | Conflicting: `.github/LICENSE` is CC BY-NC-SA 4.0, `docs/LICENSE` is GPLv3 | Uses WhatsMyName data (CC BY-SA 4.0), downloaded at runtime | none of its own for usernames | 691 via WhatsMyName | WhatsMyName's | WhatsMyName's | 2026-11-03 | Depends on the frozen WhatsMyName file |
| NExfil | MIT | MIT | `src/nexfil/url_store.json` | 328 | `test`: none 204, `string` 64, `redirect` 21, `headless` 18, others | none | 2023-09-30 | Unmaintained |
| user-scanner | MIT | MIT (sites are Python modules, not data) | `user_scanner/user_scan/**.py` | 2,550 username modules | Hand-written Python per site | `adult` directory | 2026-11-25 | Very active |
| socialscan | LICENSE is MPL 2.0 (`setup.py` classifier says MIT) | n/a (code only) | `socialscan/platforms.py` | 11 platforms | Queries registration endpoints | none | 2024-01-20 | Dormant |
| Naminter | MIT | Uses WhatsMyName data | none of its own | 691 via WhatsMyName | WhatsMyName's | WhatsMyName's | 2026-08-14 | Depends on the frozen WhatsMyName file |

## Recommendation in detail

### Which dataset

| Criterion | Sherlock | WhatsMyName | Maigret |
|---|---|---|---|
| Schema simplicity | Simplest: 4 required fields | Simple: 8 required fields, flat | Complex: engines, activation, protection, mirrors |
| Licence fit with AGPL-3.0 | MIT, no constraints beyond the notice | CC BY-SA 4.0: fine unmodified, share-alike on derived data | MIT |
| Freshness | Moderate (file last changed 2026-05-04) plus daily exclusions | Frozen 2026-11-09 | Daily |
| Built-in defence against false positives | Weakest: 68% of entries rely on status code alone | Strongest: both signatures required | Strong: `message` with presence and absence strings, plus an `errors` map |
| Size for a home-IP self-check | 481 | 691 | 11,640, of which 1,156 carry a rank |

Sherlock wins on schema and licence, WhatsMyName on per-entry strictness, Maigret on freshness. Since WhatsMyName is frozen, the practical order is Sherlock first, Maigret's ranked subset second, WhatsMyName as an optional frozen extra.

### Internal model

Design Unlist's internal site-check record as a superset that all three map onto, so each upstream file is read by a small importer and none is a hard dependency:

- URL template shown to the Operator, optional separate probe URL, method, headers, body.
- Optional username regex (Sherlock `regexCheck`, Maigret `regexCheck`), to skip sites where the name is not valid.
- "Exists" signature and "missing" signature, each an optional status code and optional body strings.
- "Unknown" markers (Maigret `errors`, Sherlock's WAF fingerprints).
- NSFW flag, category, protection tags, a known-existing username for self-test.

This fits the glossary's existing **Organization List** idea (a file published at a URL that an instance subscribes to). The glossary has no term yet for the username check or for a site-check entry; that is a gap to resolve with the domain-modeling step, not something decided here.

### Reuse options per licence (my reading)

| Option | Sherlock / Maigret (MIT) | WhatsMyName (CC BY-SA 4.0) | social-analyzer (AGPL-3.0) | Blackbird |
|---|---|---|---|---|
| Fetch at runtime from upstream URL | Allowed | Allowed; Unlist distributes nothing, so no sharing conditions are triggered for the project | Allowed | n/a |
| Bundle the file unmodified | Allowed; keep the MIT copyright and permission notice | Allowed as a separately licensed file with attribution; do not label it AGPL | Allowed (same licence) | Avoid |
| Bundle a converted or merged copy | Allowed; result can be AGPL-3.0 with the MIT notice kept | Result is Adapted Material and must be CC BY-SA 4.0; cannot be relicensed AGPL-3.0 | Allowed under AGPL-3.0 | Avoid |
| Convert in memory on the Operator's machine | Allowed | Allowed; nothing is shared | Allowed | n/a |
| Shell out to the installed tool | Allowed | n/a (no tool) | Allowed | Possible if the Operator installs it; do not redistribute |

Reasoning:

- **MIT.** The licence allows use, copy, modification and sublicensing provided "the above copyright notice and this permission notice" are included. Neither Sherlock nor Maigret has a separate licence for the data file, so the repository `LICENSE` covers it. Keep `Copyright (c) 2019 Sherlock Project` and `Copyright (c) 2020-2026 Soxoj` with the MIT text next to any bundled copy.
- **CC BY-SA 4.0, unmodified.** Section 3(a) attribution applies when the material is shared: keep the creator identification, copyright notice, licence notice and a link, and say whether it was modified. The file already carries its own `license` and `authors` arrays. ShareAlike (Section 3(b)) applies only "if You Share Adapted Material You produce". Adapted Material is material "derived from or based upon the Licensed Material and in which the Licensed Material is translated, altered, arranged, transformed, or otherwise modified". A data file sitting unmodified next to AGPL code that reads it is, in my reading, not that. CC's FAQ supports the reading on sharing: "the condition only applies if a work is modified and if the work is shared publicly", and a compilation of SA-licensed items need not itself be SA-licensed while "each individual work is still licensed individually under an SA license" `[read]` (<https://creativecommons.org/faq/>, "If CC SA-licensed content is included in a database, does the entire database have to be licensed under an SA license?"). The AGPL's own aggregate clause says "Inclusion of a covered work in an aggregate does not cause this License to apply to the other parts of the aggregate" (`LICENSE` lines 229-231 in this repository). Section 2(a)(5)(C) forbids imposing extra terms on the licensed material, so the bundled file must be marked CC BY-SA 4.0, not AGPL.
- **CC BY-SA 4.0, modified.** A converted, corrected or merged list is Adapted Material. Section 3(b)(1): "The Adapter's License You apply must be a Creative Commons license with the same License Elements, this version or later, or a BY-SA Compatible License." Section 4(b) reaches the same result for databases: including "all or a substantial portion of the database contents" in your own database makes that database Adapted Material. Creative Commons lists GPLv3 as a one-way compatible licence for BY-SA 4.0: it was "declared a 'BY-SA-Compatible License' for version 4.0 on 8 October 2015", and "compatibility with the GPLv3 is one-way only, which means you may license your contributions to adaptations of BY-SA 4.0 materials under GPLv3, but you may not license your contributions to adaptations of GPLv3 projects under BY-SA 4.0. Other special considerations apply." `[read]` (<https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/>). CC's FAQ adds that the mechanism "is designed for situations in which content is integrated into software code in a way that makes it difficult or impossible to distinguish the two" `[read]` (<https://creativecommons.org/faq/>), which is not the case for a separate JSON file. The page lists only BY-SA 4.0 itself, ported versions, the Free Art License 1.3 and GPLv3 as permitted licences for adaptations, and "Evaluated licenses not deemed compatible: None yet". **AGPL-3.0 is not on the list**, so there is no CC-declared route to AGPL-3.0. A two-step route exists on paper: relicense the adaptation as GPLv3, then rely on AGPL-3.0 section 13, which gives "permission to link or combine any covered work with a work licensed under version 3 of the GNU General Public License into a single combined work" and keeps the GPLv3 part governed by GPLv3 `[read]` (`LICENSE` lines 553-560 in this repository). That would still leave the list under GPLv3, not AGPL-3.0, and whether CC's "special considerations" are met for a data file is untested, so I would not rely on it. The safe form is: publish any derived list as its own CC BY-SA 4.0 file, separate from the code.
- **Name.** The pre-closure WhatsMyName README (commit before `abcb19d`) said the licence "does not grant rights to the WhatsMyName name or logo", asked for the credit "Uses data from the WhatsMyName project (CC BY-SA 4.0)", and said naming a product "WhatsMyName" needs permission. That section was dropped from the final README, but the credit wording is a sensible default.
- **Provenance.** Whether Sherlock's or Maigret's MIT data contains entries copied from WhatsMyName's CC BY-SA data was not checked (**unverified**). Maigret's docs say it "started as a fork of Sherlock" (`docs/source/philosophy.rst`), which is MIT to MIT.

### Why not shell out

- Sherlock and Maigret are Python packages; shelling out adds a Python runtime and a second update channel to a home-server install.
- Maigret's defaults go beyond a self-check: `settings.json` has `"recursive_search": true`, `"info_extracting": true`, `"max_connections": 100`, `"top_sites_count": 500`. They can be turned off, but the defaults would have to be overridden on every call.
- Sherlock fetches its manifest from `https://data.sherlockproject.xyz` and its exclusions from GitHub on every run unless `--local` is passed (`sherlock_project/sites.py`), so the Operator's instance would phone out anyway.
- The detection logic that the data needs is small: roughly 80 lines in Sherlock (`sherlock_project/sherlock.py` lines 376-456) and four numbered steps in the WhatsMyName README.

## Per-project detail

### Sherlock (`sherlock-project/sherlock`)

Source: commit `c588d7c8b476df9f9c84912a05d1430fb8cdcdae`, committed 2026-11-01.

- **Licence.** `LICENSE` begins "MIT License / Copyright (c) 2019 Sherlock Project". `pyproject.toml` has `license = "MIT"`. No separate licence for the data file.
- **Data file.** `sherlock_project/resources/data.json`, schema in `sherlock_project/resources/data.schema.json` ("Sherlock Target Manifest"). An object keyed by site name. Required per entry: `url` (template with `{}`), `urlMain`, `errorType`, `username_claimed`. Optional: `urlProbe`, `regexCheck`, `isNSFW`, `headers`, `request_method` (GET, POST, HEAD, PUT), `request_payload`, `errorMsg`, `errorCode`, `errorUrl`, `tags`, `__comment__`.
- **Counts.** 481 entries. `errorType`: `status_code` 327, `message` 127, `response_url` 27. `regexCheck` on 95, `urlProbe` on 52, `isNSFW` on 19, POST on 3. The README says "400+ social networks" (`docs/README.md`).
- **Detection** (`sherlock_project/sherlock.py` lines 262-456):
  - `message`: the account is reported as existing unless one of the `errorMsg` strings is in the body.
  - `status_code`: reported as existing unless the status is in `errorCode` or outside 200-299. Uses a HEAD request by default.
  - `response_url`: redirects are disabled; a 2xx response means the account exists.
  - All three assume "exists" unless a "missing" signal is seen, so a block page that returns 200 reads as an account. To counter that there is a `WAF` result state driven by four hard-coded fingerprints (two Cloudflare, one AWS CloudFront WAF, one PerimeterX), with the comment "As WAFs advance and evolve, they will occasionally block Sherlock and lead to false positives and negatives."
  - Result states: `Claimed`, `Available`, `Unknown`, `Illegal` (name fails `regexCheck`), `WAF` (`sherlock_project/result.py`).
- **Accuracy on record.**
  - A daily GitHub Actions job (`.github/workflows/exclusions.yml`, cron `0 5 * * *`) checks every site with random usernames and writes the sites that still report an account to `false_positive_exclusions.txt` on the `exclusions` branch. The client removes those sites unless `--ignore-exclusions` is passed ("may return more false positives"). On 2026-11-25 the list held 45 of 481 sites, including Reddit, Spotify, Linktree, HackerNews, DeviantArt and Archive.org. The job runs from GitHub's datacenter runners, so the list reflects what breaks from there.
  - `docs/removed-sites.md` records 131 removed sites with reasons. Examples: "As of 2021-06-27, Steam uses captcha through CloudFlare which prevents us from checking if usernames exists on the site."; "As of 2021-11-30, TM-Ladder is returning false positives due to rate limits."; "As of 2022-05-01, Gab returns false positives because they now use CloudFlare".
  - Issue templates exist for both "False positive" and "False negative" (`.github/ISSUE_TEMPLATE/`).
- **NSFW.** `isNSFW: true` on 19 entries (for example Pornhub, xHamster, ChaturBate, Erome). They are excluded unless `--nsfw` is passed (`sherlock.py` lines 771-772).
- **Request behaviour.** At most 20 worker threads, default timeout 60 s, one fixed Firefox 129 User-Agent (`sherlock.py` lines 214-240).
- **Terms and rate limits.** The README has no disclaimer and no mention of target sites' terms. Rate limits appear only as a cause of false positives in `docs/removed-sites.md`.
- **Maintenance.** Tags: v0.14.4 (2024-05-09), v0.15.0 (2024-07-08), v0.16.0 (2025-09-15), v0.16.2 (2026-09-08). Commits per month in 2026: 4, 5, 5, 17, 10, 0, 0, 3, 9, 0, 1 (January to November). `data.json` last changed 2026-05-04 (false-positive fixes) and had 12 commits in the 12 months to 2026-11-26. The exclusions branch was updated on 2026-11-23, 24 and 25.
- **Fetch URLs.** Client default `https://data.sherlockproject.xyz` (could not be reached from the research container, **unverified**); the same file is in the repository on branch `master`. Exclusions: `https://raw.githubusercontent.com/sherlock-project/sherlock/refs/heads/exclusions/false_positive_exclusions.txt`.

### WhatsMyName (`WebBreacher/WhatsMyName`)

Source: commit `abcb19d6809f0e963e353819c571133b45b6a106`, committed 2026-11-09, "Close the WhatsMyName project (#1112)".

- **Status.** `README.md`: "As of November 9, 2026, WhatsMyName is no longer maintained. This repository is archived and read-only." And: "`wmn-data.json` holds the final dataset: 691 sites, last updated November 9, 2026 ... Both stay at their current URLs, so tools that download them from `main` keep working." And: "nobody is updating these detections now, so the data will get less accurate over time. Treat results as leads to verify, not as facts." The closing commit removed the checker scripts, CI workflows and `CONTRIBUTING.md`. GitHub's archived flag was not checked through the API (**unverified**). No successor fork was identified (**unverified**).
- **Licence.** `LICENSE.md`: "Copyright (C) 2015-2026 Micah Hoffman / This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License." The same text is embedded as the `license` array at the top of `wmn-data.json` and enforced as a constant in `wmn-data-schema.json`. There is no code in the repository any more. File history shows the licence changed over time ("Changing to MIT License" 2016-12-18, "changing license" 2018-07-21); the current file is what applies to the current data.
- **Data file.** `wmn-data.json` (251 KB), JSON Schema draft-07 in `wmn-data-schema.json`. Top level: `license`, `authors`, `categories`, `sites`. Required per site: `name`, `uri_check` (template with `{account}`), `e_code`, `e_string`, `m_string`, `m_code`, `known`, `cat`. Optional: `uri_pretty`, `post_body`, `headers`, `strip_bad_char`, `valid` (only ever `false`), `protection`.
- **Counts.** 691 sites. `uri_pretty` on 229, `protection` on 65, `headers` on 37, POST on 23, `strip_bad_char` on 22, `valid: false` on 1. 169 entries use the same status code for both outcomes; 31 have an empty `m_string` and 2 an empty `e_string`, so the two-signature rule is not fully met everywhere.
- **Detection** (README "Checking a site"): found when status equals `e_code` and the body contains `e_string`; not found when status equals `m_code` and the body contains `m_string`; "Anything else is unknown: the site may be blocking you, down, or changed since the entry was written." Also: "never decide on the status code alone."
- **Inclusion rules.** Publicly accessible, username in the URL, username not transformed into a numeric ID.
- **Protection tags.** Schema enum: `akamai`, `anubis`, `captcha`, `cloudflare`, `cloudfront`, `ddos-guard`, `multiple`, `other`, `user-agent`, `user-auth`. In the data: `cloudflare` 33, `other` 17, `cloudfront` 6, `user-agent` 4, `ddos-guard` 3, `anubis` 1, `captcha` 1.
- **NSFW.** Category `xx NSFW xx` on 39 sites; `dating` on 12.
- **Accuracy on record.** The project was started because "existing username checkers were full of false positives". The removed `CONTRIBUTING.md` (previous commit) required unique `e_string` and `m_string` values because plain phrases "can appear on unrelated pages and cause false positives". The removed checker (`scripts/checker/README.md`, previous commit) re-ran blocked or suspicious sites in headless Chromium and reported a "Blocked / CAPTCHA" section, which shows plain HTTP requests were not enough for part of the list even for the maintainers.
- **Terms and rate limits.** Not mentioned.
- **Maintenance before closure.** 104 commits to `wmn-data.json` in the 12 months to closure; commits per month in 2026: 15, 1, 1, 10, 3, 96, 0, 42, 2, 32, 2.

### Maigret (`soxoj/maigret`)

Source: commit `50e62c45e17b03fd3f059622d38a4cdb3ec2eab4`, committed 2026-11-25.

- **Licence.** `LICENSE` begins "MIT License / Copyright (c) 2020-2026 Soxoj". `pyproject.toml`: `license = "MIT License"`. README: "The open-source Maigret is MIT-licensed and free for commercial use without restriction". The README also advertises a separate private database ("5 000+ sites, updated daily (separate from the public open-source database)"), which is not what is in the repository.
- **Data file.** `maigret/resources/data.json` (4.4 MB). Top level: `sites`, `engines`, `tags`. A companion `maigret/resources/db_meta.json` gives `updated_at`, `sites_count`, `min_maigret_version`, `data_sha256` and `data_url`, which is close to a ready-made subscription manifest.
- **Schema.** Per site: `url` (template with `{username}`), `urlMain`, `urlProbe`, `checkType`, `presenseStrs` (upstream spelling), `absenceStrs`, `errors` (substring to error label), `regexCheck`, `headers`, `requestMethod`, `requestPayload`, `tags`, `alexaRank`, `disabled`, `protection`, `usernameClaimed`, `usernameUnclaimed`, `engine`, `urlSubpath`, `activation`, `source`, `mirrors`, `ignore403`. 8,232 entries only name an `engine` (XenForo, Discourse, phpBB, MediaWiki, GitLab, Gitea and 24 more) whose template in `engines` supplies the URL pattern and strings, so an importer must resolve that indirection.
- **Counts.** 11,640 entries, 744 disabled, 10,896 enabled. Effective check type after resolving engines: `message` 7,401, `status_code` 4,144, `response_url` 95. Tags: `forum` 6,863, `tech` 1,708, `ru` 1,616, `social` 979. `alexaRank` on 1,156. `protection` on 291 (66 of them disabled). `CHANGELOG.md` for 0.6.7 states 11,071 entries with 10,335 enabled; the file has grown since.
- **Detection** (`docs/source/development.rst`): `message` is "the most reliable method, checks if any string from `presenceStrs` is present and none of the strings from `absenceStrs` are present"; `status_code` "checks that status code of the response is 2XX"; `response_url` checks "there is not redirect and the response is 2XX". `maigret/errors.py` holds a table of block-page fingerprints (Cloudflare, DDoS-Guard, Incapsula, Anubis, Vercel, Google reCAPTCHA) that turn a response into an error instead of a result. `CONTRIBUTING.md`: rate limits, captchas and "unusual traffic" pages belong in `errors` so they produce "an UNKNOWN result instead of a false CLAIMED or false AVAILABLE".
- **Protection tags** (`docs/source/development.rst`): `tls_fingerprint` (client switches to `curl_cffi` with Chrome-like TLS; examples Instagram, NPM), `ip_reputation` ("works for most users, fails from datacenter/cloud IPs"; examples Reddit, Patreon, Figma), and `cf_js_challenge`, `cf_firewall`, `aws_waf_js_challenge`, `ddos_guard_challenge`, `js_challenge`, `custom_bot_protection`, which are paired with `disabled: true` because they do "not work for anyone right now". An optional, experimental `--cloudflare-bypass` hands those sites to a local FlareSolverr browser.
- **Accuracy on record (self-reported).** `CHANGELOG.md` 0.6.7: "on random usernames, the share of sites reporting a nonexistent account fell from about 0.6% in late October to under 0.1%." Same entry: "Up to 318 forums and wikis briefly relied on the HTTP status alone, which read as a found account; the database is repaired". `--self-check` verifies the claimed and unclaimed usernames per site.
- **Network location** (`TROUBLESHOOTING.md`): "Results vary a lot depending on where you run from." Mobile internet "usually the best results"; "Home broadband — generally good, though some ISPs are reputation-flagged"; hosting or cloud "the worst case. Datacenter IP ranges are blanket-blocked or challenged by most WAFs". It recommends lowering parallelism: "Some WAFs rate-limit aggressively. Maigret defaults to 100 concurrent connections ... dropping this makes you look less like a scanner". `docs/source/settings.rst` line 253 mentions a proxy being "rate-limited or banned". Nothing describes a home IP being banned.
- **NSFW.** No single flag. Tags `porn` (33 sites), `erotic` (14), `webcam` (8), 52 sites carrying at least one of the three; `dating` (48). Nothing is excluded by default; `--exclude-tags porn,dating` is the documented way. `docs/source/library-usage.rst` shows `excluded_tags=["nsfw", "dating"]`, but no `nsfw` tag exists in the data's tag list and the string does not appear in `maigret/*.py`, so in my reading that example would not exclude the porn-tagged sites.
- **Terms and privacy.** README disclaimer: "For educational and lawful purposes only. You are responsible for complying with all applicable laws (GDPR, CCPA, etc.) in your jurisdiction." `docs/source/privacy.rst`: no telemetry; "The usernames you search for are sent to the websites being checked". Target sites' terms are not discussed. The README carries sponsor adverts for residential-proxy vendors.
- **Defaults.** Top 500 ranked sites per run, 100 connections, 30 s timeout, recursive search and profile-data extraction on (`maigret/resources/settings.json`). The database auto-updates once per 24 hours from `db_meta.json` and falls back to the bundled copy.
- **Maintenance.** 31 tags; v0.6.4 (2026-08-11), v0.6.5 (2026-08-25), v0.6.6 (2026-09-18), v0.6.7 (2026-11-21). Commits per month July to November 2026: 36, 100, 76, 74, 114. 69 commits touched `data.json` in the 30 days to 2026-11-25, many of them bulk additions (for example "Add 440 sites (#3495)" on 2026-11-25).

### social-analyzer (`qeeqbox/social-analyzer`)

Source: commit `c585f429dcd08f390a47b5817946b880df0cc534`, committed 2026-11-08.

- **Licence.** `LICENSE` is "GNU AFFERO GENERAL PUBLIC LICENSE Version 3, 19 November 2007", the same licence as Unlist, so code and data could be combined directly.
- **Data.** `data/sites.json`: 999 entries under `websites_entries`, plus `shared_detections` (for example `mastodon`, `discourse`, `mediawiki`). Per entry: `url` (template with `{username}`), `detections` (strings marked `return: true/false`, type `normal`, `advanced`, `ocr` or `shared`), `type` (category), `global_rank`, `country`, `nsfw`. Results are a 0-100 score ("No-Maybe-Yes").
- **NSFW.** `nsfw: "true"` on 40; category `Adult` on 45.
- **Freshness.** `data/sites.json` last changed 2022-05-23. The README says the database used by its law-enforcement users "is different than the one shared here".
- **Terms.** README: "If you want your website to be excluded from this project list, please reach out to me". This is the only project seen that offers sites a way out.
- **Verdict.** Best licence match, but the data is four years stale.

### Blackbird (`p1ngul1n0/blackbird`)

Source: commit `471ef970b4cd45378de1270c1b2b06687aa158b7`, committed 2026-11-03. The WhatsMyName README links it as `antoniaci/blackbird`; both names resolve to the same commit.

- **Licence.** Two licence files that disagree. `.github/LICENSE` ("Attribution-NonCommercial-ShareAlike 4.0 International", added 2024-06-30) and `docs/LICENSE` ("GNU GENERAL PUBLIC LICENSE Version 3", added 2024-05-02). An earlier root `LICENSE` was removed on 2024-05-14. Which one the author intends is **unverified**; treat the code as not safely reusable.
- **Data.** No username dataset of its own. `src/config.py` downloads `https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json` at runtime, which is a precedent for the fetch-at-runtime option. `data/email-data.json` reuses the WhatsMyName schema for email checks. `data/wmn-metadata.json` adds profile-field extraction.
- **Terms.** README disclaimer: "for Educational purpose ONLY. Do not use it without permission."

### NExfil (`thewhiteh4t/nexfil`)

Source: commit `c540238dd510b865daac1eb59a328f8fa68b1ce5`, committed 2023-09-30.

- MIT ("Copyright (c) 2021 thewhiteh4t"). `src/nexfil/url_store.json`: 328 entries of `url`, `test`, `data`. `test` is null for 204 entries and otherwise `string`, `redirect`, `headless`, `api`, `method`, `url`, `subdomain` or `alt`. No NSFW marking. No commit since 2023-09-30.

### user-scanner (`kaifcodec/user-scanner`)

Source: commit `65af5fcecf2fcaed0e47326750fc86f9c6d4cfde`, committed 2026-11-25.

- MIT ("Copyright (c) 2025 Kaif"). Each site is a Python module (2,550 under `user_scanner/user_scan/`, 220 under `user_scanner/email_scan/`), so there is no data file to subscribe to. Reuse would mean shelling out or importing Python.
- It also checks email addresses, and some of those modules "may send emails/notifications" to the address unless left off (`--allow-loud`, `docs/FLAGS.md`). That is a risk to keep out of a self-check.
- README disclaimer: "strictly for educational purposes, authorized security research, and defensive OSINT investigations". The README carries proxy-vendor adverts.

### socialscan (`iojw/socialscan`)

Source: commit `5ae42d0f82b0ebd717b3ae52b693b4ececa902b1`, committed 2024-01-20.

- `LICENSE` is "Mozilla Public License Version 2.0"; `setup.py` carries the classifier "License :: OSI Approved :: MIT License". The LICENSE file and README badge agree on MPL 2.0.
- 11 platforms, code only (`socialscan/platforms.py`). It queries "the registration servers of the platforms", fetching CSRF tokens and cookies, and claims "100% accuracy". Its README explains why profile-URL checks go wrong: reserved words and "Deleted/banned account usernames tend to be unavailable even though the profile pages might not exist".
- For Unlist this answers a different question (is the name taken, not is there a public account) and touches sign-up endpoints, which is more intrusive than loading a public profile page.

### Naminter (`3xp0rt/Naminter`)

Source: commit `7cb094f8d9b6c4d94a464e91aacfa75167f06e45`, committed 2026-08-14.

- MIT ("Copyright (c) 2025–2026 3xp0rt"). A client for the WhatsMyName dataset; `naminter/core/constants.py` points at the upstream `wmn-data.json` and schema URLs. No dataset of its own.

### Others not examined

`soxoj/osint-namecheckers-list` (MIT, commit `8ebe939`, 2026-11-21) lists further tools, including Snoop ("largest raw site count; partially paid"), Investigo and vesper (both reuse Sherlock's database). None were inspected (**unverified**).

## Detection reliability across projects

- **False positives.** The main cause on record is a block or challenge page returned with status 200, or a redesign that removes the "not found" string. Sherlock's design reports an account by default, so it is the most exposed; 45 of its 481 sites were on the false-positive list on 2026-11-25. WhatsMyName and Maigret's `message` type need a positive string and are safer.
- **False negatives.** Caused by blocks answered with 403 or 404, rate limits, login walls, and sites that keep a name reserved after deletion. socialscan's README notes that deleted or banned accounts stay unavailable without a profile page.
- **Protected sites.** WhatsMyName tags 65 of 691 entries with a protection type. Maigret tags 291 and disables 66 of those. Sherlock removes such sites and lists them in `docs/removed-sites.md` (seven entries there name a captcha or Cloudflare).
- **What a result means for Unlist.** "Account exists" means a public page for that name exists, not that it belongs to the Subject. WhatsMyName's closing README says to treat results "as leads to verify, not as facts"; Unlist should show the profile URL and let the Operator confirm before any request to the site.

## Legal and terms exposure on record

- None of the projects documents the terms of service of the sites it checks, and none claims permission from them.
- Disclaimers shift responsibility to the person running the tool: Maigret ("lawful purposes only ... GDPR, CCPA"), Blackbird ("Do not use it without permission"), user-scanner, social-analyzer.
- Rate limits are documented as a cause of wrong results and as a reason to lower concurrency (Maigret `-n 20`), not as a legal topic.
- Residential IPs: Maigret says home broadband is "generally good, though some ISPs are reputation-flagged" and that datacenter IPs are the worst case. No project file read here describes a home IP being banned, and a web search of the Sherlock tracker for such reports found none (thin evidence, **unverified** either way).
- Practical implication for a home server: a full run of Sherlock's list is roughly one request per listed site (481 entries), so the load on any single site is small. Risk grows with repeated or scheduled runs and with many usernames. Run on demand, cap concurrency well below the tools' defaults, send one request per site, and never retry a site that answered with a block.

## Sources

Upstream repositories, cloned with `--depth 1` and deepened for history:

| Repository | Commit | Commit date |
|---|---|---|
| https://github.com/sherlock-project/sherlock | `c588d7c8b476df9f9c84912a05d1430fb8cdcdae` | 2026-11-01 |
| https://github.com/WebBreacher/WhatsMyName | `abcb19d6809f0e963e353819c571133b45b6a106` | 2026-11-09 |
| https://github.com/soxoj/maigret | `50e62c45e17b03fd3f059622d38a4cdb3ec2eab4` | 2026-11-25 |
| https://github.com/qeeqbox/social-analyzer | `c585f429dcd08f390a47b5817946b880df0cc534` | 2026-11-08 |
| https://github.com/p1ngul1n0/blackbird | `471ef970b4cd45378de1270c1b2b06687aa158b7` | 2026-11-03 |
| https://github.com/thewhiteh4t/nexfil | `c540238dd510b865daac1eb59a328f8fa68b1ce5` | 2023-09-30 |
| https://github.com/kaifcodec/user-scanner | `65af5fcecf2fcaed0e47326750fc86f9c6d4cfde` | 2026-11-25 |
| https://github.com/iojw/socialscan | `5ae42d0f82b0ebd717b3ae52b693b4ececa902b1` | 2024-01-20 |
| https://github.com/3xp0rt/Naminter | `7cb094f8d9b6c4d94a464e91aacfa75167f06e45` | 2026-08-14 |
| https://github.com/soxoj/osint-namecheckers-list | `8ebe939f5759b8b5e955ef22ce73014536efd5e2` | 2026-11-21 |
| https://github.com/creativecommons/cc-legal-tools-data (`docs/licenses/by-sa/4.0/legalcode.en.html`) | `f4166d601de085b7ad62eb7f8251a3808ffaba73` | 2026-11-25 |

Licence texts quoted: CC BY-SA 4.0 legal code from the Creative Commons repository above; AGPL-3.0 from `LICENSE` in this repository.

## Not verified

State after the 2026-11-26 verification pass. See the [Verification log](#verification-log) for what changed.

- The FSF licence list (<https://www.gnu.org/licenses/license-list.html>) and the GPL FAQ could not be read: `www.gnu.org` reset the connection twice and again after a one-minute wait, and the fetch tool could not resolve the host. The MIT-to-AGPL direction is therefore from the MIT text and my reading, not from the FSF's own statement. The CC pages (compatible licences, FAQ, 2015 announcement) were read.
- `https://data.sherlockproject.xyz` was refused by the container's proxy, so it is not confirmed that it serves the same file as the repository. The Sherlock website documentation was not read.
- GitHub's archived flag on WhatsMyName, and whether any fork continues the dataset.
- Which licence Blackbird's author intends.
- Whether Sherlock's or Maigret's data includes entries taken from WhatsMyName.
- All accuracy figures. No checks were run; Maigret's "under 0.1%" and socialscan's "100% accuracy" are the projects' own claims.
- Reports of residential IP bans in the projects' issue trackers; the trackers were not searched systematically.
- Snoop and the other tools named only in `osint-namecheckers-list`.
- Commit counts come from shallow clones (300 to 600 commits deep) and cover only that window.

## Verification log

Pass of 2026-11-26, limited to the licence-compatibility statements. Pages read in full: <https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/>, <https://creativecommons.org/faq/> (including its sections on software, databases, NonCommercial and remixing), <https://creativecommons.org/2015/10/08/cc-by-sa-4-0-now-one-way-compatible-with-gplv3/>, <https://creativecommons.org/share-your-work/cclicenses/>. The AGPL-3.0 text was re-read from `LICENSE` in this repository. <https://www.gnu.org/licenses/license-list.html> and the GPL FAQ were **not readable**: `www.gnu.org` closed the connection mid-exchange on three attempts (one retried after a minute), and the web-fetch tool could not resolve the host. Nothing was routed around.

Counts: 3 statements confirmed, 1 corrected or extended, 2 still unverified. The rest of the file (dataset counts, commits, detection logic) is from the upstream clones and was out of scope for this pass.

| Section | Said | Now says | Source |
|---|---|---|---|
| Recommendation in detail, "CC BY-SA 4.0, modified" | CC lists GPLv3 as one-way compatible, declared 2015-10-08; "unverified first-hand" | Confirmed first-hand, with CC's wording: one-way, "you may not license your contributions to adaptations of GPLv3 projects under BY-SA 4.0", and "special considerations apply". Declared 8 October 2015 | <https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/>, <https://creativecommons.org/2015/10/08/cc-by-sa-4-0-now-one-way-compatible-with-gplv3/> |
| same | "AGPL-3.0 is not GPLv3, so I would not rely on that route" | Confirmed, and made specific. AGPL-3.0 is absent from CC's list (which names only BY-SA, ported BY-SA, Free Art License 1.3 and GPLv3; no licence is recorded as evaluated and rejected). A two-step route exists on paper (relicense the adaptation as GPLv3, then combine under AGPL-3.0 section 13), but the list would stay GPLv3 and CC says the mechanism is meant for content integrated into software where the two cannot be told apart. Recommendation unchanged: keep a derived list as a separate CC BY-SA 4.0 file | same, <https://creativecommons.org/faq/>, repository `LICENSE` section 13 |
| Reasoning, "CC BY-SA 4.0, unmodified" | Unmodified data file beside AGPL code is not Adapted Material (my reading) | Reading stands and is supported by CC's FAQ: ShareAlike "only applies if a work is modified and if the work is shared publicly"; a compilation need not itself be SA | <https://creativecommons.org/faq/> |
| Answer 4 and the reuse table (CC BY-SA converted copy must stay CC BY-SA, cannot be relicensed AGPL-3.0) | as stated | Confirmed: CC's page says contributions to BY-SA 4.0 adaptations "may only be licensed under" the listed licences, and AGPL-3.0 is not among them | compatible-licenses page above |
| Not verified, first bullet | CC page and FSF list could not be fetched | CC pages now read; only the FSF list remains unread | n/a |

### Remaining unverified, and why

- The FSF's own statements on MIT, Apache-2.0 and CC0 compatibility with the GPL family (<https://www.gnu.org/licenses/license-list.html>): host unreachable. This file's MIT conclusions rest on the MIT text and my reading. CC's FAQ does say "the CC0 Public Domain Dedication is GPL-compatible and acceptable for software" `[read]`, but that is CC's statement, not the FSF's.
- The FSF's view of whether CC BY-SA 4.0 data is compatible with AGPL-3.0 directly: not read.
- Everything not about licence compatibility (dataset sizes, commits, `data.sherlockproject.xyz`, WhatsMyName archived flag, Blackbird intent, provenance of Sherlock and Maigret data) is unchanged and still unverified as listed above.
