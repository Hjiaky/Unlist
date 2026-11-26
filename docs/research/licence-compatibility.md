# Are the planned dependencies and data licences compatible with AGPL-3.0-or-later?

Research for issue #35. Researched 2026-11-26 from shallow clones of each project's repository (commits below) and from the licence texts. Nothing from the clones was executed.

**This is a reading of licence texts for software design, not legal advice.** Where a statement is my own reasoning rather than a quoted source, it is tagged `[analysis]`.

**The FSF's own pages could not be read.** `www.gnu.org` reset the connection on two `curl` attempts, again on a retry one minute later, and the web-fetch tool could not resolve the host. Nothing was routed around (no mirrors, caches or archives). So every "the FSF lists X as GPL-compatible" statement below is `[memory]`, and each verdict rests on the licence texts. See [Could not verify](#could-not-verify).

## Answer

| # | Item | Licence (from its own files) | How Unlist uses it | Compatible with AGPL-3.0-or-later? | Conditions to meet |
|---|---|---|---|---|---|
| 1 | Django (+ `asgiref`, `sqlparse`) | BSD-3-Clause. Django also ships `LICENSE.python` (PSF-2.0 for stdlib-derived code), PyDispatcher's BSD notice, and MIT jQuery, Select2 and XRegExp in the admin | (a) code shipped in the image | **Yes** | Keep the copyright notices, conditions and disclaimer in what Unlist distributes. Do not use "Django" or its contributors' names to endorse Unlist. If the admin is enabled, its MIT JavaScript is served too: keep those notices |
| 2 | htmx 2.0.11 | 0BSD ("Zero-Clause BSD") | (a) JavaScript served from the instance | **Yes** | None. Recommended: add a licence comment or JavaScript web-labels entry, because `htmx.min.js` has no licence header |
| 3 | gunicorn 27.0.1 | MIT, plus a `NOTICE` with an HPND-style notice (Vinay Sajip) and two more MIT notices (Eventlet, Meebo) | (a) code shipped in the image | **Yes** | Keep `LICENSE` and the `NOTICE` text. The wheel installs only `LICENSE`, so Unlist's notices file must carry `NOTICE` itself |
| 4 | Public Suffix List | MPL-2.0. The file carries only the Exhibit A notice, **no** "Incompatible With Secondary Licenses" notice | (b) data bundled with each release | **Yes, with conditions** | Ship `public_suffix_list.dat` unmodified, header kept. Tell recipients it is MPL-2.0 and where to get the licence. Changes to the file stay under MPL-2.0 (which may also be AGPL via §3.3). No runtime fetch unless the Operator turns it on |
| 5 | `datenanfragen/data` | CC0 1.0 | (b) bundled, and republished as a derived CC0 Organization List | **Yes** | None. Credit is courtesy, not required. CC0 does not license the datenanfragen name or trademarks |
| 6 | JustDeleteMe (`jdm-contrib/jdm`) | MIT, covering `_data/sites.json` | (b) bundled data, or (c) fetched | **Yes, with conditions** | Keep the MIT notice with any copy or substantial portion. **A list built from it cannot be published as plain CC0**: keep it as a separate MIT-licensed list, or carry the MIT notice with the derived list |
| 7 | Have I Been Pwned breach catalogue | CC BY 4.0 (established in `hibp-api-terms.md`) | (c) fetched and shown; maybe (b) a bundled snapshot | **Yes, with conditions** (as separate data, not merged into code) | Visible attribution with a link to haveibeenpwned.com wherever the data appears. Show each breach's `Attribution` field. A bundled snapshot needs a notice, a licence link and a note of any changes. HIBP is a proprietary service: fetching is opt-in and marked nonfree |
| 8 | Python (CPython) | PSF License Version 2 (with other licences for bundled third-party parts) | runtime; (a) only if the project publishes a container image | **Yes** | Nothing while Unlist ships only its own source. If an image is published, keep Python's licence file in it and **check the whole base image**: it contains GPL and LGPL programs whose source must be offered |

Unlist's own AGPL obligation also lands on the RC: §13 requires every network user to be offered the Corresponding Source. See the [checklist](#obligations-checklist-for-the-rc).

## Repositories read

