import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { bundleTestModule } from './helpers.mjs';

const memory = new Map();
Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: { getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key) } });
const ui = await bundleTestModule("export * from './tests/render-harness';", 'render');

test('every route renders its actual screen without runtime exceptions or console errors', async () => {
  const screens = [
    ['/dashboard', 'Welcome back, Alex.'],
    ['/documents', 'Your knowledge, organized.'],
    ['/documents?folder=erp', 'ERP Lens'],
    ['/documents/doc-1', 'ERP Lens Inventory Manual'],
    ['/documents/doc-2', 'PDF preview'],
    ['/documents/doc-6', 'Download file'],
    ['/documents/doc-21', 'Design System Overview'],
    ['/search', 'The answer is closer than you think.'],
    ['/search?q=Inventory', 'Warehouse Process Guide'],
    ['/archive', 'Out of the way. Still within reach.'],
    ['/users', 'The people behind the knowledge.'],
    ['/settings', 'A workspace that works for you.'],
    ['/profile', 'Your corner of the workspace.'],
    ['/integrations', 'AI apps can only see what YOU can see'],
    ['/oauth/consent?app=ChatGPT&redirect_uri=https://chatgpt.com/connector/callback&verified=1', 'wants to access Company Knowledge as Alex Morgan'],
    ['/login', 'Sign in with Google'],
    ['/google-preview/doc-1', 'Google Workspace preview'],
  ];
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args.join(' '));
  try {
    for (const [route, expected] of screens) {
      const html = await ui.renderScreen(route);
      assert.ok(html.includes(expected), `${route} should contain ${expected}`);
      assert.ok(!html.includes('Let’s get you back on track'), route);
    }
  } finally { console.error = original; }
  assert.deepEqual(errors, []);
});

test('role switching changes navigation, creation actions, and restricted screens', async () => {
  const admin = await ui.renderScreen('/documents');
  const manager = await ui.renderScreen('/documents', 'manager');
  const employee = await ui.renderScreen('/documents', 'employee');
  const guest = await ui.renderScreen('/documents', 'guest');
  assert.ok(admin.includes('href="/settings"'));
  assert.ok(manager.includes('href="/users"'));
  assert.ok(!manager.includes('href="/settings"'));
  assert.ok(!employee.includes('href="/users"'));
  assert.ok(employee.includes('href="/integrations"'));
  assert.ok(!guest.includes('href="/integrations"'));
  assert.ok(!guest.includes('Add document'));
  assert.ok(!guest.includes('Employee Handbook 2026'));
  assert.ok(guest.includes('Company Overview Deck'));
  assert.ok((await ui.renderScreen('/settings', 'employee')).includes('This space is restricted'));
  assert.ok((await ui.renderScreen('/users', 'guest')).includes('This space is restricted'));
  assert.ok((await ui.renderScreen('/integrations', 'guest')).includes('This space is restricted'));
  assert.ok((await ui.renderScreen('/dashboard')).includes('AI agent calls (30d)'));
  assert.ok(!(await ui.renderScreen('/dashboard', 'employee')).includes('AI agent calls (30d)'));
  assert.ok((await ui.renderScreen('/users')).includes('Bot'));
  assert.ok((await ui.renderScreen('/users')).includes('API tokens'));
  assert.ok((await ui.renderScreen('/documents/doc-1')).includes('Recent access'));
});

test('viewer exposes supported previews, edit controls, and locked Phase 2 insights', async () => {
  const doc = await ui.renderScreen('/documents/doc-1');
  assert.ok(doc.includes('id="document-editor"') === false);
  assert.ok(doc.includes('Google Doc'));
  assert.ok(doc.includes('Ask AI about this document'));
  for (const placeholder of ['Summary', 'Key Takeaways', 'Keywords', 'Topics']) assert.ok(doc.includes(placeholder));
  assert.ok(doc.includes('Having trouble?'));
  assert.ok(doc.includes('href="/google-preview/doc-1"'));
  const pdf = await ui.renderScreen('/documents/doc-2');
  assert.ok(pdf.includes('/samples/document.pdf#toolbar=0'));
  const image = await ui.renderScreen('/documents/doc-21');
  assert.ok(image.includes('alt="Design System Overview"'));
});

test('permissions render Guest warning and principal preview; highlights escape regex characters', async () => {
  const html = await ui.renderAccessPicker();
  assert.ok(html.includes('Guest outside your company'));
  assert.ok(html.includes('Who can access'));
  assert.ok(html.includes('Noah Williams'));
  assert.equal(ui.renderHighlight('A [draft] document', '[draft]'), 'A <mark>[draft]</mark> document');
  assert.equal(ui.renderHighlight('<script>alert(1)</script>', 'alert'), '&lt;script&gt;<mark>alert</mark>(1)&lt;/script&gt;');
});

test('seeded download assets are real local PDF, image, text, and Office files', async () => {
  const pdf = await readFile('public/samples/document.pdf');
  assert.equal(pdf.subarray(0, 8).toString(), '%PDF-1.4');
  for (const extension of ['docx', 'xlsx', 'pptx']) {
    const bytes = await readFile(`public/samples/document.${extension}`);
    assert.equal(bytes.subarray(0, 2).toString(), 'PK');
  }
  assert.ok((await readFile('public/samples/document.svg', 'utf8')).includes('<svg'));
  assert.ok((await readFile('public/samples/document.txt', 'utf8')).includes('Company Knowledge'));
});
