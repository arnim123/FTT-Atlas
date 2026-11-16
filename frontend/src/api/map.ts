import type { Access, AccessChannel, AccessLevel, AuditChannel, AuditEvent, AuditStatus, Dashboard, Document, DocumentType, DocumentVersion, Folder, Grant, OAuthGrant, OrgSettings, Permission, SearchResult, SyncStatus, Taxonomy, TokenScope, User } from '@/types';
import { absoluteApi, type Schemas } from './http';
import { rememberWorkspaceRoot, toUiFolderId } from './ids';

const SOURCE_TO_UI: Record<string, DocumentType> = {
  google_doc: 'google-doc', google_sheet: 'google-sheet', google_slide: 'google-slide',
  pdf: 'pdf', docx: 'docx', xlsx: 'xlsx', ppt: 'ppt', txt: 'txt', image: 'image',
};
const COLORS = ['sage', 'rose', 'sand', 'lavender', 'blue'];
const CHART = ['#4a8b78', '#6b8f71', '#8aa4b5', '#c4a574', '#b07d74'];

export function uiSource(value: string): DocumentType {
  return SOURCE_TO_UI[value] ?? 'txt';
}

export function apiSource(value: string) {
  return value.replaceAll('-', '_');
}

export function colorFor(id: string) {
  let hash = 0;
  for (const char of id) hash = (hash + char.charCodeAt(0)) % COLORS.length;
  return COLORS[hash];
}

export function syncStatus(value: string | null | undefined): SyncStatus {
  if (value === 'pending' || value === 'failed') return value;
  return 'synced';
}

export function mapGrants(rows: { principal_type: string; principal_id: string; access: string }[]): Grant[] {
  return rows.map(row => ({ principalType: row.principal_type as Grant['principalType'], principalId: row.principal_id, permission: row.access as Permission }));
}

export function accessFrom(row: { visibility?: string | null; default_access?: string | null; drive_sync_status?: string | null; drive_sync_error?: string | null }, grants: Grant[] = []): Access {
  return {
    level: (row.visibility || 'private') as AccessLevel,
    defaultPermission: (row.default_access || 'view') as Permission,
    grants,
    syncStatus: syncStatus(row.drive_sync_status),
    syncError: row.drive_sync_error ?? null,
  };
}

export function mapUser(row: Schemas['UserRead']): User {
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    role: row.role,
    departmentId: row.department_id,
    status: row.status,
    color: colorFor(row.id),
    lastActive: row.last_seen_at ?? row.last_login_at ?? row.created_at,
    accountType: row.is_bot ? 'bot' : 'person',
  };
}

export function mapTaxonomy(row: { id: string; name: string; description?: string | null; code?: string }): Taxonomy {
  return { id: row.id, name: row.name, description: row.description ?? '', code: row.code, color: CHART[colorIndex(row.id)] };
}

export function mapDocument(row: Schemas['DocumentRead'], extras: { content?: string; versions?: DocumentVersion[] } = {}): Document {
  return {
    id: row.id,
    name: row.name,
    description: row.description ?? '',
    type: uiSource(row.source_type),
    tags: row.tags.map(tag => tag.name),
    categoryId: row.category_id,
    departmentId: row.department_id,
    folderId: toUiFolderId(row.folder_id) ?? row.folder_id,
    ownerId: row.owner_id,
    createdAt: row.created_at,
    modifiedAt: row.last_modified_at ?? row.updated_at,
    version: row.current_version_number,
    access: accessFrom(row),
    archived: row.status === 'archived',
    views: 0,
    size: row.size_bytes ?? 0,
    content: extras.content ?? '',
    googleFileId: fileId(row.google_web_url),
    fileUrl: row.file_url ? absoluteApi(row.file_url) : undefined,
    fileName: row.original_filename ?? undefined,
    versions: extras.versions ?? [],
    starred: false,
    myAccess: row.my_access,
    openUrl: row.google_web_url,
  };
}

export function mapVersion(row: Schemas['VersionRead']): DocumentVersion {
  return {
    number: row.version_number,
    createdAt: row.created_at,
    uploadedBy: row.uploaded_by ?? '',
    size: row.size_bytes ?? 0,
    note: row.change_note ?? '',
    fileUrl: absoluteApi(row.download_url),
    fileName: row.original_filename ?? undefined,
  };
}

export function flattenFolders(nodes: Schemas['FolderNode'][]): Folder[] {
  const folders: Folder[] = [];
  const walk = (items: Schemas['FolderNode'][], parentUiId: string | null, topLevel: boolean) => {
    let rooted = false;
    for (const node of items) {
      const top = topLevel && !node.parent_id && !rooted;
      if (top) { rooted = true; rememberWorkspaceRoot(node.id); }
      const uiId = top ? 'root' : node.id;
      folders.push({
        id: uiId,
        name: node.name,
        parentId: parentUiId,
        departmentId: node.department_id ?? '',
        ownerId: node.owner_id ?? '',
        access: accessFrom(node),
        archived: false,
        documentCount: node.document_count,
        restricted: node.path_only || node.my_access === 'none',
        myAccess: node.my_access ?? 'none',
      });
      walk(node.children ?? [], uiId, false);
    }
  };
  walk(nodes, null, true);
  if (!folders.some(folder => folder.id === 'root') && folders[0]) rememberWorkspaceRoot(folders[0].id);
  return folders.map(folder => ({ ...folder, documentCount: descendantCount(folder.id, folders) }));
}

export function mapRelated(row: Schemas['RelatedDocumentRead']): Document {
  return stubDocument({
    id: row.id,
    name: row.name,
    type: uiSource(row.source_type),
    departmentId: row.department_id,
    folderId: toUiFolderId(row.folder_id) ?? row.folder_id,
  });
}

