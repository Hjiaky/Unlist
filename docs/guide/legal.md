# What Unlist does and does not do

[Auf Deutsch: Rechtliches](de/rechtliches.md)

This page says plainly what Unlist is for, what it leaves to you, and what it keeps. It is a description of software, **not legal advice**. Unlist is not a law firm and the people who make it are not your lawyers. If a case matters a lot to you, ask a lawyer or a consumer or data protection advice service in your country.

## The short version

- Unlist helps people use their **own** rights under the GDPR (EU) and the UK GDPR: the right of **access** (Article 15), the right to **erasure** (Article 17) and the right to **object** (Article 21).
- Requests go out **from the person's own email address**, and **each one is approved** by the Operator first.
- Unlist never sends a threat, never asks for compensation, and never submits a complaint for you.
- It never stores ID documents.
- The data stays on your machine. Nothing leaves unless you turn something on.

## What the law gives a person

The GDPR (in the EU) and the UK GDPR (in the United Kingdom) give every person rights over their personal data. These are the ones Unlist uses:

- **Access** (Art. 15). Anyone can ask an organization whether it holds data about them, and ask for a copy, the purposes, the recipients (by name), the source of data it did not get from them, the retention period, and more.
- **Erasure** (Art. 17). Anyone can ask an organization to delete their data where one of the legal grounds applies, for example the data is no longer needed, consent was withdrawn, or the person objected.
- **Objection** (Art. 21). Anyone can object to processing. An objection to **direct marketing** must always be honoured. Other objections need a reason that concerns the person's own situation, and the organization may keep processing if it shows overriding grounds.

Unlist also uses **withdrawal of consent** (Art. 7(3)) and asks the organization to tell the companies it passed the data on to (Art. 19).

Useful facts that Unlist builds on:

- **No form is required.** A plain email is a valid request, in the EU and the UK. An organization may offer a web form or portal, but cannot make it compulsory.
- **No reasons are needed** for an access request, and it is free of charge.
- **One month to answer.** The organization may extend this by up to two further months, but only if it says so, with reasons, within the first month.
- **An organization may ask for proof of identity only if it has reasonable doubt**, and only for what is proportionate. Demanding a copy of an ID document is generally not appropriate, especially when the person writes from an address the organization already knows.
- **Complaints to the regulator are free** and made by the person themselves.

## What Unlist does

- Reads the mail you import and works out **which organizations have written to the person**.
- Drafts a polite **Access Request**, and, once an organization shows it holds data, a **Removal Request** (which stacks erasure, objection and withdrawal of consent). For brokers it also asks them to keep a minimal "suppression record" so they do not collect the person again.
- Waits for the Operator's **approval** for every email, then either sends it (live connection) or hands it over to be sent by the person (import-only).
- Counts the **deadlines**, shows how it did, and prepares a **reminder** and later a **Complaint draft**, always for approval.
- Keeps a dated **timeline** of what happened, as evidence.
- Suggests **re-checks**, because data returns.

## What Unlist does not do

- **It is not legal advice and not a law firm.** It cannot tell you whether an organization's refusal is lawful, whether your own use of Unlist is covered by any exception, or what will happen in court.
- **It does not guarantee results.** Organizations may refuse, for example because a law requires them to keep the data (Art. 17(3)). The European data protection authorities' 2025 review of erasure requests found that the refusals its authorities examined were "overall justified", and noted that some organizations apply exceptions automatically without checking the individual case. A refusal is not always wrong, and it is not always right.
- **It does not lodge Complaints.** The Subject lodges their own Complaint with their own Supervisory Authority. Unlist writes a draft and shows where to send it.
- **It never stores ID documents.** If a Subject decides to send one, they attach it from their own device, ideally with unneeded details blacked out. Unlist records only that ID was sent, and when.
- **It never threatens or demands compensation.** The tone is gentle first: a polite request, then a reminder, then a Complaint draft.
- **It does not monitor the web, scrape sites, or sign anyone up for anything.** It works from mail you give it and lists you give it.

## Consent of each household member

Unlist acts for a person **only with their consent**. When you add a Subject, you record who agreed (the person, or a parent for a child), when, and exactly what it covers: import their mail, send access and removal requests from their address (each approved first), read and store replies, and draft complaints. Consent can be withdrawn at any time, and open Cases then stop. Deleting a Subject erases everything about them.

