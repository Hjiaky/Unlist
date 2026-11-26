<!--
SPDX-License-Identifier: CC0-1.0
Copyright (C) 2026 The Unlist contributors
-->
# Public holidays (`holidays.json`)

The deadline engine (`unlist/cases/deadlines.py`) uses this file to move a due date that falls on a public holiday of the Organization's country to the next working day. Weekends (Saturday and Sunday) are always skipped and are not listed here.

**National holidays only. Check before relying on them.** Regional, state, cantonal and local holidays are not included, so a deadline at an Organization in, say, Bavaria or Catalonia may in fact be a day later than Unlist says. Unlist adds 3 days of grace before it calls a request overdue, which covers most of these gaps.

## Source and licence

Written for Unlist in November 2026 from public knowledge of each country's national holiday law (listed below). It was not checked line by line against the official texts. Holiday dates are facts and not copyrightable; to the extent this compilation is, it is dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/), which is compatible with Unlist's AGPL-3.0-or-later.

| Code | Country | Basis | Not included |
|---|---|---|---|
| AT | Austria | Feiertagsruhegesetz 1957 | Good Friday, 24 December |
| BE | Belgium | Royal Decree of 18 April 1974 | replacement days for holidays on a Sunday |
| CH | Switzerland | Federal Constitution Art. 110(3) (1 August); New Year's Day, Ascension Day and Christmas Day are observed in every canton | all other cantonal holidays |
| CZ | Czechia | Act No. 245/2000 Coll. | — |
| DE | Germany | Unity Treaty (3 October); the other eight are in every state's holiday law | state holidays (Epiphany, Corpus Christi, Reformation Day, All Saints' Day, Day of Repentance, and others) |
| DK | Denmark | Danish public holidays (helligdage); General Prayer Day abolished from 2024 | Constitution Day, Christmas Eve, New Year's Eve |
| ES | Spain | Workers' Statute Art. 37.2 and the yearly national calendar | regional holidays, Maundy Thursday, holidays moved from Sunday to Monday |
| FI | Finland | Public holidays, plus Midsummer Eve and Christmas Eve from the act on calculating statutory time limits (150/1930) | — |
| FR | France | Code du travail Art. L3133-1 | Alsace-Moselle (Good Friday, 26 December), overseas holidays |
| GB | United Kingdom (England and Wales) | Banking and Financial Dealings Act 1971 and royal proclamations; Christmas Day and Good Friday by custom | Scotland and Northern Ireland, which have different bank holidays; one-off bank holidays proclaimed for a single year |
| IE | Ireland | Organisation of Working Time Act 1997, Schedule 2 (Saint Brigid's Day from 2023) | — |
| IT | Italy | Law 260/1949 as amended; Saint Francis' Day (4 October) again a national holiday from 2026 | local patron saints' days |
| LU | Luxembourg | Code du travail Art. L.232-2 (Europe Day from 2019) | compensatory days for holidays on a Sunday |
| NL | Netherlands | Algemene termijnenwet (general time limits act), which includes Good Friday and Liberation Day | — |
| PL | Poland | Act of 18 January 1951 on non-working days, as amended (Christmas Eve from 2025) | — |
| PT | Portugal | Código do Trabalho Art. 234 | Carnival, municipal holidays |
| SE | Sweden | Act 1989:253 on public holidays, plus Midsummer Eve, Christmas Eve and New Year's Eve from the act on calculating statutory time limits (1930:173) | — |

Where a country's law on computing statutory time limits treats extra days like holidays (FI, NL, SE), those days are included, because they only ever make a deadline later.

## Substitute days

England and Wales: when New Year's Day, Christmas Day or Boxing Day falls on a weekend, the next weekday that is not already a bank holiday is a substitute bank holiday ("bank holiday in lieu"). Holidays with `"substitute": true` get this treatment; no other country uses it.

## Format

```json
{"countries": {"DE": {"name": "Germany", "scope": "...", "holidays": [ ... ]}}}
```

Each holiday has an English `name`, an optional `local_name` and `note`, optional `from_year` / `until_year` (inclusive), optional `"substitute": true`, and one `rule`:

| `rule` | Fields | Example |
|---|---|---|
| `fixed` | `month`, `day` | 3 October |
| `easter` | `offset` (days from Western Easter Sunday) | Good Friday is `-2`, Whit Monday `50` |
| `nth_weekday` | `month`, `weekday`, `nth` (`1` first, `-1` last); optional `unless_day_falls_on: {day, weekday}` | last Monday of May |
| `weekday_on_or_after` | `month`, `day`, `weekday` | Midsummer Day: first Saturday on or after 20 June |

Easter is computed with the anonymous Gregorian algorithm, so dates exist for any year without network access. To correct or add a country, edit the JSON and run the deadline tests (`UNLIST_TESTING=1 python manage.py test unlist.cases`).
