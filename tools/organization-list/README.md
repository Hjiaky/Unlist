# Unlist official Organization List: sources and build

This directory is meant to become its own repository, `hjiaky/unlist-organizations` (spec section 16). Until that repository exists it lives here, inside Unlist, and moves out unchanged. Everything in it is dedicated to the public domain under **CC0 1.0** (`LICENSE`), so fixes can flow back to datarequests.org.

## Layout

| Path | What it holds |
|---|---|
| `build.py` | The build. Python standard library only. |
| `schema.json` | JSON Schema of an Organization List file (header, records, obsolete records). Schema version 1. |
| `organizations/<slug>.json` | Unlist's fields for an upstream record: `broker`, `domains`, `recheck-default`, `last-checked`, `notes`, or a correction of any record field until it is fixed upstream. |
| `brokers/<slug>.json` | Unlist-only records (Brokers not in datenanfragen), complete records in the list format. |
| `ambiguous-domains.json` | Domains shared by many senders (free mail, email service providers, hosting and newsletter platforms). Never claimed, never matched. |

## Building

```sh
git clone https://github.com/datenanfragen/data /tmp/upstream/data
git clone https://github.com/jdm-contrib/jdm /tmp/upstream/jdm
python3 -I build.py /tmp/upstream/data --jdm /tmp/upstream/jdm --out dist --date 2026-11-26
```

The checkouts are read as data only: JSON is parsed, nothing in them runs, and the commit is read from `.git` without running git. The build writes to `--out`:

- `organizations.json` (CC0): header (name, licence, credit, homepage, version, date, `schema_version`, source commit) plus one record per line and the obsolete records with their redirects.
- `jdm-domains.json` (**MIT**, with JustDeleteMe's notice verbatim in its header): JustDeleteMe domains mapped onto official slugs. A separate list because MIT data cannot go into the CC0 list.
- `supervisory-authorities.json` (CC0): the 57 upstream Supervisory Authority records, unchanged.
- copies of `ambiguous-domains.json` and `schema.json`.

It prints a report and exits with status 1, listing every error, when the result is not publishable. Unlist bundles the output in `unlist/organizations/data/`.

The current snapshot was built from `datenanfragen/data` at `4f6385518492d0c15dddf0ac3e487098ccdc922a` (2026-11-26) and `jdm-contrib/jdm` at `b75bc1463f85993fd87f7215907d61fe243e25bd` (2026-11-24).

## Rules the build applies

- **Upstream fields** keep their datenanfragen names. Fax numbers, PGP keys, custom template paths, `facet-group` and `nsfw` are dropped; a suggested transport of `fax` becomes `letter`.
- **Domains.** A `domains` field in `organizations/` or `brokers/` is a claim, and a domain claimed by two records **fails the build**. Otherwise the host of the upstream `web` URL becomes the record's domain, unless another record has the same host (72 such hosts, mostly churches, schools and company groups, are left unassigned and listed in the report) or the host is in `ambiguous-domains.json`. A domain here is the lowercase host without a leading `www.`; the Public Suffix List is not used yet, so `shop.example.co.uk` stays as it is.
- **Named-person addresses.** An email whose local part reads like `firstname.lastname` (and contains none of the role words listed in `build.py`) is published without the email, with a note, until it is fixed upstream. Four records are affected in this snapshot: `acnw3`, `dlrg-de`, `elitenetzwerk-bayern`, `kirchenkreis-altholstein`.
- **Obsolete records** are carried over with their reason and redirect. A redirect to a slug that no longer exists is dropped and reported.
- **Validation.** Every published record is checked against `schema.json` with a small built-in validator (no `jsonschema` dependency). An invalid record fails the build; fix it in `organizations/<slug>.json` and report it upstream.
- **JustDeleteMe mapping.** A JustDeleteMe site is mapped onto an official record when its domains point at exactly one record (and its name points nowhere else), or, failing that, when its name equals exactly one record's name or brand and that record has no domains and is not scoped to particular countries. The deletion URL is not used (it is often hosted by a third party). Only domains of the record's brand family are kept (same label as one of its domains, name or brands), and domains another record owns, that two records would share, or that are subdomains of a domain the record already has are dropped.

## Brokers (from `docs/research/eu-uk-brokers.md` in Unlist)

- **49 upstream records flagged** `broker: true`: the 54 the research found upstream, minus the five borderline ones below.
- **17 Unlist-only Broker records added**: the 21 new rows minus 2 ceased (Caloga, Experian Nederland) and 2 borderline (Stichting BKR, GeoPostcodes).
- **No search-excerpt (`[S]`) email is published.** Those records (192.com, Cognism, Creditsafe Nederland) carry a postal address or web page only and a note "Contact to be confirmed". Every `[S]` contact must be confirmed on the Broker's own page before it is added. Records whose source names no contact at all (Solocal Marketing Services, Tagadamedia, Irish Credit Bureau, the Belgian firms from the EDPB study, Lifecycle Marketing, Locatefamily) say so in a note and are marked `scraped`.
- `last-checked` is set only where the role mailbox was read on a primary register (ICO entries, 2026-11-26).
- No non-commercially licensed list (Big Ass Data Broker Opt-Out List, Optery, Privacy Rights Clearinghouse) was consulted or copied.

### Awaiting a human decision

These seven rows are marked borderline in the research. They are neither flagged nor added until someone decides whether they count as Brokers:

| Row | Kind | Upstream slug |
|---|---|---|
| Besurance HIS GmbH (formerly informa HIS) | insurance claims database | `informa-his` |
| DEMDA Deutsche Mieter Datenbank | tenant database | `demda` |
| Cifas | fraud-prevention data sharing | `cifas` |
| GB Group plc | identity-verification data | `gb-group` |
| Trulioo (Ireland) Limited | identity-verification data | `trulioo-information-services-inc` |
| Stichting BKR | credit registry run by a foundation | not upstream |
| GeoPostcodes | address data, link to individuals unclear | not upstream |

## To report upstream (datarequests.org)

- `asos-shop`: `web` is `httsp://www.asos.com` (corrected here in `organizations/asos-shop.json`).
- `callcredit-gb`: stale after the TransUnion rebrand (see its note).
- The four named-person email addresses above.
