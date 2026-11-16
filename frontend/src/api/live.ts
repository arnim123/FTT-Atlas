import type { Access, ArchiveItem, AuditFilters, ConsentDecision, CreateDocumentInput, CreateTokenInput, Document, DocumentFilters, DocumentType, ReferenceData, ResourceTarget, Role, TaxonomyKind, User } from '@/types';
import { isAdmin } from '@/lib/access';
import { ApiError, apiGet, apiSend, apiUpload, type Schemas } from './http';
import { toApiFolderId, toUiFolderId } from './ids';
import { accessChannel, accessFrom, apiSource, auditQueryChannel, flattenFolders, mapAudit, mapDashboard, mapDocument, mapGrant, mapGrants, mapOrg, mapRelated, mapSearchHit, mapTaxonomy, mapToken, mapUser, mapVersion } from './map';

const ROLE_EMAIL: Record<Role, string> = {
  super_admin: 'alex.morgan@company.com',
  admin: 'sarah.chen@company.com',
  manager: 'james.wilson@company.com',
  employee: 'emma.davis@company.com',
  guest: 'noah@partner.co',
};

export function restoreSession() {
  return apiGet<Schemas['UserRead']>('/api/v1/auth/me', { redirectOn401: false }).then(mapUser);
}

export function signInWithGoogle(idToken: string) {
  return apiSend<Schemas['UserRead']>('/api/v1/auth/google', { method: 'POST', json: { id_token: idToken }, redirectOn401: false }).then(mapUser);
}

export function loginWithTestEmail(email: string) {
  return apiSend<Schemas['UserRead']>('/api/v1/auth/test-login', { method: 'POST', json: { email }, redirectOn401: false }).then(mapUser);
}

export function endSession() {
  return apiSend<void>('/api/v1/auth/logout', { method: 'POST' });
}

export function getRoleIdentity(role: Role) {
  const email = ROLE_EMAIL[role];
  if (!email) return Promise.reject(new ApiError(404, 'NOT_FOUND', 'No active account is available for this role.'));
  return loginWithTestEmail(email);
}

export function getProfile() {
  return restoreSession();
}

export async function getReferenceData(): Promise<ReferenceData> {
  const [departments, categories, tags, users] = await Promise.all([
    apiGet<Schemas['DepartmentRead'][]>('/api/v1/departments'),
    apiGet<Schemas['TaxonomyRead'][]>('/api/v1/categories'),
    apiGet<Schemas['TaxonomyRead'][]>('/api/v1/tags'),
    apiGet<Schemas['UserRead'][]>('/api/v1/users/directory'),
  ]);
  return { departments: departments.map(mapTaxonomy), categories: categories.map(mapTaxonomy), tags: tags.map(mapTaxonomy), users: users.map(mapUser) };
}

export async function listFolderTree() {
  const nodes = await apiGet<Schemas['FolderNode'][]>('/api/v1/folders/tree');
  return flattenFolders(nodes);
}

export async function listDocuments(filters: DocumentFilters = {}) {
  const folders = await listFolderTree();
  const status = filters.archived ? 'archived' : filters.includeArchived ? 'all' : 'active';
  const sort = filters.sort === 'name' ? 'name' : filters.sort === 'oldest' ? 'oldest' : 'modified';
  const rows = await collect<Schemas['DocumentRead']>('/api/v1/documents', {
    status,
    sort,
    department_id: filters.departmentId,
    category_id: filters.categoryId,
    owner_id: filters.ownerId,
    type: filters.type ? apiSource(filters.type) : undefined,
  });
  const allowed = folderScope(filters.folderId, folders);
  const query = filters.query?.trim().toLowerCase();
  return rows.map(row => mapDocument(row)).filter(document => {
    if (allowed && !allowed.has(document.folderId)) return false;
    if (filters.tag && !document.tags.some(tag => tag.toLowerCase() === filters.tag?.toLowerCase())) return false;
    if (filters.from && document.modifiedAt.slice(0, 10) < filters.from) return false;
    if (filters.to && document.modifiedAt.slice(0, 10) > filters.to) return false;
    if (query && !`${document.name} ${document.description} ${document.tags.join(' ')}`.toLowerCase().includes(query)) return false;
    return true;
  });
}

