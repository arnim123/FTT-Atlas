import type { AccessToken, AuditEvent, DocumentAccessEvent, OAuthGrant, OrgSettings } from '@/types';

const hour = 60 * 60 * 1000;
const day = 24 * hour;
const at = (offset: number) => new Date(Date.now() + offset).toISOString();

export const seedOrgSettings: OrgSettings = { allowExternalAi: true, allowWriteScopes: true, maxTokenLifetimeDays: 365 };

export const seedTokens: AccessToken[] = [
  { id: 'tok-1', userId: 'u1', name: 'ChatGPT desktop', prefix: 'dms_pat_ab12', scopes: ['docs:read'], createdAt: at(-40 * day), lastUsedAt: at(-1 * hour), expiresAt: at(200 * day), status: 'active' },
  { id: 'tok-2', userId: 'u1', name: 'Cursor local', prefix: 'dms_pat_c4e8', scopes: ['docs:read', 'docs:write'], createdAt: at(-12 * day), lastUsedAt: at(-2 * hour), expiresAt: at(78 * day), status: 'active' },
  { id: 'tok-3', userId: 'u1', name: 'Legacy export', prefix: 'dms_pat_91fa', scopes: ['docs:read'], createdAt: at(-200 * day), lastUsedAt: at(-40 * day), expiresAt: at(-20 * day), status: 'expired' },
  { id: 'tok-4', userId: 'u2', name: 'Claude research', prefix: 'dms_pat_77b0', scopes: ['docs:read'], createdAt: at(-60 * day), lastUsedAt: at(-30 * day), expiresAt: at(30 * day), status: 'revoked' },
  { id: 'tok-5', userId: 'u4', name: 'Grok notes', prefix: 'dms_pat_e21d', scopes: ['docs:read'], createdAt: at(-8 * day), lastUsedAt: at(-5 * hour), expiresAt: at(82 * day), status: 'active' },
  { id: 'tok-6', userId: 'u13', name: 'Indexer sync', prefix: 'dms_pat_55ac', scopes: ['docs:read', 'docs:write'], createdAt: at(-3 * day), lastUsedAt: at(-20 * 60 * 1000), expiresAt: at(362 * day), status: 'active' },
];

export const seedGrants: OAuthGrant[] = [
  { id: 'grant-1', userId: 'u1', appName: 'ChatGPT', redirectDomain: 'chatgpt.com', verified: true, scopes: ['docs:read'], grantedAt: at(-20 * day), lastUsedAt: at(-1 * hour), status: 'active' },
  { id: 'grant-2', userId: 'u1', appName: 'Claude', redirectDomain: 'claude.ai', verified: true, scopes: ['docs:read', 'docs:write'], grantedAt: at(-10 * day), lastUsedAt: at(-3 * hour), status: 'active' },
  { id: 'grant-3', userId: 'u3', appName: 'Cursor', redirectDomain: 'cursor.com', verified: true, scopes: ['docs:read'], grantedAt: at(-6 * day), lastUsedAt: at(-1 * day), status: 'active' },
];

const clients: { name: string; channel: AuditEvent['channel']; tool: string }[] = [
  { name: 'ChatGPT', channel: 'MCP', tool: 'documents.read' },
  { name: 'Claude', channel: 'MCP', tool: 'documents.search' },
  { name: 'Grok', channel: 'REST', tool: 'GET /v1/documents' },
  { name: 'Cursor', channel: 'MCP', tool: 'documents.list' },
  { name: 'Claude Code', channel: 'REST', tool: 'GET /v1/documents/{id}' },
  { name: 'Warehouse bot', channel: 'REST', tool: 'POST /v1/documents/{id}' },
];
const actors = ['u1', 'u1', 'u1', 'u1', 'u2', 'u3', 'u4', 'u7', 'u13'];
const statuses: AuditEvent['status'][] = ['ok', 'ok', 'ok', 'ok', 'ok', 'error', 'denied'];

export const seedAudit: AuditEvent[] = Array.from({ length: 60 }, (_, index) => {
  const client = clients[index % clients.length];
  return {
    id: `audit-${index + 1}`, userId: actors[index % actors.length], time: at(-index * 5 * hour),
    channel: client.channel, clientName: client.name, toolOrEndpoint: client.tool,
    status: statuses[index % statuses.length], durationMs: 80 + (index * 53) % 1400,
  };
});

const accessRows: [string, DocumentAccessEvent['channel'], string, string][] = [
  ['doc-1', 'MCP', 'ChatGPT', 'u1'],
  ['doc-1', 'Web', 'Atlas web', 'u1'],
  ['doc-1', 'API', 'Warehouse bot', 'u13'],
  ['doc-1', 'MCP', 'Claude', 'u2'],
  ['doc-1', 'MCP', 'Cursor', 'u3'],
  ['doc-4', 'MCP', 'ChatGPT', 'u7'],
  ['doc-4', 'Web', 'Atlas web', 'u7'],
  ['doc-4', 'API', 'Claude Code', 'u7'],
  ['doc-11', 'Web', 'Atlas web', 'u4'],
  ['doc-11', 'MCP', 'Grok', 'u4'],
  ['doc-2', 'Web', 'Atlas web', 'u2'],
  ['doc-2', 'API', 'Custom script', 'u2'],
  ['doc-15', 'MCP', 'Cursor', 'u7'],
  ['doc-6', 'Web', 'Atlas web', 'u9'],
  ['doc-8', 'MCP', 'Claude', 'u2'],
  ['doc-3', 'API', 'Grok', 'u8'],
];

export const seedDocumentAccess: DocumentAccessEvent[] = accessRows.map(([documentId, channel, clientName, userId], index) => ({
  id: `access-${index + 1}`, documentId, channel, clientName, userId, time: at(-(index + 1) * 3 * hour),
}));
