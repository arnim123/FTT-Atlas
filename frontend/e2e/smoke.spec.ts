import { expect, test, type Page } from '@playwright/test';

const API = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8000';

test.use({ viewport: { width: 1440, height: 900 } });

async function signIn(page: Page, email = 'alex.morgan@company.com') {
  await page.goto('/login');
  await page.locator('#test-email').fill(email);
  await page.getByRole('button', { name: 'Continue with test account' }).click();
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
}

async function setExternalAccess(page: Page, enabled: boolean) {
  await page.evaluate(async (next) => {
    const response = await fetch('/api/v1/admin/org-settings', {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch' },
      body: JSON.stringify({ external_ai_enabled: next }),
    });
    if (!response.ok) throw new Error(`Could not update organization controls (${response.status})`);
  }, enabled);
}

test('workspace smoke: library, search, archive, roles, and tokens', async ({ page, request }) => {
  const folderName = `Playwright ${Date.now()}`;
  let secret = '';
  await signIn(page);
  const linkedId = await page.evaluate(async () => {
    for (let pageNumber = 1; pageNumber <= 20; pageNumber += 1) {
      const response = await fetch(`/api/v1/documents?status=all&page=${pageNumber}&page_size=100`, { credentials: 'include', headers: { 'X-Requested-With': 'fetch' } });
      const body = await response.json();
      const found = (body.items ?? []).find((item: { google_web_url?: string | null; id: string; status?: string }) => item.google_web_url?.includes('atlasDemoSharedDoc01') && item.status !== 'archived');
      if (found) return found.id as string;
      if (!body.items?.length || body.items.length < 100) break;
    }
    return '';
  });

  await page.goto('/documents');
  await expect(page.getByRole('tree', { name: 'Company folder tree' })).toBeVisible();
  await page.getByRole('tree', { name: 'Company folder tree' }).getByRole('button', { name: /Open folder / }).first().click();
  await page.getByRole('button', { name: 'New folder' }).click();
  await page.locator('#folder-name').fill(folderName);
  await page.getByRole('button', { name: 'Create folder' }).click();
  await expect(page.getByText('Folder created')).toBeVisible();
  await expect(page.getByRole('button', { name: `Open folder ${folderName}` })).toBeVisible();

  if (linkedId) {
    await page.goto(`/documents/${linkedId}`);
  } else {
    await page.getByRole('button', { name: 'Add document' }).first().click();
    await page.getByRole('tab', { name: 'Link existing' }).click();
    await page.locator('#google-url').fill('https://docs.google.com/document/d/atlasDemoSharedDoc01/edit');
    await expect(page.getByText('Link looks good')).toBeVisible();
    await page.locator('#document-name').fill('Shared inventory notes');
    await expect(page.locator('#document-category')).not.toHaveValue('');
    await page.getByRole('button', { name: 'Link document' }).click();
  }
  await expect(page.getByRole('heading', { name: 'Shared inventory notes' })).toBeVisible();
  await expect(page.getByText('Recent access')).toBeVisible();
  await expect(page.getByText('Web', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: /Open in Google Docs/ }).first()).toBeVisible();

  await page.getByRole('button', { name: 'Permissions' }).click();
  await page.locator('#default-access').selectOption('edit');
  await page.getByRole('button', { name: 'Save permissions' }).click();
  await expect(page.getByText('Permissions updated')).toBeVisible();

  await page.getByRole('button', { name: 'Document actions' }).click();
  await page.getByRole('menuitem', { name: 'Archive document' }).click();
  await page.getByRole('button', { name: 'Archive', exact: true }).click();
  await page.goto('/archive');
  await expect(page.getByText('Shared inventory notes')).toBeVisible();
  await page.getByRole('button', { name: 'Restore' }).first().click();
  await page.getByRole('button', { name: 'Restore', exact: true }).last().click();
  await expect(page.getByText('Shared inventory notes')).toHaveCount(0);

  await page.goto('/search');
  await page.getByRole('searchbox', { name: 'Search all knowledge' }).fill('Inventory');
  await expect(page.getByRole('link', { name: 'Inventory SOP', exact: true })).toBeVisible();

  await page.goto('/dashboard');
  await page.locator('#view-role').selectOption('employee');
  await expect(page.getByRole('heading', { name: 'Welcome back, Emma.' })).toBeVisible();
  await page.locator('#view-role').selectOption('guest');
  await expect(page.getByRole('heading', { name: 'Welcome back, Noah.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add document' })).toHaveCount(0);
  await page.locator('#view-role').selectOption('super_admin');
  await expect(page.getByRole('heading', { name: 'Welcome back, Alex.' })).toBeVisible();

  await page.goto('/integrations');
  await page.getByRole('button', { name: 'ChatGPT' }).click();
  await expect(page.getByLabel('MCP server URL')).toHaveValue(/\/mcp$/);
  await page.keyboard.press('Escape');
  await page.getByRole('tab', { name: 'My access tokens' }).click();
  await page.getByRole('button', { name: 'Create token' }).first().click();
  await page.locator('#token-name').fill('Playwright agent');
  await page.getByRole('button', { name: 'Create token' }).last().click();
  const secretField = page.getByRole('textbox', { name: 'Access token', exact: true });
  await expect(secretField).toBeVisible();
  secret = await secretField.inputValue();
  expect(secret.startsWith('dms_pat_')).toBeTruthy();
  await page.getByRole('button', { name: 'Done' }).click();
  await expect(page.getByText(secret)).toHaveCount(0);
  await expect(page.getByRole('cell', { name: 'Playwright agent' }).first()).toBeVisible();

  try {
    const allowed = await request.get(`${API}/api/v1/agent/search?q=Inventory`, { headers: { Authorization: `Bearer ${secret}` } });
    expect(allowed.ok()).toBeTruthy();
    await page.getByRole('tab', { name: 'Organization controls' }).click();
    await page.getByRole('switch', { name: 'Allow external AI access' }).click();
    await page.getByRole('button', { name: 'Turn off access' }).click();
    await expect(page.getByText('Organization controls updated')).toBeVisible();
    const blocked = await request.get(`${API}/api/v1/agent/search?q=Inventory`, { headers: { Authorization: `Bearer ${secret}` } });
    expect(blocked.status()).toBe(403);
    const body = await blocked.json();
    expect(body.detail.code).toBe('EXTERNAL_ACCESS_DISABLED');
  } finally {
    await setExternalAccess(page, true);
  }

  await page.getByRole('tab', { name: 'My access tokens' }).click();
  await page.getByRole('row', { name: /Playwright agent/ }).first().getByRole('button', { name: 'Revoke' }).click();
  await page.getByRole('button', { name: 'Revoke token' }).click();
  await expect(page.getByText('Token revoked')).toBeVisible();
  const revoked = await request.get(`${API}/api/v1/agent/search?q=Inventory`, { headers: { Authorization: `Bearer ${secret}` } });
  expect(revoked.status()).toBe(401);
});