**Children.** A child's data rights belong to the child. A parent or guardian can act on their behalf where the child is not mature enough to do so. The ages in the GDPR's Article 8 are ages for giving *consent* to online services, not ages for making rights requests. Unlist asks for a parent's consent for anyone under 18, and flags children from age 12 as needing their own involvement. That 12 is Unlist's own cautious rule, not a legal limit.

**Acting for someone else.** The GDPR does not itself regulate representation; national law does. An organization may ask for proof that you may act for the person. Unlist can generate a dated **letter of authority**, for one organization only, for the Subject to sign. In the UK, the person who acts for someone else is responsible for providing the evidence.

## Where requests come from

Every request is written **in the Subject's name and sent from the Subject's own address**. That is deliberate: an organization knows that address, so it can match the request to its records without asking for ID. Unlist does not send from its own address, because it has none. The Operator is the person who presses "approve".

## What data Unlist keeps, and where

Everything is in **one folder** (`./data`): one SQLite database file and a folder of attachments.

**It keeps:**

- Subjects: name, country, addresses, identifying details you add, year of birth, the consent record.
- Discovery results: per organization, its name and domain, first and last date seen, the number of emails, the kind of evidence, and the subject line of the strongest email.
- Cases: drafts, the exact sent text, replies and their attachments, dates, the timeline.
- Settings, local overrides to Organization Lists, and (encrypted) mailbox app passwords and a language-model key.

**It never keeps:**

- **Mail bodies** from discovery. Message bodies are read only to check for order markup and keywords, then discarded. (Replies to your requests are kept in full, as evidence.)
- **ID documents.**

**Encryption.** Only passwords and keys are encrypted (with a key kept outside the data folder). Everything else is readable by anyone who can read the folder. Protect the machine and its disk. A [backup](backup.md) is just as sensitive as the data.

**What leaves the instance, and only if you ask for it:**

| What | When |
|---|---|
| The emails you approve, to the organization | When you approve and send (or send yourself) |
| Mailbox access over IMAP and SMTP | Only if you set up a [live connection](live-connection.md); scheduled re-scans only if you switch them on |
| Text for a language model | Only if you switch on the [language model](llm.md); a remote endpoint is a nonfree service |
| A list download | Only when you press "Update lists" for lists you subscribed to by URL |
| A request to Have I Been Pwned | Only when you press "Update breach list" (a nonfree service) |
| A page fetch | Only when you press "Find privacy contact" and paste an address (needs the language model) |

There is **no telemetry**, no account with Unlist, no automatic update check. The project does not receive anything from your instance.

## Limits

- **EU and UK only.** Unlist is built around the GDPR and the UK GDPR. It does not do US-style web-form opt-outs. A Subject in another country can be added, but the legal wording and the complaint authorities are for the EU and UK.
- **English and German templates.** For an organization that expects another language, Unlist uses English; a language model, if you set one up, can offer a translation to review. Read it before you approve it.
- **Deadlines use national public holidays** that ship with Unlist, for 17 countries, and only national ones: AT, BE, CH, CZ, DE, DK, ES, FI, FR, GB, IE, IT, LU, NL, PL, PT, SE. They were written from public knowledge of each country's holiday law and **should be checked** against an official calendar if a date matters. For other countries only weekends are skipped. A 3-day grace before "overdue" covers many gaps.
- **Contacts may be wrong.** The Organization Lists are community data. A contact that is only scraped is flagged, and you confirm it before the first request. A list update that changes the contact of an organization you already wrote to waits for your decision.
- **The law moves.** Examples at the time of writing: in the UK, the data protection regulator is now called the Information Commission (its website still says "ICO"), and new statutory rules on stopping the clock and complaining to the organization came into force in 2026. In the EU, a proposal ("Digital Omnibus") to restrict abusive access requests has been put forward but not adopted, and a new regulation will fix what a cross-border complaint must contain from 2 April 2027, including that the request was made to the organization first. Unlist's drafts are built to fit this, but a release can lag behind.
- **Some points are unsettled.** For example, the EU rule that the clock pauses while an organization waits for identity information is the European Data Protection Board's interpretation, not the text of the GDPR. National rules on representation before a regulator were not checked.

The research behind Unlist's wording, with every claim traced to its source, is in `docs/research/gdpr-request-requirements.md` in the repository.

## If you are unsure

If you are not sure whether to use Unlist for a particular person or a particular situation (a dispute with an organization, a child, someone who has died, someone who cannot decide for themselves), stop and get proper advice first. Unlist is happy to wait.
