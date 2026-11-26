# Unlist

Unlist is a self-hosted app that helps one household find out which companies hold their personal data, and ask them in writing to show it and delete it. It does this with your own mail and your own rights under the GDPR and the UK GDPR: you import old mail, Unlist finds the senders, drafts the requests, tracks the deadlines and re-checks later. It is a free alternative to paid services such as DeleteMe and Incogni, and it runs on your own computer.

One person, the **Operator**, runs it for the people in the household, the **Subjects**, with their consent.

## What it stands for

- **Free software.** Unlist is AGPL-3.0-or-later, and everything it ships with carries a free licence. Online services that are not free software are optional, off by default, and marked as such.
- **Nothing leaves without approval.** Every email sent in a person's name waits for the Operator to approve it. Unlist reads, matches and counts days on its own, but it never sends by itself.
- **It contacts nobody unless you turn that on.** No telemetry, no accounts, no CDNs, no automatic list updates.
- **Import first.** You can use Unlist without giving it a mailbox password: export your mail to a file and import it. A live mailbox connection is an optional extra.

## Status

**Pre-release.** Unlist has not reached v1.0.0-rc1 yet. All features planned for the release candidate exist, but no real household has used it for the four weeks the release needs. Expect rough edges, back up often, and read every draft before you approve it.

Unlist is not a law firm and does not give legal advice. See [what Unlist does and does not do](docs/guide/legal.md) ([auf Deutsch](docs/guide/de/rechtliches.md)).

## Quick start

You need Docker with Compose and about 1 GB of free disk space.

```sh
git clone https://github.com/Hjiaky/Unlist.git
cd Unlist
docker compose up -d --build
docker compose logs unlist
sudo cp key/unlist.key /somewhere/safe/unlist.key
```

What these do:

1. Download Unlist and go into its folder.
2. Build and start it. The first start creates the `data` and `key` folders and generates an encryption key.
3. Show the log, which tells you where the new key is.
4. Copy the key somewhere safe and private, away from `data`. `sudo` is needed only if your own user cannot read the file, which belongs to the container's user.

Then open <http://localhost:8000> (or `http://<this machine>:8000` from another device on your network) and follow [first run](docs/guide/first-run.md). In German: [Schnellstart](docs/guide/de/schnellstart.md).

## The guide

| Page | What it covers |
|---|---|
| [Install and run](docs/guide/install.md) | Requirements, folders, the key, HTTPS, upgrades, every setting |
| [First run](docs/guide/first-run.md) | From the first login to your first Case, replies, deadlines and complaints |
| [Live mailbox connection](docs/guide/live-connection.md) | Optional: read-only IMAP and sending through SMTP |
| [Optional language model](docs/guide/llm.md) | Optional: a local model for suggestions |
| [Backup and restore](docs/guide/backup.md) | What a backup holds, how to restore, how to test it |
| [What Unlist does and does not do](docs/guide/legal.md) | The legal basis, its limits, and what data Unlist keeps |
| [Organization Lists](docs/guide/organization-lists.md) | Where the contact data comes from, and how to update or improve it |
| [Schnellstart](docs/guide/de/schnellstart.md), [Rechtliches](docs/guide/de/rechtliches.md) | The two most important pages in German |

The index is [docs/guide/README.md](docs/guide/README.md). For contributors: the specification is `docs/spec/v1.0.0-rc1.md`, the vocabulary is `GLOSSARY.md`, and the principles are in `AGENTS.md`.

## Licence

Unlist's own code is **AGPL-3.0-or-later** (see `LICENSE`). Third-party software and data, with their licences, are listed in `THIRD-PARTY-NOTICES` and on the About page of a running instance (`/about/`). If you change Unlist and let other people use your instance, the AGPL asks you to offer them your source: set `UNLIST_SOURCE_URL` (see [install](docs/guide/install.md#settings)).

## Reporting problems

Open an issue at <https://github.com/Hjiaky/Unlist/issues>. Unlist itself never depends on GitHub; that is only where the project talks.

**Do not put personal data in an issue.** No real names, addresses, case references or screenshots of replies. Describe what happened with made-up examples. If you think you found a security problem, say so in the issue without details and ask for a private way to send them.