| Repository | Commit | Date | Licence file read |
|---|---|---|---|
| https://github.com/django/django | `f0e7bd9` | 2026-11-26 | `LICENSE`, `LICENSE.python`, `pyproject.toml`, vendored `LICENSE*` under `django/contrib/admin/static`, `django/dispatch/license.txt` |
| https://github.com/django/asgiref | `03dcd19` | 2026-10-23 | `LICENSE`, `setup.cfg` |
| https://github.com/andialbrecht/sqlparse | `09dbe1e` | 2026-11-01 | `LICENSE`, `pyproject.toml` |
| https://github.com/bigskysoftware/htmx | `51c3e67` | 2026-11-18 | `LICENSE`, `package.json`, `dist/htmx.min.js` |
| https://github.com/benoitc/gunicorn | `5ced50e` | 2026-11-12 | `LICENSE`, `NOTICE`, `pyproject.toml` |
| https://github.com/publicsuffix/list | `59540d8` | 2026-11-26 | `LICENSE`, `public_suffix_list.dat`, `README.md`, `docs/` |
| https://github.com/datenanfragen/data | `4f63855` | 2026-11-26 | `LICENSE`, `README.md` |
| https://github.com/jdm-contrib/jdm | `b75bc14` | 2026-11-24 | `LICENSE`, `README.md`, `_data/sites.json` |
| https://github.com/python/cpython | `62a7400` | 2026-11-26 | `LICENSE` |

AGPL-3.0 quotes are from `LICENSE` in this repository. CC BY 4.0 quotes are from <https://creativecommons.org/licenses/by/4.0/legalcode.en>, read 2026-11-26.

## How permissive licences fit the AGPL (shared reasoning)

Used by items 1, 2, 3, 6 and 8.

- AGPL-3.0 §7 lets a covered work carry, for material added to it, terms "Requiring preservation of specified reasonable legal notices or author attributions", "Disclaiming warranty or limiting liability", "Limiting the use for publicity purposes of names of licensors or authors" and "Prohibiting misrepresentation of the origin of that material" `[read]` (`LICENSE` lines 349-365). BSD-3-Clause, MIT, 0BSD and HPND ask for no more than those, so code under them can be combined with AGPL code. The combination is conveyed under the AGPL, and the permissive parts keep their own notices `[analysis]`. The FSF licence list calls Modified BSD, Expat (MIT), 0BSD and Python 2.0.1+ licences GPL-compatible `[memory]`; not re-read.
- Django and gunicorn are separate, unmodified packages that Unlist imports. AGPL §1 excludes "general-purpose tools or generally available free programs which are used unmodified … but which are not part of the work" from the Corresponding Source `[read]` (`LICENSE` lines 122-129). So Unlist's source offer need not include their source while they stay unmodified, but their licences still apply when Unlist ships them (in a container image or a vendored copy) `[analysis]`.
- Data files under other licences are not "extensions of the covered work". AGPL §5: "Inclusion of a covered work in an aggregate does not cause this License to apply to the other parts of the aggregate" `[read]` (`LICENSE` lines 223-231). Bundled data keeps its own licence and must be labelled with it, not as AGPL `[analysis]`.

## Distinguishing (a), (b), (c)

`[analysis]`

- **(a) Code shipped with Unlist** (Django, gunicorn, htmx; Python if an image is published). The licence conditions apply on every distribution: a release tarball, a container image, and the htmx file each browser downloads from the instance. Serving htmx to a browser is conveying a copy, so its licence travels with it. 0BSD asks for nothing; the others ask for their notices.
- **(b) Data bundled with Unlist** (Public Suffix List, datenanfragen, JustDeleteMe, maybe an HIBP snapshot). It is a separate work in an aggregate. Its own licence governs copying and changes. File-level copyleft (MPL-2.0) and attribution licences (MIT, CC BY) attach to the file and any list derived from it, not to Unlist's code.
- **(c) Data fetched at runtime and shown** (HIBP, possibly upstream lists). The Operator's instance copies the data, not the project, so the project has no notice to ship. Displaying CC BY material to the Operator or a Subject is Sharing under CC BY 4.0 ("to provide material to the public by any means"), so the attribution must show in the UI. Fetching contacts a third party, so AGENTS.md rule 4 makes it opt-in.

## 1. Django

