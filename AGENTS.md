# Unlist

Self-hosted alternative to personal-data removal services such as DeleteMe and Incogni. Domain language lives in `GLOSSARY.md`.

## Principles

These rank above convenience and features.

- **Tao:** simple and unforced. Fewest moving parts, good defaults over settings, nothing done without being asked. Done means nothing left to remove.
- **Free Software, as St IGNUcius would approve:** AGPL, free dependencies only, the user stays in control of their own computing. Flag anything that leans on a proprietary service instead of quietly adding it.

What these rule out in practice is being decided in https://github.com/Hjiaky/Unlist/issues/22.

## Planning

The road to v1.0.0-rc1 is charted as a wayfinder map: https://github.com/Hjiaky/Unlist/issues/1. Research findings live in `docs/research/`.

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
