export type Role = 'super_admin' | 'admin' | 'manager' | 'employee' | 'guest';
export type UserStatus = 'active' | 'invited' | 'deactivated';
export type AccessLevel = 'private' | 'department' | 'organization' | 'custom';
export type Permission = 'view' | 'edit';
export type DocumentType = 'google-doc' | 'google-sheet' | 'google-slide' | 'pdf' | 'docx' | 'xlsx' | 'ppt' | 'txt' | 'image';
export type SyncStatus = 'synced' | 'pending' | 'failed';
export type TaxonomyKind = 'departments' | 'categories' | 'tags';

export type AccountType = 'person' | 'bot';
export interface User {
  id: string; name: string; email: string; role: Role; departmentId: string;
  status: UserStatus; color: string; lastActive: string; accountType?: AccountType;
}
export type MyAccess = 'none' | 'view' | 'edit' | 'manage';
export interface Taxonomy { id: string; name: string; description: string; color?: string; code?: string }
export interface Grant { principalType: 'user' | 'department'; principalId: string; permission: Permission }
export interface Access { level: AccessLevel; defaultPermission: Permission; grants: Grant[]; syncStatus: SyncStatus; syncError?: string | null }
export interface Folder {
  id: string; name: string; parentId: string | null; departmentId: string; ownerId: string;
  access: Access; archived: boolean; documentCount?: number; restricted?: boolean; myAccess?: MyAccess;
}
export interface DocumentVersion {
  number: number; createdAt: string; uploadedBy: string; size: number; note: string; fileUrl?: string; fileName?: string; content?: string;
}
export interface Document {
  id: string; name: string; description: string; type: DocumentType; tags: string[];
  categoryId: string; departmentId: string; folderId: string; ownerId: string;
  createdAt: string; modifiedAt: string; version: number; access: Access; archived: boolean;
  views: number; size: number; content: string; googleFileId?: string; fileUrl?: string;
  fileName?: string; versions: DocumentVersion[]; starred: boolean; myAccess?: MyAccess; openUrl?: string | null;
}
export interface DocumentFilters {
  folderId?: string; departmentId?: string; categoryId?: string; tag?: string;
  type?: string; ownerId?: string; query?: string; archived?: boolean;
  includeArchived?: boolean; from?: string; to?: string;
  sort?: 'modified' | 'name' | 'views' | 'oldest' | 'relevance';
}
export interface SearchResult { document: Document; matchedIn: ('name' | 'tag' | 'content' | 'category' | 'description')[]; snippet: string; score: number }
export interface Dashboard {
  totalDocuments: number; addedThisMonth: number; activeUsers: number;
  byDepartment: { name: string; count: number; color: string }[];
  recent: Document[]; popular: Document[]; previousMonth: number;
  agentCalls30d: number; agentSparkline: number[];
}
export interface ReferenceData { departments: Taxonomy[]; categories: Taxonomy[]; tags: Taxonomy[]; users: User[] }
export interface CreateDocumentInput {
  name: string; description: string; tags: string[]; categoryId: string; departmentId: string;
  folderId: string; access: Access; type: DocumentType; googleUrl?: string; template?: string; file?: File;
}
export interface ResourceTarget { kind: 'document' | 'folder'; id: string; name: string }
export interface ArchiveItem { kind: 'document' | 'folder'; id: string; name: string; departmentId: string; ownerId: string; type?: DocumentType; modifiedAt?: string }

export type TokenScope = 'docs:read' | 'docs:write';
export type TokenStatus = 'active' | 'expired' | 'revoked';
export type TokenLifetime = 30 | 90 | 365;
export type AuditChannel = 'REST' | 'MCP';
export type AccessChannel = 'Web' | 'API' | 'MCP';
export type AuditStatus = 'ok' | 'error' | 'denied';

export interface AccessToken {
  id: string; userId: string; name: string; prefix: string; scopes: TokenScope[];
  createdAt: string; lastUsedAt: string | null; expiresAt: string; status: TokenStatus;
}
export interface CreatedAccessToken extends AccessToken { secret: string }
export interface CreateTokenInput { name: string; scopes: TokenScope[]; expiresInDays: TokenLifetime }
export interface OAuthGrant {
  id: string; userId: string; appName: string; redirectDomain: string; verified: boolean;
  scopes: TokenScope[]; grantedAt: string; lastUsedAt: string | null; status: 'active' | 'revoked';
}
export interface AuditEvent {
  id: string; userId: string; time: string; channel: AuditChannel; clientName: string;
  toolOrEndpoint: string; status: AuditStatus; durationMs: number;
}
export interface AuditFilters { everyone?: boolean; channel?: AuditChannel | ''; status?: AuditStatus | ''; client?: string }
export interface OrgSettings { allowExternalAi: boolean; allowWriteScopes: boolean; maxTokenLifetimeDays: TokenLifetime }
export interface DocumentAccessEvent {
  id: string; documentId: string; time: string; channel: AccessChannel; clientName: string; userId: string;
}
export interface ConsentQuery { app?: string | null; redirectUri?: string | null; verified?: string | null; scope?: string | null }
export interface ConsentRequest {
  appName: string; redirectDomain: string; verified: boolean; writeRequested: boolean;
  allowWrite: boolean; externalAccess: boolean; userName: string;
}
export interface ConsentDecision { decision: 'allow' | 'deny'; appName: string; redirectDomain: string; scopes: TokenScope[] }
export interface ConsentResult { decision: 'allow' | 'deny'; grantId?: string; redirectTo?: string }
