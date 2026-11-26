# Household trial checklist (before v1.0.0-rc1)

The release candidate is tagged only after one real household has used a pre-release on real mailboxes for at least four weeks, sending real requests (spec section 17, item 6). This page lists what the trial should cover and what to record. File every problem as a GitHub issue, or fix it, before the tag.

Tracked in https://github.com/Hjiaky/Unlist/issues/58; the open mailbox questions are https://github.com/Hjiaky/Unlist/issues/25.

## Before you start

- [ ] Install the pre-release by following `docs/guide/install.md` exactly. Note every step that was unclear or wrong.
- [ ] Copy `./key/unlist.key` somewhere safe.
- [ ] Take a backup right away and restore it into a throwaway second instance (`docs/guide/backup.md`, "Test a restore in three steps").

## Week 1: import and discovery

- [ ] **Google Takeout** (issue #25, point 1): export Mail only, as mbox, and import it. Record whether it is one file or several, its size, how long the import took, and whether anything looked wrong.
- [ ] **Another provider's export**, if anyone in the household uses one (GMX, WEB.DE, Posteo, Thunderbird's local folders exported as mbox...).
- [ ] **Discovery quality** (issue #25, point 5): go through the discovery list per Subject.
  - Note Organizations that are clearly wrong: misgraded evidence, newsletters shown as accounts, personal contacts that slipped through.
  - Note obvious ones that are missing.
  - Count how many messages had order markup, using the evidence kind "order markup".
- [ ] **Unassigned senders:** assign a few; check that a re-import keeps the assignments and the ignores.
- [ ] **Optional live connection** (issue #25, points 2 to 4): connect one Gmail mailbox with an app password.
  - Check mail stays unread and a scan finishes.
  - Note what Unlist shows for `\All` / All Mail.
  - If anyone has Outlook.com, try an app password and record what happens.

## Weeks 1 to 2: requests

- [ ] Open Cases for 10 to 20 Organizations, including at least two Brokers.
- [ ] Read every draft before approving it. Note wording that is wrong, unclear or too long, in English and German.
- [ ] Send in import-only mode (`.eml` or `mailto:`), and in live mode if connected. Check that the reference code arrives in the subject line, and that From is the Subject's own address.
- [ ] Check the computed deadlines against a calendar, especially around public holidays.

## Weeks 2 to 4: answers

- [ ] Feed replies in by re-importing, uploading `.eml` files or a live scan. Note every mis-match and every wrong suggested outcome.
- [ ] Note how each Organization answered: data sent, nothing held, ID demanded, portal only, refused, silence.
- [ ] Use at least one reminder, and if it comes to it, look at (do not necessarily lodge) one Complaint draft and its evidence bundle.
- [ ] If an ID document is demanded, walk the pushback. Check nothing is ever stored.
- [ ] Look at the statistics and the breach check. Note anything confusing.

## Legal and data checks before the tag

These are open from the build and need a human eye. Each is listed on its GitHub ticket.

- [ ] **Holiday data** in `unlist/cases/data/holidays.json`, written from memory (#42). Most worth checking:
  - IT 4 October
  - PL Christmas Eve
  - IE St Brigid's Day
  - DK Great Prayer Day
  - LU Europe Day
  - CH
  - the FI and SE eves
  - NL Good Friday
- [ ] **Deadline rules marked uncertain** in #42: the late UK ID request, the UK day-of-receipt count, the EU pause and the extension cut-off.
- [ ] **Template legal statements** in `unlist/cases/mail_templates/LEGAL-CHECK.md`, especially the ones listed as unsure in #43 and the `id_copy_reply` template from #50.
- [ ] **Licence of the template texts:** CC0, decided by agent in #43; confirm.
- [ ] **UK first step:** the s.164A complaint to the Organization is offered only when both the Subject and the Organization are UK (#52); confirm.
- [ ] **Organization List:** decide the 7 borderline Brokers, and confirm the `[S]` contacts (#41).
- [ ] **Mail provider presets**, all marked unverified, in `unlist/mail/data/mail-providers.json` (#48).
- [ ] A native German speaker proofreads `docs/guide/de/` and the German templates.

## Then

- [ ] Fix or file everything found.
- [ ] Set the version to `1.0.0rc1` (`pyproject.toml` and `unlist/__init__.py`).
- [ ] Push the tag `v1.0.0rc1`. The release workflow publishes the image.
