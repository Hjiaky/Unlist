# Unlist

Self-hosted alternative to personal-data removal services such as DeleteMe and Incogni. Domain language lives in `GLOSSARY.md`.

## Principles

These rank above convenience and features. Principled, not hardcore. Decided in https://github.com/Hjiaky/Unlist/issues/22.

### Free Software, as St IGNUcius would approve

- Unlist's own code is **AGPL-3.0-or-later**.
- Every dependency and bundled data file carries a free licence that can be combined with the AGPL. Check once when adding it.
- Proprietary online services (cloud LLMs, Have I Been Pwned and similar) are optional, off by default, marked as nonfree in the UI, and only allowed where a free alternative exists and is documented. Unlist is complete without them.
- The instance contacts nobody unless the Operator turned that on. No telemetry.
- JavaScript is fine, but free-licensed and served from the instance: no CDNs, no third-party fonts or scripts.
- The project lives on GitHub; the app must never depend on GitHub.
- Flag anything that leans on a proprietary service instead of quietly adding it.

### Tao

The RC is the core loop: import mail, discover Organizations, send requests, track, re-check. An extra ships only if it adds no new service, dependency or setting. Check every build ticket against these:

1. One container, one database file, no extra services to run.
2. Works with no configuration beyond adding a Subject and importing mail. A setting exists only if a sensible default cannot.
3. Data stays inspectable: plain files for lists and templates, one SQLite file for state.
4. The instance contacts nobody unless the Operator turned that on.
5. Gentle first: polite request, then a reminder, then a Complaint draft. Never threats, never compensation demands.
6. No nagging, no streaks, no scores that exist to pull the Operator back in.
7. A feature is done when nothing can be removed from it. A new feature must say what it lets us remove, or why the core loop is incomplete without it.

Every email leaving in a Subject's name is approved first. Reading, matching, deadline tracking and reminders to the Operator run on their own.

## Working with the human

Ask the human only high-value decisions: hard to reverse, changing scope, touching the principles above, or carrying legal or privacy risk for Subjects. Decide everything else yourself with the best default, and record it on the ticket as "decided by agent" so it can be overturned. When unsure whether something is high-value, decide it and say so plainly.

## Planning and building

- The spec is `docs/spec/v1.0.0-rc1.md`. Each section links the decision behind it on the (closed) wayfinder map, https://github.com/Hjiaky/Unlist/issues/1.
- The build backlog is https://github.com/Hjiaky/Unlist/issues/37 and its sub-issues. Take a ticket whose `Blocked by:` issues are all closed.
- Research findings live in `docs/research/`, prototypes in `docs/prototypes/`, and architecture decisions in `docs/adr/`.

## Subagent models

Pick the cheapest model tier that does the job well; don't run every subagent on the session's model.

- **Fastest tier:** lookups, file and code searches, mechanical edits, fetching a page for one fact.
- **Middle tier:** research tickets that read documentation, APIs and repositories and summarise them with sources.
- **Most capable tier:** work a decision rests on and that is hard to check afterwards: legal and licence reasoning, security review, architecture review.
- Grilling and prototype tickets stay in the main session with the human.

## Agent skills

### Issue tracker

Issues, specs and wayfinder maps live in GitHub Issues on `hjiaky/unlist`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
