# 1. Python, Django and SQLite in one container

Date: 2026-11-26
Status: Accepted
Decided in: https://github.com/Hjiaky/Unlist/issues/3

## Context

Unlist is a self-hosted app for one household. Its core is mail handling: reading `.mbox` exports and optionally IMAP, parsing headers, sending over SMTP or handing `.eml` files to the Subject. It needs a small web UI, a scheduler that only prepares work, and one database file. The principles in `AGENTS.md` ask for free dependencies only, few moving parts, one container and no third-party requests from the browser.

Three stacks were weighed:

- **Python + Django:** the standard library already handles mbox, email parsing, IMAP and SMTP. Django brings the database layer, migrations, forms, login, sessions and CSRF protection in one package. It has a large contributor pool. The image is around 150 MB.
- **Go:** one small binary and a tiny image, but mail handling, forms, migrations and login would come from several third-party libraries or be written by hand.
- **TypeScript / Node:** one language end to end, but many small npm dependencies (more moving parts, more supply-chain risk), and mail handling from third-party packages.

## Decision

Build Unlist in **Python with Django**, storing state in **one SQLite file**, with pages rendered on the server and a little local JavaScript (htmx), all inside **one container**.

## Consequences

- Mail handling rests on the Python standard library (`mailbox`, `email`, `imaplib`, `smtplib`), so the core needs no third-party mail code.
- Dependencies stay few and free: Django (BSD-3-Clause) and htmx (BSD Zero Clause), plus a bundled Public Suffix List snapshot (MPL-2.0). Each new dependency is checked against the AGPL once, when it is added.
- The image is larger than a Go binary would be. Accepted in exchange for fewer dependencies and less hand-written plumbing.
- Changing language later would mean a rewrite. That is why this record exists.
