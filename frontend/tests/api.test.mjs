import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { bundleTestModule } from './helpers.mjs';

const api = await bundleTestModule("export * from './src/api'; export { db } from './src/mocks/db';");
const baseline = structuredClone(api.db);
beforeEach(() => Object.assign(api.db, structuredClone(baseline)));
const admin = () => api.getInitialUser();
const access = () => ({ level: 'organization', defaultPermission: 'view', grants: [], syncStatus: 'synced' });
const input = (changes = {}) => ({ name: 'Team test resource', description: 'A practical guide.', tags: ['Process'], categoryId: 'guide', departmentId: 'product', folderId: 'root', type: 'google-doc', access: access(), ...changes });

test('seed includes all types, roles, access levels, departments, and the requested search results', async () => {
  assert.equal(api.db.documents.length, 52);
  assert.equal(api.db.users.length, 13);
  assert.equal(new Set(api.db.users.map(user => user.role)).size, 5);
  assert.equal(new Set(api.db.documents.map(doc => doc.type)).size, 9);
  assert.equal(new Set(api.db.documents.map(doc => doc.access.level)).size, 4);
  const reference = await api.getReferenceData(admin());
  assert.equal(reference.departments.length, 5);
  const results = await api.searchDocuments('Inventory', { sort: 'relevance' }, admin());
  for (const name of ['ERP Lens Inventory Manual', 'Inventory SOP', 'Warehouse Process Guide']) {
    assert.ok(results.some(result => result.document.name === name), name);
  }
  assert.ok(results.every(result => result.matchedIn.length && result.snippet));
});

test('Employee and Guest queries cannot read private or out-of-scope documents', async () => {
  const employee = await api.getRoleIdentity('employee');
  const guest = await api.getRoleIdentity('guest');
  const all = await api.listDocuments(admin());
  const employeeDocs = await api.listDocuments(employee);
  const guestDocs = await api.listDocuments(guest);
  assert.ok(employeeDocs.length < all.length);
  assert.ok(employeeDocs.some(doc => doc.id === 'doc-45'));
  assert.ok(!employeeDocs.some(doc => doc.id === 'doc-40'));
  assert.equal(guestDocs.length, 4);
  assert.ok(guestDocs.every(doc => doc.access.level === 'custom'));
  await assert.rejects(api.getDocument('doc-40', employee), /access/);
  await assert.rejects(api.getDocument('doc-1', guest), /access/);
  await assert.rejects(api.createDocument(input(), guest), /permission/);
  await assert.rejects(api.listUsers(employee), /permission/);
});

test('dashboard and recursive folder counts match each role’s visible documents', async () => {
  for (const role of ['super_admin', 'manager', 'employee', 'guest']) {
    const actor = await api.getRoleIdentity(role);
    const docs = await api.listDocuments(actor);
    const dashboard = await api.getDashboard(actor);
    const folders = await api.listFolderTree(actor);
    assert.equal(dashboard.totalDocuments, docs.length);
    assert.equal(folders.find(folder => folder.id === 'root').documentCount, docs.length);
    assert.equal(dashboard.byDepartment.reduce((sum, department) => sum + department.count, 0), docs.length);
  }
  const docs = await api.listDocuments(admin(), { folderId: 'erp' });
  assert.ok(docs.length > 5);
  assert.ok(docs.every(doc => doc.folderId.startsWith('erp')));
});

test('folder creation, renaming, moves, and cycle prevention work at arbitrary depth', async () => {
  const parent = await api.createFolder({ name: 'Parent', parentId: 'root', departmentId: 'product' }, admin());
  const child = await api.createFolder({ name: 'Child', parentId: parent.id, departmentId: 'product' }, admin());
  const grandchild = await api.createFolder({ name: 'Grandchild', parentId: child.id, departmentId: 'product' }, admin());
  await assert.rejects(api.updateFolder(parent.id, { parentId: grandchild.id }, admin()), /subfolders/);
  await assert.rejects(api.createFolder({ name: 'Parent', parentId: 'root', departmentId: 'product' }, admin()), /already exists/);
  const renamed = await api.updateFolder(child.id, { name: 'Renamed', parentId: 'products' }, admin());
  assert.equal(renamed.name, 'Renamed');
  assert.equal(renamed.parentId, 'products');
  await assert.rejects(api.deleteFolder('root', admin()), /cannot be deleted/);
});