export async function getDocument(id: string) {
  const row = await apiGet<Schemas['DocumentRead']>(`/api/v1/documents/${id}`);
  const versions = await apiGet<Schemas['VersionRead'][]>(`/api/v1/documents/${id}/versions`).catch(() => []);
  let content = '';
  if (!row.source_type.startsWith('google')) {
    const body = await apiGet<Schemas['ContentRead']>(`/api/v1/documents/${id}/content?limit=8000`).catch(() => null);
    content = body?.text ?? '';
  }
  return mapDocument(row, { content, versions: versions.map(mapVersion) });
}

export function getEmbed(id: string) {
  return apiGet<Schemas['EmbedRead']>(`/api/v1/documents/${id}/embed`).then(row => ({ previewUrl: row.preview_url, editUrl: row.edit_url, openUrl: row.open_url }));
}

export async function getRelatedDocuments(id: string) {
  const page = await apiGet<Schemas['RelatedList']>(`/api/v1/documents/${id}/related`);
  return page.items.map(mapRelated);
}

export function recordView() {
  return Promise.resolve();
}

export function checkGoogleSharing(url: string) {
  return apiSend<Schemas['GooglePreviewRead']>('/api/v1/documents/google/preview', { method: 'POST', json: { url } }).then(row => ({
    shared: row.shared,
    fileId: row.file_id ?? '',
    email: row.service_account_email,
  }));
}

export async function createDocument(input: CreateDocumentInput, onProgress?: (percent: number) => void) {
  const folderId = requireFolder(input.folderId);
  const tag_ids = await resolveTags(input.tags);
  if (input.file) {
    const form = new FormData();
    form.set('file', input.file);
    form.set('name', input.name.trim());
    form.set('folder_id', folderId);
    form.set('category_id', input.categoryId);
    form.set('department_id', input.departmentId);
    form.set('visibility', input.access.level);
    form.set('default_access', input.access.defaultPermission);
    if (input.description) form.set('description', input.description);
    if (tag_ids.length) form.set('tag_ids', tag_ids.join(','));
    const row = await apiUpload<Schemas['DocumentRead']>('/api/v1/documents/upload', form, onProgress);
    return mapDocument(row);
  }
  if (input.googleUrl) {
    const row = await apiSend<Schemas['DocumentRead']>('/api/v1/documents/google/link', { method: 'POST', json: { url: input.googleUrl, metadata: metadata(input, folderId, tag_ids) } });
    return mapDocument(row);
  }
  if (input.type.startsWith('google')) {
    const row = await apiSend<Schemas['DocumentRead']>('/api/v1/documents/google/create', {
      method: 'POST',
      json: { title: input.name.trim(), type: googleKind(input.type), template: input.template && input.template !== 'blank' ? input.template : null, folder_id: folderId, metadata: metadata(input, folderId, tag_ids) },
    });
    return mapDocument(row);
  }
  const row = await apiSend<Schemas['DocumentRead']>('/api/v1/documents', {
    method: 'POST',
    json: { name: input.name.trim(), description: input.description || null, folder_id: folderId, category_id: input.categoryId, department_id: input.departmentId, source_type: apiSource(input.type), visibility: input.access.level, default_access: input.access.defaultPermission, tag_ids },
  });
  return mapDocument(row);
}