- `LICENSE` is the three-clause BSD text: "Copyright (c) Django Software Foundation and individual contributors. All rights reserved." It requires that "Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer", that "Redistributions in binary form must reproduce the above copyright notice … in the documentation and/or other materials provided with the distribution", and that "Neither the name of Django nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission" `[read]` (<https://github.com/django/django/blob/f0e7bd9/LICENSE>).
- `pyproject.toml`: `license = "BSD-3-Clause"`, `license-files = ["LICENSE", "LICENSE.python", "AUTHORS"]`. Required dependencies: `asgiref>=3.13`, `sqlparse>=0.5.0`, and `tzdata` on Windows only `[read]`.
- `LICENSE.python`: "Django includes code from the Python standard library, which is licensed under the Python license, a permissive open source license. The copyright and license is included below for compliance with Python's terms." `[read]`. See item 8 for that licence.
- `django/dispatch/license.txt`: "django.dispatch was originally forked from PyDispatcher", with PyDispatcher's BSD-style notice, "Copyright (c) 2001-2003, Patrick K. O'Brien and Contributors" `[read]`.
- Vendored JavaScript in the admin, each with its own MIT licence file: jQuery ("Copyright OpenJS Foundation and other contributors"), Select2 ("Copyright (c) 2012-2017 Kevin Brown, Igor Vaynberg, and Select2 contributors") and XRegExp ("Copyright (c) 2007-present Steven Levithan") `[read]` (`django/contrib/admin/static/admin/js/vendor/*/LICENSE*`). They reach a browser only if Unlist enables `django.contrib.admin`.
- `asgiref`: `LICENSE` is BSD, "Copyright (c) Django Software Foundation and individual contributors", and `setup.cfg` says `license = BSD-3-Clause` `[read]`. `sqlparse`: `LICENSE` is a three-clause BSD text ("Copyright (c) 2016, Andi Albrecht"), classifier "BSD License" `[read]`.
- **Verdict** `[analysis]`: compatible. Clause 3 (no endorsement) is a §7(d) term the AGPL allows. Because the wheels list their licence files in `license-files`, `pip install` puts them in each package's `.dist-info` inside the image. Still, Unlist's own third-party notices file should reproduce them, so they reach someone who only gets the source tarball or reads the About page. Avoid wording such as "Django-certified".

## 2. htmx

- `LICENSE` is headed "Zero-Clause BSD": "Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted", followed by a warranty disclaimer `[read]` (<https://github.com/bigskysoftware/htmx/blob/51c3e67/LICENSE>).
- `package.json`: `"version": "2.0.11"`, `"license": "0BSD"` `[read]`.
- `dist/htmx.min.js` starts with code; it has no licence comment `[read]`.
- **Verdict** `[analysis]`: compatible, with no conditions. 0BSD needs no notice kept. It counts as code served from the instance (a). It satisfies the "no CDN" rule as long as the file is vendored into Unlist's static files.
- **Recommendation** `[analysis]`: the Free Software principle and the FSF's LibreJS add-on care whether a browser can tell the JavaScript is free. Serve the unminified `htmx.js` or add a licence comment to the minified file, and list it on a "JavaScript licence information" page (the LibreJS "web labels" convention: file, licence, source link). The LibreJS conventions are `[memory]`; gnu.org was unreachable.

## 3. gunicorn

- `LICENSE`: "2009-2026 (c) Benoît Chesneau … 2009-2015 (c) Paul J. Davis", followed by the MIT text, including "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software" `[read]` (<https://github.com/benoitc/gunicorn/blob/5ced50e/LICENSE>).
- `NOTICE`: "Gunicorn is released under the MIT license", plus notices for parts taken from elsewhere: `gunicorn.logging_config` "Copyright 2001-2005 by Vinay Sajip" (a permission notice requiring "that the above copyright notice appear in all copies and that both that copyright notice and this permission notice appear in supporting documentation" and not using the name "in advertising or publicity"); `gunicorn.debug` "Based on eventlet.debug module under MIT license"; `gunicorn.reloader` "Based on greins.reloader module under MIT license: 2010 (c) Meebo, Inc." `[read]` (<https://github.com/benoitc/gunicorn/blob/5ced50e/NOTICE>). Source files say "released under the MIT license. See the NOTICE for more information" `[read]` (`gunicorn/glogging.py`).
- `pyproject.toml`: `license = "MIT"`, `license-files = ["LICENSE"]`, version 27.0.1, no required runtime dependencies (only optional extras such as `gevent`, `tornado`) `[read]`.
- **Verdict** `[analysis]`: compatible. Gap: `NOTICE` is not in `license-files`, so the installed wheel does not carry the Sajip, Eventlet and Meebo notices. Unlist's notices file should include gunicorn's `NOTICE` text verbatim. Not using the gunicorn extras keeps further dependencies out.

## 4. Public Suffix List

- `LICENSE` is "Mozilla Public License Version 2.0" `[read]` (<https://github.com/publicsuffix/list/blob/59540d8/LICENSE>).
- The data file's header is exactly the MPL Exhibit A notice: "This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/." `[read]` (<https://github.com/publicsuffix/list/blob/59540d8/public_suffix_list.dat>, lines 1-3).
- **No "Incompatible With Secondary Licenses" notice.** The string occurs 0 times in `public_suffix_list.dat`, and nowhere in the repo's `README.md` or `docs/`; it occurs only in `LICENSE` itself, as the definition `[read]`. MPL-2.0 §1.5 defines the term as (a) Exhibit B attached, or (b) code first offered under MPL 1.1 or earlier and not also under a Secondary License `[read]`. (a) is not the case. Whether (b) applies depends on the list's licence history before MPL-2.0. That history was not checked; the list moved to MPL-2.0 when that version came out `[memory]`.
- MPL-2.0 §1.12 names the AGPL directly: "'Secondary License' means either the GNU General Public License, Version 2.0, the GNU Lesser General Public License, Version 2.1, the GNU Affero General Public License, Version 3.0, or any later versions of those licenses." `[read]`
- §3.3: "You may create and distribute a Larger Work under terms of Your choice, provided that You also comply with the requirements of this License for the Covered Software. If the Larger Work is a combination of Covered Software with a work governed by one or more Secondary Licenses, and the Covered Software is not Incompatible With Secondary Licenses, this License permits You to additionally distribute such Covered Software under the terms of such Secondary License(s)" `[read]`.
- §3.1: "All distribution of Covered Software in Source Code Form, including any Modifications that You create or to which You contribute, must be under the terms of this License. You must inform recipients that the Source Code Form of the Covered Software is governed by the terms of this License, and how they can obtain a copy of this License." `[read]`
- §3.4: "You may not remove or alter the substance of any license notices (including copyright notices, patent notices, disclaimers of warranty, or limitations of liability) contained within the Source Code Form" `[read]`.
- The file asks: "Please pull this list from, and only from https://publicsuffix.org/list/public_suffix_list.dat, rather than any other VCS sites." `[read]` (line 5). This is a request, not a licence term `[analysis]`.
- **Verdict** `[analysis]`: compatible. The bundled `.dat` and Unlist form a Larger Work, which Unlist may distribute under AGPL-3.0-or-later while the `.dat` stays MPL-2.0. The simplest compliant form is: ship the file byte-for-byte with its header, put a copy of the MPL-2.0 text (or the URL) next to it, and name it in the notices file. If Unlist ever edits the list, the edited file stays MPL-2.0 (file-level copyleft), and its source (the `.dat`) must be offered. Since the `.dat` is its own source form, shipping it unmodified meets that. Converting it at build time into a Python module or a pickle would make a Modification or an Executable Form, which brings extra duties. Parse the `.dat` at start-up instead.
- **Design notes** `[analysis]`: (1) Refreshing the list at runtime contacts publicsuffix.org, so it must be off by default (AGENTS.md rule 4). Update the snapshot with each release. (2) If a parsing library is added later, check its licence and whether it downloads the list by itself. `tldextract` does by default `[memory]`.
- The MPL FAQ at mozilla.org was not reachable (proxy refused the host), so no Mozilla commentary is quoted. The licence text above is enough for this question.

## 5. datenanfragen/data

Already established in [organization-lists.md §1](organization-lists.md#1-datenanfragendata-datarequestsorg) and its licence reasoning (CC0 1.0 in `LICENSE`, on every record page and on the Open source page; CC's FAQ says CC0 "is GPL-compatible and acceptable for software" and waives database rights). Not redone. Re-checked at commit `4f63855`:

- `LICENSE` begins "Creative Commons Legal Code / CC0 1.0 Universal". It waives "database rights (such as those arising under Directive 96/9/EC …)" `[read]` (<https://github.com/datenanfragen/data/blob/4f63855/LICENSE>, lines 54-58).
- §4(a): "No trademark or patent rights held by Affirmer are waived, abandoned, surrendered, licensed or otherwise affected by this document." `[read]` (line 104).
- README: "by contributing, you agree for your work to be released under a Creative Commons CC0 1.0 Universal license" `[read]`.
- **Verdict** `[analysis]`: compatible, no conditions. Bundling, transforming and republishing a derived CC0 Organization List are all allowed. Two cautions: do not present Unlist's list as datenanfragen's or use their name as an endorsement (§4(a) keeps trademark rights), and a credit line ("Seeded from datenanfragen.de, CC0") is good practice. A privacy check for personal data inside records is still open (listed as a gap in `organization-lists.md`); it is not a licence matter.

## 6. JustDeleteMe (jdm-contrib/jdm)

Licence established in [organization-lists.md §4](organization-lists.md#4-justdeleteme). Re-checked at the same commit `b75bc14`:

- `LICENSE`: "The MIT License (MIT) / Copyright (c) 2013-2020 Robb Lewis, The JDM Contrib Team, & various contributors" `[read]` (<https://github.com/jdm-contrib/jdm/blob/b75bc14/LICENSE>).
- README "License": "Project licensed under the MIT License (MIT)." The README also names two third-party parts of the website: a language icon from Font Awesome "released under the CC-BY 4.0 license", and search code from DevCenter.me, "MIT licensed, Copyright (c) 2013 Steve Streza" `[read]`.
- The data is `_data/sites.json`, 2,671 entries with `name`, `url`, `difficulty`, free-text `notes` (and translated `notes_de`, `notes_it`, …) `[read]`. No separate data licence, so the repository's MIT licence covers it `[analysis]`.
- **Verdict** `[analysis]`: compatible, with the MIT condition: "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." **This collides with publishing the official Organization List as CC0.** Domains and deletion URLs are close to bare facts, but the `notes` text is creative writing, and the EU database right can cover a substantial extraction. The safe route:
  - publish JustDeleteMe-derived data as its **own Organization List file, labelled MIT, with the JDM notice**, which an instance subscribes to next to the CC0 list; or
  - if fields are merged into one file, attach the MIT notice to that file, which means the file is no longer plain CC0 and cannot be offered back to datenanfragen as is.
  - Copy only the data, not the Font Awesome icon or the site code.

## 7. Have I Been Pwned breach catalogue

Licence and attribution terms established in [hibp-api-terms.md](hibp-api-terms.md#attribution-and-licence) (read in full on 2026-11-26): breach and paste data is CC BY 4.0; "Clear and visible attribution with a link to haveibeenpwned.com should be present anywhere data from the service is used"; the Terms of Use require attribution "in accordance with the Creative Commons Attribution 4.0 licence and our brand usage guidelines"; 130 of 1,055 breaches carry their own `Attribution` value. Not redone. Added from the CC BY 4.0 legal code (<https://creativecommons.org/licenses/by/4.0/legalcode.en>) `[read]`:

- §3(a)(1): if You Share the material "(including in modified form)", You must retain "identification of the creator(s) … a copyright notice; a notice that refers to this Public License; a notice that refers to the disclaimer of warranties; a URI or hyperlink to the Licensed Material to the extent reasonably practicable", "indicate if You modified the Licensed Material", and "indicate the Licensed Material is licensed under this Public License, and include the text of, or the URI or hyperlink to, this Public License."
- §3(a)(2): "You may satisfy the conditions in Section 3(a)(1) in any reasonable manner based on the medium, means, and context … it may be reasonable to satisfy the conditions by providing a URI or hyperlink to a resource that includes the required information."
- §3(a)(4): "If You Share Adapted Material You produce, the Adapter's License You apply must not prevent recipients of the Adapted Material from complying with this Public License."
- §2(a)(5)(B) "No downstream restrictions. You may not offer or impose any additional or different terms or conditions on … the Licensed Material if doing so restricts exercise of the Licensed Rights."
- §4(b): including "all or a substantial portion of the database contents in a database in which You have Sui Generis Database Rights" makes that database (not its individual contents) Adapted Material.
- CC's FAQ: "our licenses are currently not compatible with the major software licenses, so it would be difficult to integrate CC-licensed work with other free software" `[read]` (<https://creativecommons.org/faq/>). The FSF lists CC BY 4.0 as a free licence compatible with GPLv3 `[memory]`, not re-read.
- **Verdict** `[analysis]`:
  - **(c) Fetched and displayed** (the main case): compatible. The data is not combined into the code. Every page or report showing breach data needs "Data from Have I Been Pwned" linked to <https://haveibeenpwned.com>, a CC BY 4.0 link, the breach's own `Attribution` value where present, and a note when the description is shortened or reworded.
  - **(b) Bundled snapshot** (for example a catalogue file shipped so the instance contacts nobody): allowed as a separate CC BY 4.0 file in the aggregate, labelled CC BY 4.0, never AGPL, with a source note ("Have I Been Pwned breach catalogue, fetched <date> from https://haveibeenpwned.com/api/v3/breaches"), a licence link and a note of any transformation. Do not merge it into Unlist's CC0 list: the result would be Adapted Material needing CC BY attribution, so it would no longer be plain CC0.
  - Logos (`LogoPath`) were not shown to be under CC BY. Do not bundle them, and do not hotlink them (that also makes the browser contact a third party).
  - **Principle, not licence:** HIBP is a proprietary online service. The catalogue fetch and the per-address lookup must be off by default and marked nonfree in the UI (AGENTS.md). A bundled CC BY snapshot is free data, needs no contact with HIBP, and could be the documented free alternative for the catalogue. No free alternative for per-address lookup is established here.

## 8. Python (CPython)

- `LICENSE` section B: "Python software and documentation are licensed under the Python Software Foundation License Version 2. Starting with Python 3.8.6, examples, recipes, and other code in the documentation are dual licensed under the PSF License Version 2 and the Zero-Clause BSD license. Some software incorporated into Python is under different licenses." `[read]` (<https://github.com/python/cpython/blob/62a7400/LICENSE>).
- PSF License §2 grants rights to "reproduce, analyze, test, perform and/or display publicly, prepare derivative works, distribute, and otherwise use Python alone or in any derivative version, provided, however, that PSF's License Agreement and PSF's notice of copyright, i.e., 'Copyright (c) 2001 Python Software Foundation; All Rights Reserved' are retained". §3 asks a derivative work to "include … a brief summary of the changes made to Python". §7 grants no trademark rights `[read]`.
- The same file's history table marks "2.2 and above … PSF … yes" under "GPL-compatible?", with the footnote "GPL-compatible doesn't mean that we're distributing Python under the GPL … The GPL-compatible licenses make it possible to combine Python with other software that is released under the GPL" `[read]`. This is the PSF's own statement. The FSF's matching entry is `[memory]`.
- **Verdict** `[analysis]`: compatible. Running AGPL code on Python creates no obligation. Python is a "generally available free program used unmodified", outside Unlist's Corresponding Source (§1). Unlist does not modify Python, so the §3 summary of changes does not apply.
- **Container caveat** `[analysis]`: if the project publishes a container image (ADR 0001 says "one container"), it distributes Python and the image's base operating system. A Debian-based image contains GPL and LGPL programs (shell, C library, coreutils and others) `[memory]`, and distributing their binaries brings the duty to offer their source. Python's own bundled parts (OpenSSL, expat, libffi, zlib, SQLite and so on) carry permissive or public-domain licences `[memory]`. This is outside the eight items asked about and needs its own check once the base image is chosen. Publishing the `Containerfile` alone, and letting Operators build it, avoids distributing the binaries.

## Obligations checklist for the RC

Concrete items the v1.0.0-rc1 release must contain. `[analysis]` unless quoted above.

1. **Unlist's own AGPL source offer (§13).** Every page, or at least a prominent footer or menu item, offers the Corresponding Source of the running version "from a network server at no charge". The default can point at the release tag. An Operator who changes the code must be able to point it at their own source; this is the one setting a sensible default cannot replace, because AGPL §13 binds modified versions.
2. **Appropriate Legal Notices in the UI (AGPL §0 and §5(d)).** An About page showing Unlist's copyright, that there is no warranty, that it is licensed under AGPL-3.0-or-later, and how to view the licence.
3. **`THIRD-PARTY-NOTICES` file in the repository and every release artifact (tarball, image)**, also reachable from the About page, with the full text of:
   - Django `LICENSE` and `LICENSE.python`, plus PyDispatcher's notice (`django/dispatch/license.txt`);
   - if the admin is enabled: the jQuery, Select2 and XRegExp MIT notices;
   - `asgiref` and `sqlparse` BSD-3-Clause notices;
   - gunicorn `LICENSE` **and `NOTICE`** (the wheel does not carry `NOTICE`);
   - htmx 0BSD (not required, but listed so the JavaScript is clearly free);
   - JustDeleteMe MIT notice, if its data ships;
   - Python's PSF licence, if an image ships.
4. **Public Suffix List:** `public_suffix_list.dat` shipped byte-for-byte with its MPL header, a copy of the MPL-2.0 text beside it (e.g. `data/LICENSE.MPL-2.0`) or at least the URL, an entry in the notices file naming the file, its licence and its upstream URL, and the snapshot date. No runtime refresh unless the Operator turns it on.
5. **Organization Lists as separate, labelled files:**
   - the official list derived from datenanfragen: `CC0-1.0`, with a credit line to datenanfragen.de;
   - JustDeleteMe-derived data: a separate list labelled `MIT` with its copyright and permission notice. Not merged into the CC0 list.
   - Each list file states its licence inside it (a header or metadata field), so it stays correct when fetched alone.
6. **HIBP attribution in the UI**, wherever breach data appears (lists, detail pages, exports, emails or reports to a Subject): "Data from Have I Been Pwned", linked to <https://haveibeenpwned.com>, plus a link to CC BY 4.0, the breach's `Attribution` field when present, and "shortened" or "modified" when the description is not shown verbatim. The HIBP feature is off by default and marked nonfree.
7. **If an HIBP catalogue snapshot ships:** a separate file labelled CC BY 4.0, with the source URL, the fetch date and a note of any transformation. No logos.
8. **JavaScript licence information.** htmx served from the instance's own static files with a licence comment, and a short "JavaScript licence information" page (file, licence, source link) covering htmx and any admin JavaScript.
9. **Licence check for every added package.** Generate a list of the installed distributions and their licence metadata at release time and compare it with the notices file, because Django and gunicorn may gain dependencies in later versions.
10. **Container image, if one is published:** a separate check of the base image's licences and source offers before the RC ships an image.

## Could not verify

- **The FSF licence list and GPL FAQ** (<https://www.gnu.org/licenses/license-list.html>, <https://www.gnu.org/licenses/gpl-faq.html>): `www.gnu.org` reset the connection (curl error 35, proxy log "ws_closed_mid_exchange") twice at about 15:32 UTC, and again at 15:33:59 UTC after a one-minute wait. The web-fetch tool returned `ENOTFOUND www.gnu.org` (the host is outside this session's allowed network). Nothing was routed around. All FSF compatibility statements here (Modified BSD, Expat/MIT, 0BSD, MPL-2.0, Python, CC0, CC BY 4.0) are `[memory]`. The verdicts rest on the licence texts, and for MPL-2.0 on its own explicit naming of the AGPL as a Secondary License. To close this: allow `www.gnu.org` in the session's network settings and re-read the list's entries for these licences.
- **mozilla.org MPL FAQ**, **publicsuffix.org**, **docs.python.org**, **djangoproject.com** and **htmx.org**: the agent proxy refused the tunnel (HTTP 403, host not allowed). Each project's licence was read from its own repository instead. Not needed for the verdicts.
- **Public Suffix List licence history**: whether any of the list was ever offered only under MPL 1.1 (MPL-2.0 §1.5(b)) was not checked. Exhibit B is absent, and the list is offered under MPL-2.0 today `[memory]`.
- **HIBP brand guidelines** (`brand.haveibeenpwned.com`) and the licence of breach logos: not reachable or not stated. Carried over from `hibp-api-terms.md`.
- **Container base image** licences and source-offer duties: out of scope, not checked.
- **Wheel contents**: whether the published Django, asgiref and sqlparse wheels contain exactly the `license-files` listed was inferred from `pyproject.toml` / `setup.cfg`, not checked by installing them.
- **LibreJS web-labels format**: `[memory]`; its documentation is on gnu.org.

## Verification log

| Time (UTC, 2026-11-26) | Request | Result |
|---|---|---|
| ~15:32 | `curl` www.gnu.org `license-list.html`, `gpl-faq.html` | Connection reset by peer (×2) |
| 15:33:59 | Retry of both | Connection reset by peer (×2) |
| ~15:34 | Web-fetch tool, `license-list.html` | `ENOTFOUND www.gnu.org` |
| ~15:35 | creativecommons.org CC BY 4.0 legal code | 200, read |
| ~15:35 | mozilla.org MPL FAQ, publicsuffix.org `/learn/` and `/list/`, docs.python.org licence page, djangoproject.com, htmx.org | Proxy refused (403) |
| ~15:40 | creativecommons.org `/faq/` | 200, read |
| — | `git clone --depth 1` of the nine repositories above | All succeeded, read only |
