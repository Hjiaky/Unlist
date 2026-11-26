// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 The Unlist contributors
//
// Browser smoke test of the UI (#53). Not part of CI (CI has no browser); run it locally:
//
//     node scripts/ui-smoke.mjs                 # walk the first run, check phone width
//     node scripts/ui-smoke.mjs --screenshots   # also write docs/prototypes/screenshots/*.png
//
// Needs: the project's virtualenv (.venv, see CONTRIBUTING or AGENTS.md) or a `python3` with the
// requirements installed, and Node with the `playwright` package and its Chromium (installed
// locally or globally; this script does not install anything). It starts a throwaway instance in
// a temporary directory (UNLIST_DATA_DIR, UNLIST_KEY_FILE) on a free local port, walks the first
// run (create the Operator, add a Subject, record consent, import a tiny mbox), opens Cases with
// "Pursue", approves two drafts together on "Needs you" (checking both recipients are on the
// summary screen), then loads the main pages at 390 px and fails if any scrolls sideways.
// Nothing contacts another host: the fixture mbox and the bundled lists are local.

import { execFileSync, execSync, spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SCREENSHOTS = process.argv.includes('--screenshots');
const SHOTS_DIR = path.join(ROOT, 'docs', 'prototypes', 'screenshots');
const FIXTURE = path.join(ROOT, 'scripts', 'ui-smoke.mbox');
const PASSWORD = 'a long enough passphrase for testing';
const PHONE = 390;

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  try {
    return require('playwright');
  } catch {
    const globalRoot = execSync('npm root -g').toString().trim();
    return require(path.join(globalRoot, 'playwright'));
  }
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

async function waitFor(url, tries = 100) {
  for (let i = 0; i < tries; i++) {
    try {
      const response = await fetch(url, { redirect: 'manual' });
      if (response.status < 500) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`The app did not start at ${url}`);
}

const failures = [];
function check(condition, message) {
  if (condition) {
    console.log(`  ok   ${message}`);
  } else {
    console.log(`  FAIL ${message}`);
    failures.push(message);
  }
}

async function main() {
  const { chromium } = loadPlaywright();
  const python = existsSync(path.join(ROOT, '.venv', 'bin', 'python')) ? path.join(ROOT, '.venv', 'bin', 'python') : 'python3';
  const tmp = mkdtempSync(path.join(os.tmpdir(), 'unlist-ui-'));
  const env = {
    ...process.env,
    UNLIST_DATA_DIR: path.join(tmp, 'data'),
    UNLIST_KEY_FILE: path.join(tmp, 'key', 'unlist.key'),
    UNLIST_DEBUG: '1', // runserver then serves the static files itself
  };
  const run = (...args) => execFileSync(python, args, { cwd: ROOT, env, stdio: ['ignore', 'ignore', 'inherit'] });
  console.log('Preparing a throwaway instance in', tmp);
  run('-m', 'unlist.bootstrap');
  run('manage.py', 'migrate', '--noinput');
  run('manage.py', 'load_bundled_lists');
  run('manage.py', 'load_breaches');

  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const server = spawn(python, ['manage.py', 'runserver', '--noreload', `127.0.0.1:${port}`], {
    cwd: ROOT,
    env,
    stdio: ['ignore', 'ignore', 'pipe'],
  });
  let serverLog = '';
  server.stderr.on('data', (chunk) => (serverLog += chunk));
  const browser = await chromium.launch();
  try {
    await waitFor(`${base}/login/`);
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    const errors = [];
    page.on('console', (msg) => msg.type() === 'error' && errors.push(msg.text()));
    page.on('pageerror', (error) => errors.push(String(error)));

    console.log('First run');
    await page.goto(base + '/');
    check(page.url().endsWith('/setup/'), 'a fresh instance leads to setup');
    await page.fill('#id_username', 'operator');
    await page.fill('#id_password1', PASSWORD);
    await page.fill('#id_password2', PASSWORD);
    await page.click('button[type=submit]');
    check(page.url().endsWith('/subjects/add/'), 'after setup: "Add your first Subject"');
    check(await page.isVisible('text=Add your first Subject'), 'the first-Subject page says so');

    await page.fill('#id_name', 'Robin Example');
    await page.selectOption('#id_country', 'DE');
    await page.fill('#id_email', 'robin@example.org');
    await page.click('main button[type=submit]');
    check(/\/subjects\/\d+\/consent\/$/.test(page.url()), 'after adding the Subject: record consent');
    const subjectUrl = page.url().replace(/consent\/$/, '');

    await page.check('#id_confirm');
    await page.click('main button[type=submit]');
    check(/\/mail\/subjects\/\d+\/import\/$/.test(page.url()), 'after consent: import mail');

    await page.setInputFiles('#id_file', FIXTURE);
    await page.click('main button[type=submit]');
    check(/\/discoveries\/$/.test(page.url()), 'after the import: the discovery list');
    const pursueButtons = page.locator('main form[action$="/pursue/"] button');
    for (let i = 0; i < 25 && (await pursueButtons.count()) < 3; i++) {
      await new Promise((r) => setTimeout(r, 200)); // the import may run in the background
      await page.reload();
    }
    check((await pursueButtons.count()) >= 3, 'the import found Organizations to pursue');

    console.log('Pursue and approve a batch');
    for (let i = 0; i < 3; i++) {
      await page.locator('main form[action$="/pursue/"] button').first().click();
      await page.waitForLoadState();
    }
    check((await page.locator('.messages .success').count()) >= 1, 'pursuing opens a Case');

    await page.goto(base + '/?view=table');
    const rows = page.locator('section[aria-labelledby=h-drafts] tbody tr');
    check((await rows.count()) === 3, 'Needs you lists the three drafts');
    const recipients = [];
    for (let i = 0; i < 2; i++) {
      recipients.push((await rows.nth(i).locator('td.recipient').innerText()).trim());
      await rows.nth(i).locator('input[type=checkbox]').check();
    }
    await page.click('section[aria-labelledby=h-drafts] button[form=batch]');
    const summary = await page.locator('main').innerText();
    check(page.url().endsWith('/approve/'), 'the batch goes through one summary screen');
    for (const recipient of recipients) check(summary.includes(recipient), `the summary lists ${recipient}`);
    await page.click('button[name=confirm]');
    const approved = await page.locator('.messages .success').allInnerTexts();
    check(approved.length === 2, 'confirming approves both drafts');
    check((await page.locator('section[aria-labelledby=h-drafts] tbody tr').count()) === 1, 'one draft is left to approve');

    // One handed-over request is marked sent, so the board has a "Waiting" card too.
    await page.goto(subjectUrl + '?view=table');
    await page.locator('main table tr:has-text("Handed over") a[href*="/cases/"]').first().click();
    const caseUrl = page.url();
    await page.click('button:has-text("Mark sent")');
    check(await page.isVisible('main h2:has-text("Waiting")'), 'marking a handed-over request sent starts the wait');

    console.log('Table / Board');
    await page.goto(base + '/?view=board');
    check(await page.isVisible('.board'), '?view=board shows the board');
    await page.goto(base + '/');
    check(await page.isVisible('.board'), 'the board is remembered without the parameter');
    await page.goto(subjectUrl);
    check(await page.isVisible('.board'), 'the same choice holds on the Subject page');

    if (SCREENSHOTS) {
      mkdirSync(SHOTS_DIR, { recursive: true });
      const shot = async (url, name) => {
        await page.goto(url);
        await page.screenshot({ path: path.join(SHOTS_DIR, name), fullPage: true });
        console.log('  wrote', path.relative(ROOT, path.join(SHOTS_DIR, name)));
      };
      await shot(subjectUrl + '?view=table', 'subject-page.png');
      await shot(base + '/?view=table', 'needs-you-table.png');
      await shot(base + '/?view=board', 'needs-you-board.png');
      await shot(caseUrl, 'case-page.png');
      await shot(base + '/statistics/', 'statistics.png');
      await page.goto(base + '/?view=table');
    }

    console.log(`Phone width (${PHONE} px)`);
    const phone = await browser.newContext({
      viewport: { width: PHONE, height: 844 },
      deviceScaleFactor: 1,
      storageState: await context.storageState(),
    });
    const small = await phone.newPage();
    small.on('pageerror', (error) => errors.push(String(error)));
    const organization = await (async () => {
      await page.goto(caseUrl);
      return page.locator('main a[href^="/organizations/o/"]').first().getAttribute('href');
    })();
    const pages = [
      '/', '/?view=board', subjectUrl, subjectUrl + '?view=board&tab=all', caseUrl, '/cases/', '/cases/replies/',
      subjectUrl.replace('/subjects/', '/mail/subjects/') + 'discoveries/',
      subjectUrl.replace('/subjects/', '/mail/subjects/') + 'import/',
      subjectUrl.replace('/subjects/', '/mail/subjects/') + 'connections/',
      '/organizations/', organization, '/organizations/lists/', '/breaches/', '/statistics/', '/settings/',
      '/llm/', '/backup/', '/subjects/add/', '/about/',
    ];
    for (const url of pages) {
      const shown = url.replace(base, '');
      await small.goto(base + shown);
      const width = await small.evaluate(() => document.documentElement.scrollWidth);
      check(width <= PHONE, `${shown} fits ${PHONE} px (scrollWidth ${width})`);
      if (width > PHONE) {
        // Name the elements that stick out, to make the failure easy to fix.
        const culprits = await small.evaluate((limit) => {
          const found = [];
          for (const element of document.querySelectorAll('body *')) {
            const box = element.getBoundingClientRect();
            if (box.right > limit + 1 && !element.parentElement.closest('.table-wrap, .board')) {
              found.push(`${element.tagName.toLowerCase()}.${element.className} (${Math.round(box.right)} px)`);
            }
          }
          return found.slice(0, 5);
        }, PHONE);
        console.log('       sticking out:', culprits.join(', '));
      }
    }
    await small.goto(base + '/');
    check(await small.isVisible('.topbar summary'), 'at phone width the sidebar is a menu in the top bar');
    check(!(await small.isVisible('.sidebar')), 'and the sidebar itself is hidden');
    if (SCREENSHOTS) {
      await small.goto(subjectUrl + '?view=table');
      await small.screenshot({ path: path.join(SHOTS_DIR, 'subject-page-phone.png'), fullPage: true });
      await small.goto(base + '/');
    }
    await small.click('.topbar summary');
    check(await small.isVisible('.topbar .nav >> text=Statistics'), 'the menu opens without JavaScript of our own');
    const unique = [...new Set(errors)];
    check(unique.length === 0, `no browser errors${unique.length ? ': ' + unique.join('; ') : ''}`);
  } finally {
    await browser.close();
    server.kill();
    rmSync(tmp, { recursive: true, force: true });
  }
  if (failures.length) {
    console.log(`\n${failures.length} check(s) failed.`);
    if (/Traceback/.test(serverLog)) console.log(serverLog.slice(-4000));
    process.exit(1);
  }
  console.log('\nAll browser checks passed.');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