export async function updateDocument(id: string, changes: Partial<Pick<Document, 'name' | 'description' | 'tags' | 'content' | 'starred'>>) {
  const body: Record<string, unknown> = {};
  if (changes.name) body.name = changes.name;
  if (changes.description !== undefined) body.description = changes.description;
  if (changes.tags) body.tag_ids = await resolveTags(changes.tags);
  if (!Object.keys(body).length) return getDocument(id);
  const row = await apiSend<Schemas['DocumentRead']>(`/api/v1/documents/${id}`, { method: 'PATCH', json: body });
  return mapDocument(row);
}

export async function bulkDocuments(ids: string[], action: 'archive' | 'restore' | 'delete' | 'move', folderId?: string) {
  for (const id of ids) {
    if (action === 'move') await apiSend(`/api/v1/documents/${id}/move`, { method: 'POST', json: { folder_id: requireFolder(folderId) } });
    else if (action === 'delete') await apiSend(`/api/v1/documents/${id}/permanent-delete`, { method: 'POST' });
    else await apiSend(`/api/v1/documents/${id}/${action}`, { method: 'POST' });
  }
  return ids.length;
}

export function uploadVersion(id: string, file: File) {
  const form = new FormData();
  form.set('file', file);
  form.set('change_note', 'New version uploaded');
  return apiUpload<Schemas['DocumentRead']>(`/api/v1/documents/${id}/versions`, form).then(mapDocument);
}

export function restoreVersion(id: string, version: number) {
  return apiSend<Schemas['DocumentRead']>(`/api/v1/documents/${id}/versions/${version}/restore`, { method: 'POST', json: { change_note: `Restored from version ${version}` } }).then(mapDocument);
}

export async function createFolder(input: { name: string; parentId: string; departmentId: string }, folders: { id: string; departmentId: string }[] = []) {
  const known = folders.length ? folders : await listFolderTree();
  const parent = known.find(folder => folder.id === input.parentId);
  return apiSend<Schemas['FolderRead']>('/api/v1/folders', {
    method: 'POST',
    json: { name: input.name.trim(), parent_id: requireFolder(input.parentId), department_id: parent?.departmentId || input.departmentId, visibility: 'department', default_access: 'edit' },
  }).then(row => ({ id: toUiFolderId(row.id) ?? row.id, name: row.name }));
}

export async function updateFolder(id: string, changes: { name?: string; parentId?: string; archived?: boolean }) {
  if (changes.archived !== undefined) throw new ApiError(409, 'UNSUPPORTED', 'Folders stay in the tree. Archive the documents inside them, or delete an empty folder.');
  if (changes.name) await apiSend(`/api/v1/folders/${requireFolder(id)}`, { method: 'PATCH', json: { name: changes.name } });
  if (changes.parentId) await apiSend(`/api/v1/folders/${requireFolder(id)}/move`, { method: 'POST', json: { parent_id: requireFolder(changes.parentId) } });
}

export function deleteFolder(id: string) {
  return apiSend(`/api/v1/folders/${requireFolder(id)}`, { method: 'DELETE' });
}

export async function listArchived(): Promise<ArchiveItem[]> {
  const rows = await collect<Schemas['DocumentRead']>('/api/v1/documents', { status: 'archived' });
  return rows.map(row => mapDocument(row)).filter(document => document.myAccess === 'manage').map(document => ({
    kind: 'document' as const, id: document.id, name: document.name, departmentId: document.departmentId, ownerId: document.ownerId, type: document.type, modifiedAt: document.modifiedAt,
  }));
}

export async function searchDocuments(query: string, filters: DocumentFilters) {
  const tags = filters.tag ? await apiGet<Schemas['TaxonomyRead'][]>('/api/v1/tags') : [];
  const tag = tags.find(item => item.name.toLowerCase() === filters.tag?.toLowerCase());
  const params = new URLSearchParams({ q: query, page_size: '50' });
  if (filters.departmentId) params.set('department', filters.departmentId);
  if (filters.categoryId) params.set('category', filters.categoryId);
  if (filters.ownerId) params.set('owner', filters.ownerId);
  if (filters.type) params.set('type', apiSource(filters.type));
  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  if (filters.includeArchived || filters.archived) params.set('include_archived', 'true');
  if (tag) params.append('tags', tag.id);
  const page = await apiGet<Schemas['SearchResponse']>(`/api/v1/search?${params.toString()}`);
  return page.items.map(mapSearchHit);
}

