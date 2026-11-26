# Organization Lists

To ask an organization for your data, Unlist needs to know **who it is and how to reach its privacy contact**: the email address, postal address or web form for data protection requests, whether it is a Broker, and what it tends to ask for. That knowledge comes from **Organization Lists**.

## What a list is

An Organization List is a shareable file describing Organizations, published at a web address. It works like the filter lists of an ad blocker: an instance can subscribe to several, put them in an order, and add its own corrections on top.

- **Format.** One JSON file with a header (name, licence, homepage, version, date) and a list of records. A published JSON Schema describes it. When Unlist loads a list, a record that does not fit is skipped with a note, and the previous version of the list is kept.
- **Records.** One per organization that must answer requests (the "controller"): name, brands, web domains, contacts (privacy email, postal address, web form, phone), what identification it asks for, the language to use, the supervisory authority, a Broker flag, and a quality mark: *verified*, *tested* or *scraped*.
- **Plain files.** Lists are data you can open and read. Unlist keeps them in its one database file but the bundled originals ship as plain JSON.

## The lists that come with Unlist

Unlist comes with its lists built in, so it works offline. Each release carries a dated snapshot.

| List | What it is | Licence |
|---|---|---|
| **Unlist official Organization List** (`organizations.json`) | About 3,000 Organizations with privacy contacts, seeded from the open database behind [datarequests.org](https://www.datarequests.org) (`datenanfragen/data`), plus Brokers that Unlist maintains. | **CC0 1.0**, public domain |
| **JustDeleteMe domains** (`jdm-domains.json`) | Web domains from the [JustDeleteMe](https://justdeleteme.xyz) project, mapped onto the official records so that more mail senders can be matched. It holds no contacts. | **MIT** (notice kept in the file) |
| **Breach catalogue** (not an Organization List) | The free breach list of Have I Been Pwned, used by the [breach check](first-run.md#the-breach-check). | **CC BY 4.0**, attribution shown wherever it is used |

Unlist is not endorsed by datarequests.org, JustDeleteMe or Have I Been Pwned. The Public Suffix List (used to find a sender's registrable domain) is bundled unmodified under the MPL-2.0. All notices are in `THIRD-PARTY-NOTICES` and on the About page.

Only data with a free licence that can be combined with the AGPL is bundled. Lists under non-commercial licences are not copied in.

## The settings page

Open **Organization Lists** in the sidebar (`/organizations/lists/`). You see each list with its order, version, date and when it was last updated.

- **Order.** Move lists up and down. **A higher list wins, field by field:** for each field of a record, the highest list that has a value for it is used. Records from different lists are matched by their slug or by a shared domain.
- **Enable or disable** a list. Bundled lists can be disabled but not removed.
- **Conflicts are shown.** A web domain claimed by two different Organizations matches neither until you resolve it locally.

## Subscribing to another list

On the same page, under "Add a list", enter the web address of a list file. Unlist fetches it **once**, right then, because you asked, and puts it at the **lowest** position. Move it up if you want it to win.

Anyone can publish a list: a household, a club, a consumer group, a company that wants to document its own privacy contacts. If you run your own, you only need to host the JSON file.

## Updating

**Updating is manual and never automatic.** Press **Update lists** and Unlist refetches the lists you subscribed to by address. A press is the only time it contacts anyone for this. Without the press, nothing is fetched, ever.

Bundled lists do not update that way. They change with Unlist releases (see [upgrading](install.md#upgrading)).

**Contact review.** If an update changes the privacy contact of an Organization you already have a Case with, the new contact is not applied automatically. It appears on a review page (`/organizations/pending/`) side by side with the old one, and applies only after you accept it. This stops a bad update from redirecting requests.

## Local overrides

A list entry may be out of date or wrong. On an Organization's page you can **override** any field locally: the contact, its domains, the request language, the Broker flag, the re-check interval and so on. Your overrides beat every list, and they survive updates. You can delete an override again.

An organization on no list becomes a **local stub**. Nothing is sent to a stub until you have confirmed its contact.

A contact marked *scraped* is flagged, and you confirm it before the first request.

## Contributing back

If you fixed a contact or found a missing Organization, others can benefit.

1. On the Organization's page, press **Export overrides as a suggestion (JSON)**. It downloads your overrides for that Organization as a record in the list format.
2. Send it **upstream first.** The company contact data in the official list comes from datarequests.org, so a correction to an address or email belongs in their open database (`datenanfragen/data` on GitHub), where it helps everyone who uses it. Unlist's own list picks it up from there.
3. Send Unlist-specific things (the Broker flag, domains used for matching, re-check defaults, EU/UK Brokers missing from the list) as a pull request to the Organization List repository with a source for each claim. Until that repository is split out, the list and its build tool live in the Unlist repository under `tools/organization-list/` (see its README).

**Please do not send** personal data, or contacts you have not checked on the organization's own page. A named person's email address is not published in the official list.

## Good to know

- A Broker is marked everywhere in Unlist. Brokers come back more often, so they get a shorter re-check interval (90 days).
- The official list is a snapshot. Organizations move and merge. When an old record has a replacement, its open Cases are carried over with their history and deadlines.
- Contact data is only as good as its source. Where an entry looks wrong, trust the organization's own privacy page over any list.