test('document create, move, archive, restore, and permanent delete update the same data layer', async () => {
  const actor = await api.getRoleIdentity('employee');
  const doc = await api.createDocument(input({ tags: ['A new tag'] }), actor);
  assert.equal(doc.ownerId, actor.id);
  assert.ok((await api.getReferenceData(actor)).tags.some(tag => tag.name === 'A new tag'));
  await api.bulkDocuments([doc.id], 'move', actor, 'erp-manual');
  assert.equal((await api.getDocument(doc.id, actor)).folderId, 'erp-manual');
  await api.bulkDocuments([doc.id], 'archive', actor);
  assert.ok(!(await api.listDocuments(actor)).some(item => item.id === doc.id));
  assert.ok((await api.listArchived(actor)).some(item => item.id === doc.id));
  await api.bulkDocuments([doc.id], 'restore', actor);
  assert.ok((await api.listDocuments(actor)).some(item => item.id === doc.id));
  await assert.rejects(api.bulkDocuments([doc.id], 'delete', actor), /permission/);
  await api.bulkDocuments([doc.id], 'delete', admin());
  await assert.rejects(api.getDocument(doc.id, admin()), /could not be found/);
});

test('bulk changes validate every item before mutating, and inactive accounts cannot act', async () => {
  const actor = await api.getRoleIdentity('employee');
  await assert.rejects(api.bulkDocuments(['doc-11', 'doc-1'], 'archive', actor), /permission/);
  assert.equal((await api.getDocument('doc-11', actor)).archived, false);
  const inactive = api.db.users.find(user => user.status === 'deactivated');
  await assert.rejects(api.listDocuments(inactive), /inactive/);
});

test('custom permissions allow per-person editing, revocation, and sync retry', async () => {
  const actor = admin();
  const guest = await api.getRoleIdentity('guest');
  const target = { kind: 'document', id: 'doc-1', name: 'ERP Lens Inventory Manual' };
  const custom = { ...access(), level: 'custom', grants: [{ principalType: 'user', principalId: guest.id, permission: 'view' }] };
  const pending = await api.updatePermissions(target, custom, actor);
  assert.equal(pending.syncStatus, 'pending');
  assert.ok(await api.getDocument(target.id, guest));
  await assert.rejects(api.updateDocument(target.id, { content: 'Not allowed' }, guest), /permission/);
  custom.grants[0].permission = 'edit';
  await api.updatePermissions(target, custom, actor);
  await api.updateDocument(target.id, { content: 'Guest edit' }, guest);
  assert.equal((await api.getDocument(target.id, actor)).content, 'Guest edit');
  assert.equal((await api.retryPermissionSync(target, actor)).syncStatus, 'synced');
  await api.updatePermissions(target, { ...access(), level: 'private' }, actor);
  await assert.rejects(api.getDocument(target.id, guest), /access/);
  await assert.rejects(api.updatePermissions(target, { ...custom, grants: [] }, actor), /at least one/);
});

test('uploaded text versions restore both file metadata and actual preview content', async () => {
  const first = new File(['First version content'], 'notes.txt', { type: 'text/plain' });
  const doc = await api.createDocument(input({ file: first, type: 'txt' }), admin());
  assert.equal(doc.content, 'First version content');
  const updated = await api.uploadVersion(doc.id, new File(['Second version content'], 'notes-v2.txt'), admin());
  assert.equal(updated.version, 2);
  assert.equal(updated.content, 'Second version content');
  await assert.rejects(api.uploadVersion(doc.id, new File(['Wrong type'], 'wrong.pdf'), admin()), /same file type/);
  const restored = await api.restoreVersion(doc.id, 1, admin());
  assert.equal(restored.version, 3);
  assert.equal(restored.versions.length, 3);
  assert.equal(restored.fileName, 'notes.txt');
  assert.equal(restored.content, 'First version content');
  assert.throws(() => api.validateUpload(new File([], 'empty.txt')), /empty/);
  assert.throws(() => api.validateUpload(new File(['x'], 'program.exe')), /supported file type/);
  assert.throws(() => api.validateUpload(new File([new Uint8Array(25 * 1024 * 1024 + 1)], 'huge.pdf')), /25 MB/);
});