export function getDashboard() {
  return apiGet<Schemas['DashboardResponse']>('/api/v1/dashboard').then(mapDashboard);
}

export async function listUsers(filters: { query?: string; role?: string; departmentId?: string; status?: string } = {}) {
  const rows = await collect<Schemas['UserRead']>('/api/v1/users', {
    search: filters.query,
    role: filters.role,
    department_id: filters.departmentId,
    status: filters.status,
  });
  return rows.map(mapUser);
}

export function inviteUser(input: { email: string; role: Role; departmentId: string; accountType?: 'person' | 'bot' }) {
  return apiSend<Schemas['UserRead']>('/api/v1/users/invite', { method: 'POST', json: { email: input.email, role: input.role, department_id: input.departmentId, is_bot: input.accountType === 'bot' } }).then(mapUser);
}

export function updateUser(id: string, changes: { role?: Role; departmentId?: string; status?: User['status'] }) {
  if (changes.status === 'deactivated') return apiSend<Schemas['UserRead']>(`/api/v1/users/${id}/deactivate`, { method: 'POST' }).then(mapUser);
  if (changes.status === 'active') return apiSend<Schemas['UserRead']>(`/api/v1/users/${id}/reactivate`, { method: 'POST' }).then(mapUser);
  const body: Record<string, unknown> = {};
  if (changes.role) body.role = changes.role;
  if (changes.departmentId) body.department_id = changes.departmentId;
  return apiSend<Schemas['UserRead']>(`/api/v1/users/${id}`, { method: 'PATCH', json: body }).then(mapUser);
}

export async function listTaxonomy(kind: TaxonomyKind) {
  const path = kind === 'departments' ? '/api/v1/departments' : `/api/v1/${kind}`;
  const rows = await apiGet<(Schemas['TaxonomyRead'] | Schemas['DepartmentRead'])[]>(path);
  return rows.map(row => mapTaxonomy(row));
}

export async function saveTaxonomy(kind: TaxonomyKind, input: { id?: string; name: string; description: string; code?: string }) {
  const path = kind === 'departments' ? '/api/v1/departments' : `/api/v1/${kind}`;
  const body = kind === 'departments' && !input.id ? { name: input.name.trim(), description: input.description, code: slug(input.name) } : { name: input.name.trim(), description: input.description };
  const row = await apiSend<Schemas['TaxonomyRead'] | Schemas['DepartmentRead']>(input.id ? `${path}/${input.id}` : path, { method: input.id ? 'PATCH' : 'POST', json: body });
  return mapTaxonomy(row);
}

export function deleteTaxonomy(kind: TaxonomyKind, id: string) {
  const path = kind === 'departments' ? '/api/v1/departments' : `/api/v1/${kind}`;
  return apiSend(`${path}/${id}`, { method: 'DELETE' });
}

export async function getPermissions(target: ResourceTarget) {
  const id = target.kind === 'folder' ? requireFolder(target.id) : target.id;
  const permissions = await apiGet<Schemas['PermissionsRead']>(`/api/v1/${target.kind}s/${id}/permissions`);
  if (target.kind === 'document') {
    const document = await apiGet<Schemas['DocumentRead']>(`/api/v1/documents/${id}`);
    return { access: accessFrom(permissions, mapGrants(permissions.grants)), ownerId: document.owner_id, departmentId: document.department_id };
  }
  const folder = (await listFolderTree()).find(item => item.id === target.id);
  return { access: accessFrom(permissions, mapGrants(permissions.grants)), ownerId: folder?.ownerId ?? '', departmentId: folder?.departmentId ?? '' };
}

