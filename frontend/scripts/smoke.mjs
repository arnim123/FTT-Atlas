import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, rm, access } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';
import assert from 'node:assert/strict';
import { BrowserSession, pause } from './cdp.mjs';

const port = Number(process.env.ATLAS_E2E_PORT ?? 4173);
const debugPort = Number(process.env.ATLAS_CHROME_PORT ?? 9173);
const base = `http://127.0.0.1:${port}`;
const chromePath = process.env.CHROME_PATH ?? (process.platform === 'darwin' ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : process.platform === 'win32' ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : '/usr/bin/google-chrome');
const output = resolve('test-results');
let server, chrome, browser, profile;
let serverLog = '', chromeLog = '';

async function reachable(url, child, label) {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`${label} exited before becoming ready. ${label === 'Vite' ? serverLog : chromeLog}`);
    try { const response = await fetch(url, { signal: AbortSignal.timeout(1000) }); if (response.ok) return response; } catch { /* Startup can take a moment. */ }
    await pause(100);
  }
  throw new Error(`${label} did not become ready. Check port permissions. ${label === 'Vite' ? serverLog : chromeLog}`);
}

async function check(name, action) { await action(); console.log(`✓ ${name}`); }
async function switchRole(role) { await browser.value('#view-role', role); await browser.wait(`document.querySelector('#view-role')?.value === ${JSON.stringify(role)}`); await browser.ready(); }
async function contains(text) { return browser.evaluate(`document.body.innerText.includes(${JSON.stringify(text)})`); }

