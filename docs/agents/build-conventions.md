# Build conventions

How code is laid out, so that tickets built in parallel fit together. Read `AGENTS.md`, `GLOSSARY.md` and the spec (`docs/spec/v1.0.0-rc1.md`) first.

## Layout

One Django app per area, all registered in `unlist/settings.py` and mounted in `unlist/urls.py`:

| App | URL prefix | Owns |
|---|---|---|
| `unlist.core` | `/` | Operator setup and login, base template, middleware, scheduler registry (`unlist/core/scheduler.py`) |
| `unlist.subjects` | `/subjects/` | Subject, consent record, identifying details, mailboxes and their mode |
| `unlist.organizations` | `/organizations/` | Organization, Organization Lists (loading, merging, overrides, updates), domains, Supervisory Authorities |
| `unlist.cases` | `/cases/` | Case and its events, the lifecycle state machine, deadlines (`deadlines.py`), mail templates and rendering, replies, ID handling, re-checks, Complaints |
| `unlist.mail` | `/mail/` | mbox import, the discovery scanner, optional IMAP and SMTP |
| `unlist.breaches` | `/breaches/` | breach catalogue snapshot and matching |
| `unlist.stats` | `/statistics/` | statistics dashboard and monthly snapshots |
| `unlist.llm` | `/llm/` | the optional LLM endpoint and its four jobs |
| `unlist.legal` | `/about/` | About page, source link, notices, JavaScript licence page |
| `unlist.backup` | `/backup/` | backup and restore commands and the settings button |

- Each app has `models.py`, `views.py`, `urls.py` (with `app_name`), `templates/<app>/`, `tests.py` (or a `tests/` package) and its own migrations. **Only touch other apps when the ticket requires it.**
- Put logic that does not need the database in plain modules with pure functions (for example `unlist/cases/deadlines.py`, `unlist/mail/scanner.py`). Test them without the database where possible.
- Data files that ship with a release live under `unlist/<app>/data/`, each with its licence next to it.
- Scheduler jobs: decorate a function `f(now) -> str | None` with `@unlist.core.scheduler.job` in a module the app imports from `AppConfig.ready()`. Jobs only prepare work; nothing is ever sent by the scheduler.

## Code

- Every source file starts with:
  ```
  # SPDX-License-Identifier: AGPL-3.0-or-later
  # Copyright (C) 2026 The Unlist contributors
  ```
  (HTML and CSS files: the same as a comment where the format allows.)
- Python 3.12+, Django 5.2. `ruff check` and `ruff format` with the settings in `pyproject.toml` (line length 120).
- Use the glossary's words in names: `Subject`, `Organization`, `Case`, `Listing`, `AccessRequest`, `RemovalRequest`, `SuppressionRecord`, `Complaint`, `SupervisoryAuthority`, `OrganizationList`, `Operator`. Never `user` for a Subject, `company` for an Organization, or `opt-out` for a Removal Request.
- No new dependency without a free, AGPL-compatible licence and a reason the standard library or Django cannot do it. Add it to `requirements.txt` with a comment.
- Nothing may contact another host unless the Operator explicitly triggered it (a button) or switched it on. Tests must not touch the network.
- Pages extend `unlist/base.html` and put their content in `{% block content %}`. No inline `<script>` or `style=""` (the Content-Security-Policy forbids them); use classes in `unlist/core/static/unlist/unlist.css` or an app stylesheet under `unlist/<app>/static/<app>/`.

## Mail templates

- Plain-text files at `unlist/cases/mail_templates/<lang>/<kind>.txt`, rendered with Django's template language in a separate engine with autoescaping off (so `{% if %}` can drop optional paragraphs).
- First line `Subject: ...`, then one blank line, then the body.
- Variables are documented in `unlist/cases/mail_templates/README.md`.

## Tests and checks

- `UNLIST_TESTING=1 python manage.py test` must pass, along with `ruff check .`, `ruff format --check .` and `UNLIST_TESTING=1 python manage.py makemigrations --check --dry-run`.
- Each ticket's "Done when" criteria become tests.

## Commits

One commit per ticket (or a few), message starting with the ticket's title and naming the ticket number, ending with the attribution lines the session asks for.