test('Google URLs validate hosts and sharing, and demo links stay in the current SPA', async () => {
  assert.ok(api.validateGoogleUrl('https://docs.google.com/document/d/abc123/edit'));
  assert.ok(api.validateGoogleUrl('https://docs.google.com/spreadsheets/d/abc123/edit'));
  assert.equal(api.validateGoogleUrl('https://docs.google.com.evil.example/document/d/abc123'), false);
  assert.equal(api.validateGoogleUrl('javascript:alert(1)'), false);
  assert.equal((await api.checkGoogleSharing('https://docs.google.com/document/d/UNSHARED-demo/edit')).shared, false);
  await assert.rejects(api.createDocument(input({ googleUrl: 'https://docs.google.com/document/d/UNSHARED-demo/edit' }), admin()), /service account/);
  const doc = await api.createDocument(input(), admin());
  assert.equal(api.getGoogleDocumentUrl(doc), `/google-preview/${doc.id}`);
});

test('user administration enforces manager scope, administrator hierarchy, and invite validation', async () => {
  const manager = await api.getRoleIdentity('manager');
  const users = await api.listUsers(manager);
  assert.ok(users.every(user => user.departmentId === manager.departmentId));
  const invited = await api.inviteUser({ email: 'new.teammate@company.com', role: 'employee', departmentId: 'product' }, manager);
  assert.equal(invited.status, 'invited');
  await assert.rejects(api.inviteUser({ email: 'NEW.TEAMMATE@company.com', role: 'employee', departmentId: 'product' }, manager), /already exists/);
  await assert.rejects(api.inviteUser({ email: 'cross.department@company.com', role: 'employee', departmentId: 'hr' }, manager), /own department/);
  await assert.rejects(api.inviteUser({ email: 'outsider@example.com', role: 'employee', departmentId: 'product' }, admin()), /company.com/);
  await assert.rejects(api.updateUser('u1', { role: 'employee' }, await api.getRoleIdentity('admin')), /Super Admin/);
  await assert.rejects(api.updateUser('u1', { status: 'deactivated' }, admin()), /own role/);
  await api.updateUser('u4', { status: 'deactivated' }, admin());
  assert.equal(api.db.users.find(user => user.id === 'u4').status, 'deactivated');
  await api.updateUser('u4', { status: 'active' }, admin());
});

test('taxonomy CRUD prevents dangling references and keeps renamed tags consistent', async () => {
  await assert.rejects(api.deleteTaxonomy('departments', 'product', admin()), /Reassign/);
  await assert.rejects(api.deleteTaxonomy('categories', 'guide', admin()), /Reassign/);
  const category = await api.saveTaxonomy('categories', { name: 'Temporary category', description: 'Test' }, admin());
  await api.saveTaxonomy('categories', { ...category, name: 'Renamed category' }, admin());
  assert.ok((await api.listTaxonomy('categories', admin())).some(item => item.name === 'Renamed category'));
  await api.deleteTaxonomy('categories', category.id, admin());
  const tag = api.db.tags.find(item => item.name === 'Inventory');
  await api.saveTaxonomy('tags', { ...tag, name: 'Stock management' }, admin());
  assert.ok((await api.getDocument('doc-1', admin())).tags.includes('Stock management'));
  await api.deleteTaxonomy('tags', tag.id, admin());
  assert.ok(!(await api.getDocument('doc-1', admin())).tags.includes('Stock management'));
  assert.equal(api.db.documents.length, baseline.documents.length);
});