try {
  await access(chromePath);
  await mkdir(output, { recursive: true });
  server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], { cwd: process.cwd(), stdio: ['ignore', 'pipe', 'pipe'] });
  server.stdout.on('data', data => serverLog += data.toString());
  server.stderr.on('data', data => serverLog += data.toString());
  await reachable(base, server, 'Vite');
  profile = await mkdtemp(join(tmpdir(), 'atlas-browser-'));
  chrome = spawn(chromePath, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-sync', `--user-data-dir=${profile}`, `--remote-debugging-port=${debugPort}`, ...(process.platform === 'linux' ? ['--no-sandbox'] : []), 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
  chrome.stderr.on('data', data => chromeLog += data.toString());
  const targets = await (await reachable(`http://127.0.0.1:${debugPort}/json/list`, chrome, 'Chrome')).json();
  browser = await BrowserSession.connect(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
  await browser.viewport(1440, 1000);
  await browser.send('Page.navigate', { url: `${base}/dashboard` });
  await browser.wait(`document.querySelector('h1')?.textContent.includes('Welcome back')`);
  await browser.ready();

  await check('all routes load and desktop dashboard renders', async () => {
    await browser.screenshot(join(output, 'dashboard-desktop.png'));
    for (const path of ['/documents', '/documents/doc-1', '/documents/doc-2', '/documents/doc-6', '/documents/doc-21', '/search?q=Inventory', '/archive', '/integrations', '/users', '/settings', '/profile', '/oauth/consent?app=ChatGPT&redirect_uri=https://chatgpt.com/connector/callback&verified=1']) {
      await browser.route(path);
      await browser.wait(`Boolean(document.querySelector('h1'))`, `heading at ${path}`);
      assert.ok(!await contains('We couldn’t load this content'), path);
    }
  });

  await check('workspace search and keyboard command palette', async () => {
    await browser.route('/search?q=Inventory');
    await browser.wait(`document.body.innerText.includes('Warehouse Process Guide')`);
    assert.ok(await contains('ERP Lens Inventory Manual'));
    assert.ok(await contains('Inventory SOP'));
    await browser.key('k', 'KeyK', 2);
    await browser.value('[aria-label="Search command"]', 'Inventory');
    await browser.wait(`document.querySelector('[cmdk-list]')?.textContent.includes('Inventory SOP')`);
    await browser.key('Escape', 'Escape');
  });

  await check('Google document creation, editing, and local fallback navigation', async () => {
    await browser.clickText('New');
    await browser.clickText('New Google Doc', '[role="menuitem"]');
    await browser.value('#google-title', 'Browser smoke resource');
    await browser.value('#document-description', 'A document created by the browser smoke check.');
    await browser.clickText('Create document');
    await browser.wait(`document.querySelector('#main-content h1')?.textContent === 'Browser smoke resource'`);
    await browser.clickText('Edit');
    await browser.value('#document-editor', 'Browser smoke resource\n\nOverview\nSaved by the smoke check.');
    await browser.clickText('Save changes');
    await browser.wait(`document.body.innerText.includes('Document saved')`);
    await browser.clickText('View');
    await browser.wait(`document.querySelector('.paper')?.textContent.includes('Saved by the smoke check.')`);
    await browser.clickText('Open in Google Docs', 'a');
    await browser.wait(`location.pathname.startsWith('/google-preview/')`);
    assert.ok(await contains('Saved by the smoke check.'));
    await browser.clickText('Back to Atlas', 'a');
    await browser.ready();
  });

  await check('custom permissions and Guest restrictions', async () => {
    await browser.clickText('Permissions');
    await browser.click('[role="dialog"] label:has(input[value="custom"])');
    await browser.value('#add-principal', 'user:u5');
    await browser.click('[aria-label="Add principal"]');
    assert.ok(await contains('Guest outside your company'));
    await browser.clickText('Save permissions');
    await browser.wait(`!document.querySelector('[role="dialog"]')`);
    await switchRole('guest');
    assert.ok(await contains('Browser smoke resource'));
    assert.equal(await browser.evaluate(`[...document.querySelectorAll('button')].some(element => element.textContent.trim() === 'Edit')`), false);
    assert.equal(await browser.evaluate(`Boolean(document.querySelector('nav[aria-label="Main navigation"] a[href="/users"]'))`), false);
    await switchRole('super_admin');
  });

  await check('file upload and new text version', async () => {
    await browser.clickText('New');
    await browser.clickText('Upload file', '[role="menuitem"]');
    await browser.wait(`Boolean(document.querySelector('[aria-label="Choose files to upload"]'))`);
    await browser.evaluate(`(() => { const input = document.querySelector('[aria-label="Choose files to upload"]'); const data = new DataTransfer(); data.items.add(new File(['Original smoke text'], 'smoke-notes.txt', { type: 'text/plain' })); input.files = data.files; input.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await browser.clickText('Upload document');
    await browser.wait(`document.querySelector('#main-content h1')?.textContent === 'smoke-notes'`);
    assert.ok(await contains('Original smoke text'));
    await browser.evaluate(`(() => { const input = document.querySelector('[aria-label="Upload new version"]'); const data = new DataTransfer(); data.items.add(new File(['Updated smoke text'], 'smoke-notes-v2.txt', { type: 'text/plain' })); input.files = data.files; input.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await browser.wait(`document.querySelector('pre')?.textContent === 'Updated smoke text'`);
  });

  await check('archive and restore workflow', async () => {
    await browser.click('[aria-label="Document actions"]');
    await browser.clickText('Archive document', '[role="menuitem"]');
    await browser.clickText('Archive', '[role="dialog"] button');
    await browser.wait(`location.pathname === '/documents'`);
    await browser.route('/archive');
    await browser.wait(`document.body.innerText.includes('smoke-notes')`);
    await browser.clickExpression(`[...document.querySelectorAll('tr')].find(row => row.textContent.includes('smoke-notes')).querySelector('button')`);
    await browser.clickText('Restore', '[role="dialog"] button');
    await browser.wait(`!document.querySelector('tbody')?.textContent.includes('smoke-notes')`);
  });

  await check('inline settings CRUD and a mock invitation', async () => {
    await browser.route('/settings');
    await browser.clickText('Categories', '[role="tab"]');
    await browser.ready();
    await browser.clickText('Add category');
    await browser.value('[aria-label="category name"]', 'Smoke category');
    await browser.value('[aria-label="category description"]', 'Created by the smoke check.');
    await browser.click('[aria-label="Save category"]');
    await browser.wait(`Boolean(document.querySelector('[aria-label="Edit Smoke category"]'))`);
    await browser.click('[aria-label="Edit Smoke category"]');
    await browser.value('[aria-label="category name"]', 'Updated smoke category');
    await browser.click('[aria-label="Save category"]');
    await browser.wait(`Boolean(document.querySelector('[aria-label="Delete Updated smoke category"]'))`);
    await browser.click('[aria-label="Delete Updated smoke category"]');
    await browser.clickText('Delete category', '[role="dialog"] button');
    await browser.wait(`!document.querySelector('[role="dialog"]')`);
    await browser.route('/users');
    await browser.clickText('Invite user');
    await browser.value('#invite-email', 'smoke.teammate@company.com');
    await browser.clickText('Invite user', '[role="dialog"] button');
    await browser.wait(`document.querySelector('tbody')?.textContent.includes('smoke.teammate@company.com')`);
  });

  await check('recoverable error state and dark mode', async () => {
    await browser.route('/dashboard');
    await browser.click('[aria-label="Demo tools"]');
    await browser.clickText('Simulate an API error', '[role="menuitem"]');
    await browser.wait(`document.querySelector('[role="alert"]')?.textContent.includes('We couldn’t load')`);
    await browser.clickText('Try again');
    await browser.wait(`document.querySelector('h1')?.textContent.includes('Welcome back')`);
    await browser.click('[aria-label="Switch to dark mode"]');
    await browser.wait(`document.documentElement.classList.contains('dark')`);
    await browser.screenshot(join(output, 'dashboard-dark.png'));
    await browser.click('[aria-label="Switch to light mode"]');
  });

  await check('mobile drawer and page widths', async () => {
    await browser.viewport(390, 844);
    await browser.click('[aria-label="Open navigation"]');
    await browser.click('[role="dialog"] a[href="/documents"]');
    await browser.ready();
    assert.ok(await browser.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'));
    await browser.screenshot(join(output, 'documents-mobile.png'));
    await browser.route('/dashboard');
    await browser.screenshot(join(output, 'dashboard-mobile.png'));
    assert.ok(await browser.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'));
  });

  await check('sign out and both login error states', async () => {
    await browser.route('/profile');
    await browser.clickText('Sign out');
    await browser.wait(`location.pathname === '/login'`);
    for (const [scenario, message] of [['domain', 'Company account required'], ['deactivated', 'This account is deactivated']]) {
      await browser.value('[aria-label="Demo sign-in scenario"]', scenario);
      await browser.clickText('Sign in with Google');
      await browser.wait(`document.querySelector('[role="alert"]')?.textContent.includes(${JSON.stringify(message)})`);
    }
    await browser.value('[aria-label="Demo sign-in scenario"]', 'success');
    await browser.clickText('Sign in with Google');
    await browser.wait(`location.pathname === '/dashboard'`);
  });

  assert.deepEqual(browser.errors, [], 'The browser should have zero console errors and runtime exceptions');
  console.log(`\nBrowser checks passed. Screenshots: ${output}`);
} catch (error) {
  if (browser) await browser.screenshot(join(output, 'failure.png')).catch(() => undefined);
  console.error(`Browser smoke check failed: ${error.message}`);
  process.exitCode = 1;
} finally {
  browser?.close();
  chrome?.kill('SIGTERM');
  server?.kill('SIGTERM');
  if (profile) { await pause(400); await rm(profile, { recursive: true, force: true }).catch(() => undefined); }
}