export function updatePermissions(target: ResourceTarget, access: Access) {
  const id = target.kind === 'folder' ? requireFolder(target.id) : target.id;
  return apiSend<Schemas['PermissionsRead']>(`/api/v1/${target.kind}s/${id}/permissions`, {
    method: 'PUT',
    json: { visibility: access.level, default_access: access.defaultPermission, grants: access.grants.map(grant => ({ principal_type: grant.principalType, principal_id: grant.principalId, access: grant.permission })) },
  }).then(row => accessFrom(row, mapGrants(row.grants)));
}

export async function retryPermissionSync(target: ResourceTarget) {
  if (target.kind === 'document') await apiSend(`/api/v1/documents/${target.id}/resync`, { method: 'POST' });
  return (await getPermissions(target)).access;
}

export function listDocumentAccess(documentId: string) {
  return apiGet<Schemas['DocumentEventPage']>(`/api/v1/documents/${documentId}/events`).then(page => page.items.map(row => ({
    id: row.id,
    documentId: row.document_id,
    time: row.created_at,
    channel: accessChannel(row.channel),
    clientName: row.client_name || (row.channel === 'web' ? 'Web' : row.channel === 'mcp' ? 'MCP' : 'API'),
    userId: row.user_id,
  })));
}

export function listTokens(everyone = false) {
  return apiGet<Schemas['TokenPage']>(everyone ? '/api/v1/admin/tokens' : '/api/v1/tokens').then(page => page.items.map(mapToken));
}

export function createToken(input: CreateTokenInput) {
  return apiSend<Schemas['TokenCreated']>('/api/v1/tokens', { method: 'POST', json: { name: input.name.trim(), scopes: input.scopes, expires_in_days: input.expiresInDays } }).then(row => ({ ...mapToken(row), secret: row.token }));
}

export function revokeToken(id: string, actor: User) {
  return apiSend(isAdmin(actor) ? `/api/v1/admin/tokens/${id}` : `/api/v1/tokens/${id}`, { method: 'DELETE' });
}

export function listGrants(everyone = false) {
  return apiGet<Schemas['OAuthGrantPage']>(everyone ? '/api/v1/admin/grants' : '/api/v1/oauth/grants').then(page => page.items.map(mapGrant));
}

export function revokeGrant(id: string, actor: User) {
  return apiSend(isAdmin(actor) ? `/api/v1/admin/grants/${id}` : `/api/v1/oauth/grants/${id}`, { method: 'DELETE' });
}

export async function listAuditLog(filters: AuditFilters = {}) {
  const params = new URLSearchParams({ limit: '100' });
  const channel = auditQueryChannel(filters.channel);
  if (channel && filters.everyone) params.set('channel', channel);
  const path = filters.everyone ? '/api/v1/admin/audit-log' : '/api/v1/me/audit-log';
  const first = await apiGet<Schemas['AuditPage']>(`${path}?${params.toString()}`);
  let items = first.items;
  let cursor = first.next_cursor;
  let hops = 0;
  while (cursor && hops < 4) {
    params.set('cursor', cursor);
    const next = await apiGet<Schemas['AuditPage']>(`${path}?${params.toString()}`);
    items = items.concat(next.items);
    cursor = next.next_cursor;
    hops += 1;
  }
  const client = filters.client?.trim().toLowerCase() ?? '';
  return items.map(mapAudit).filter(event => (!filters.channel || event.channel === filters.channel) && (!filters.status || event.status === filters.status) && (!client || event.clientName.toLowerCase().includes(client)));
}

export function getOrgSettings() {
  return apiGet<Schemas['OrgSettingsRead']>('/api/v1/org-settings').then(mapOrg);
}