test('API responses are isolated, filters combine, and one simulated failure can recover', async () => {
  const doc = await api.getDocument('doc-1', admin());
  doc.name = 'Mutation outside the API';
  assert.notEqual((await api.getDocument('doc-1', admin())).name, doc.name);
  const docs = await api.listDocuments(admin(), { departmentId: 'product', type: 'google-doc', tag: 'ERP Lens', sort: 'name' });
  assert.ok(docs.length > 0);
  assert.ok(docs.every(item => item.departmentId === 'product' && item.type === 'google-doc' && item.tags.includes('ERP Lens')));
  assert.deepEqual(docs.map(item => item.name), [...docs.map(item => item.name)].sort((a, b) => a.localeCompare(b)));
  api.simulateNextError();
  await assert.rejects(api.getDashboard(admin()), /couldn’t connect/);
  assert.ok((await api.getDashboard(admin())).totalDocuments > 0);
});

test('login models unauthorized domains and deactivated accounts explicitly', async () => {
  await assert.rejects(api.signIn('domain'), /company domain/);
  await assert.rejects(api.signIn('deactivated'), /deactivated/);
  assert.equal((await api.signIn()).role, 'super_admin');
});

test('external AI tokens are revealed once and stay inside the caller’s access', async () => {
  assert.equal(api.db.tokens.length, 6);
  assert.equal(api.db.grants.length, 3);
  assert.equal(api.db.audit.length, 60);
  assert.equal(api.db.tokens.filter(token => token.status === 'expired').length, 1);
  assert.equal(api.db.tokens.filter(token => token.status === 'revoked').length, 1);
  const actor = admin();
  const created = await api.createToken({ name: 'Smoke token', scopes: ['docs:read'], expiresInDays: 30 }, actor);
  assert.match(created.secret, /^dms_pat_[a-f0-9]{32}$/);
  assert.equal(created.prefix, created.secret.slice(0, 12));
  const listed = await api.listTokens(actor);
  assert.equal(JSON.stringify(listed).includes(created.secret), false);
  const employee = await api.getRoleIdentity('employee');
  assert.ok((await api.listTokens(employee)).every(token => token.userId === employee.id));
  await assert.rejects(api.listTokens(employee, { everyone: true }), /permission/);
  await assert.rejects(api.listTokens(await api.getRoleIdentity('guest')), /Guest/);
  await api.revokeToken(created.id, actor);
  assert.equal((await api.listTokens(actor)).find(token => token.id === created.id).status, 'revoked');
  const ownAudit = await api.listAuditLog(employee);
  assert.ok(ownAudit.every(row => row.userId === employee.id));
  assert.ok((await api.listAuditLog(actor, { everyone: true })).length > ownAudit.length);
  await assert.rejects(api.updateOrgSettings({ allowExternalAi: false }, employee), /permission/);
  assert.equal((await api.updateOrgSettings({ allowExternalAi: false }, actor)).allowExternalAi, false);
  await assert.rejects(api.createToken({ name: 'Blocked', scopes: ['docs:read'], expiresInDays: 30 }, actor), /turned off/);
  await api.updateOrgSettings({ allowExternalAi: true, allowWriteScopes: false }, actor);
  await assert.rejects(api.createToken({ name: 'Writer', scopes: ['docs:read', 'docs:write'], expiresInDays: 30 }, actor), /write/);
  const consent = await api.getConsentRequest({ app: 'ChatGPT', redirectUri: 'https://chatgpt.com/connector/callback', verified: '1' }, actor);
  assert.equal(consent.verified, true);
  assert.equal(consent.redirectDomain, 'chatgpt.com');
  await assert.rejects(api.getConsentRequest({ app: '', redirectUri: '' }, actor), /could not be found/);
  assert.equal((await api.submitConsent({ decision: 'allow', appName: 'ChatGPT', redirectDomain: 'chatgpt.com', scopes: ['docs:read'] }, actor)).decision, 'allow');
});