export function mapSearchHit(row: Schemas['SearchHitRead']): SearchResult {
  const document = stubDocument({
    id: row.id,
    name: row.name,
    description: row.description ?? '',
    type: uiSource(row.source_type),
    tags: row.tags.map(tag => tag.name),
    categoryId: row.category_id,
    departmentId: row.department_id,
    folderId: toUiFolderId(row.folder_id) ?? row.folder_id,
    ownerId: row.owner_id,
    createdAt: row.created_at,
    modifiedAt: row.last_modified_at ?? row.created_at,
    archived: row.status === 'archived',
    openUrl: row.google_url,
  });
  return { document, matchedIn: row.matched_in, snippet: row.snippet, score: row.score };
}

export function mapDashboard(row: Schemas['DashboardResponse']): Dashboard {
  const calls = row.ai_agent_calls_30d ?? 0;
  return {
    totalDocuments: row.total_documents,
    addedThisMonth: row.added_this_month,
    activeUsers: row.active_users.count,
    byDepartment: row.by_department.map((item, index) => ({ name: item.name, count: item.count, color: CHART[index % CHART.length] })),
    recent: row.recent_uploads.map(item => mapDashboardDocument(item)),
    popular: row.most_viewed.map(item => mapDashboardDocument(item, item.view_count ?? 0)),
    previousMonth: Math.max(0, row.total_documents - row.added_this_month),
    agentCalls30d: calls,
    agentSparkline: Array.from({ length: 14 }, () => calls),
  };
}

export function mapToken(row: Schemas['TokenRead']) {
  const status = row.revoked_at ? 'revoked' as const : row.expires_at && Date.parse(row.expires_at) <= Date.now() ? 'expired' as const : 'active' as const;
  return {
    id: row.id,
    userId: row.user_id,
    name: row.name,
    prefix: row.token_prefix,
    scopes: row.scopes.filter(isScope),
    createdAt: row.created_at,
    lastUsedAt: row.last_used_at,
    expiresAt: row.expires_at ?? row.created_at,
    status,
  };
}

export function mapGrant(row: Schemas['OAuthGrantRead']): OAuthGrant {
  return {
    id: row.id,
    userId: row.user_id,
    appName: row.client_name,
    redirectDomain: row.redirect_domain,
    verified: row.verified,
    scopes: row.scopes.filter(isScope),
    grantedAt: row.created_at,
    lastUsedAt: row.last_used_at,
    status: row.revoked_at ? 'revoked' : 'active',
  };
}

export function mapAudit(row: Schemas['AuditRead']): AuditEvent {
  return {
    id: row.id,
    userId: row.user_id,
    time: row.created_at,
    channel: row.channel === 'mcp' ? 'MCP' : 'REST',
    clientName: row.user_agent || row.operation,
    toolOrEndpoint: row.operation,
    status: auditStatus(row.status_code),
    durationMs: row.duration_ms,
  };
}

export function mapOrg(row: Schemas['OrgSettingsRead']): OrgSettings {
  const days = row.max_token_days === 30 || row.max_token_days === 90 || row.max_token_days === 365 ? row.max_token_days : 365;
  return { allowExternalAi: row.external_ai_enabled, allowWriteScopes: row.allow_write_scopes, maxTokenLifetimeDays: days };
}

export function accessChannel(value: string): AccessChannel {
  if (value === 'mcp') return 'MCP';
  if (value === 'rest') return 'API';
  return 'Web';
}

export function auditQueryChannel(value: AuditChannel | '' | undefined) {
  if (value === 'MCP') return 'mcp';
  if (value === 'REST') return 'rest';
  return '';
}

function mapDashboardDocument(row: Schemas['DashboardDocumentRead'], views = 0) {
  return stubDocument({
    id: row.id,
    name: row.name,
    description: row.description ?? '',
    type: uiSource(row.source_type),
    departmentId: row.department_id,
    folderId: toUiFolderId(row.folder_id) ?? row.folder_id,
    ownerId: row.owner_id,
    createdAt: row.created_at,
    modifiedAt: row.last_modified_at ?? row.created_at,
    openUrl: row.google_url,
    views,
  });
}

function stubDocument(partial: Partial<Document> & Pick<Document, 'id' | 'name'>): Document {
  return {
    description: '',
    type: 'txt',
    tags: [],
    categoryId: '',
    departmentId: '',
    folderId: 'root',
    ownerId: '',
    createdAt: new Date(0).toISOString(),
    modifiedAt: new Date(0).toISOString(),
    version: 1,
    access: { level: 'organization', defaultPermission: 'view', grants: [], syncStatus: 'synced' },
    archived: false,
    views: 0,
    size: 0,
    content: '',
    versions: [],
    starred: false,
    myAccess: 'view',
    ...partial,
  };
}

function descendantCount(id: string, folders: Folder[]): number {
  const own = folders.find(folder => folder.id === id)?.documentCount ?? 0;
  return own + folders.filter(folder => folder.parentId === id).reduce((sum, child) => sum + descendantCount(child.id, folders), 0);
}

function fileId(url: string | null) {
  return url?.match(/\/d\/([^/]+)/)?.[1];
}

function colorIndex(id: string) {
  return [...id].reduce((sum, char) => sum + char.charCodeAt(0), 0) % CHART.length;
}

function auditStatus(code: number): AuditStatus {
  if (code < 400) return 'ok';
  if (code === 401 || code === 403) return 'denied';
  return 'error';
}

function isScope(value: string): value is TokenScope {
  return value === 'docs:read' || value === 'docs:write';
}