export function updateOrgSettings(changes: Partial<{ allowExternalAi: boolean; allowWriteScopes: boolean; maxTokenLifetimeDays: number }>) {
  const body: Record<string, unknown> = {};
  if (changes.allowExternalAi !== undefined) body.external_ai_enabled = changes.allowExternalAi;
  if (changes.allowWriteScopes !== undefined) body.allow_write_scopes = changes.allowWriteScopes;
  if (changes.maxTokenLifetimeDays !== undefined) body.max_token_days = changes.maxTokenLifetimeDays;
  return apiSend<Schemas['OrgSettingsRead']>('/api/v1/admin/org-settings', { method: 'PATCH', json: body }).then(mapOrg);
}

export function getConsentRequest(requestId: string) {
  return apiGet<Schemas['ConsentView']>(`/api/v1/oauth/consent-request?request_id=${encodeURIComponent(requestId)}`).then(row => ({
    appName: row.app_name,
    redirectDomain: row.redirect_domain,
    verified: row.verified,
    writeRequested: row.write_requested,
    allowWrite: row.allow_write,
    externalAccess: row.external_access,
    userName: row.user_name,
  }));
}

export function submitConsent(requestId: string, input: ConsentDecision) {
  return apiSend<Schemas['ConsentResult']>('/api/v1/oauth/consent', { method: 'POST', json: { request_id: requestId, decision: input.decision, scopes: input.scopes } }).then(row => ({
    decision: input.decision,
    redirectTo: row.redirect_to,
  }));
}

async function collect<T>(path: string, params: Record<string, string | undefined>) {
  const items: T[] = [];
  let page = 1;
  let total = Number.POSITIVE_INFINITY;
  while (items.length < total && page <= 20) {
    const query = new URLSearchParams({ page: String(page), page_size: '100' });
    for (const [key, value] of Object.entries(params)) if (value) query.set(key, value);
    const body = await apiGet<{ items: T[]; total?: number }>(`${path}?${query.toString()}`);
    items.push(...body.items);
    total = body.total ?? items.length;
    if (!body.items.length) break;
    page += 1;
  }
  return items;
}

async function resolveTags(names: string[]) {
  if (!names.length) return [];
  const tags = await apiGet<Schemas['TaxonomyRead'][]>('/api/v1/tags');
  const ids: string[] = [];
  for (const name of names) {
    const found = tags.find(tag => tag.name.toLowerCase() === name.toLowerCase());
    if (found) { ids.push(found.id); continue; }
    try {
      const created = await apiSend<Schemas['TaxonomyRead']>('/api/v1/tags', { method: 'POST', json: { name, description: '' } });
      tags.push(created);
      ids.push(created.id);
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) throw new ApiError(403, 'FORBIDDEN', `Ask an admin to add the “${name}” tag before using it.`);
      throw error;
    }
  }
  return ids;
}

function metadata(input: CreateDocumentInput, folderId: string, tagIds: string[]) {
  return { name: input.name.trim(), description: input.description || null, folder_id: folderId, category_id: input.categoryId, department_id: input.departmentId, visibility: input.access.level, default_access: input.access.defaultPermission, tag_ids: tagIds };
}

function googleKind(type: DocumentType) {
  if (type === 'google-sheet') return 'sheet';
  if (type === 'google-slide') return 'slide';
  return 'doc';
}

function requireFolder(id: string | null | undefined) {
  const value = toApiFolderId(id);
  if (!value) throw new ApiError(422, 'FOLDER_REQUIRED', 'Choose a folder.');
  return value;
}

function folderScope(folderId: string | undefined, folders: { id: string; parentId: string | null }[]) {
  if (!folderId || folderId === 'root') return null;
  const ids = new Set<string>();
  const visit = (id: string) => { ids.add(id); folders.filter(folder => folder.parentId === id).forEach(folder => visit(folder.id)); };
  visit(folderId);
  return ids;
}

function slug(name: string) {
  let base = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 20);
  if (!/^[a-z]/.test(base)) base = `team${base ? `-${base}` : ''}`;
  return `${base}-${Math.random().toString(36).slice(2, 6)}`.slice(0, 32);
}
