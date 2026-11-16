import { db } from '@/mocks/db';
import type { AccessToken, AuditFilters, ConsentDecision, ConsentQuery, CreateTokenInput, OAuthGrant, OrgSettings, TokenScope, User } from '@/types';
import { canView, isAdmin } from '@/lib/access';
import { USE_MOCKS, activeUser, assert, newId, request } from './client';
import * as live from './live';

const knownApps = [
  { name: /chatgpt/i, domain: 'chatgpt.com' },
  { name: /claude/i, domain: 'claude.ai' },
  { name: /grok/i, domain: 'grok.com' },
  { name: /cursor/i, domain: 'cursor.com' },
];

function member(actor: User) {
  const user = activeUser(actor);
  assert(user.role !== 'guest', 'Guests cannot use external AI access.');
  return user;
}
function isLifetime(value: number): value is 30 | 90 | 365 {
  return value === 30 || value === 90 || value === 365;
}
function viewToken(token: AccessToken): AccessToken {
  const status = token.status === 'revoked' ? 'revoked' : Date.parse(token.expiresAt) <= Date.now() ? 'expired' : 'active';
  return { id: token.id, userId: token.userId, name: token.name, prefix: token.prefix, scopes: [...token.scopes], createdAt: token.createdAt, lastUsedAt: token.lastUsedAt, expiresAt: token.expiresAt, status };
}
function viewGrant(grant: OAuthGrant): OAuthGrant {
  return { id: grant.id, userId: grant.userId, appName: grant.appName, redirectDomain: grant.redirectDomain, verified: grant.verified, scopes: [...grant.scopes], grantedAt: grant.grantedAt, lastUsedAt: grant.lastUsedAt, status: grant.status };
}
function scopesFor(scopes: TokenScope[], settings: OrgSettings): TokenScope[] {
  assert(scopes.includes('docs:read'), 'Tokens must include read access.');
  const write = scopes.includes('docs:write');
  assert(!write || settings.allowWriteScopes, 'This workspace does not allow write scopes.');
  return write ? ['docs:read', 'docs:write'] : ['docs:read'];
}
function mintSecret() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return `dms_pat_${[...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('')}`;
}

export function listTokens(actor: User, filters: { everyone?: boolean } = {}) {
  if (!USE_MOCKS) return live.listTokens(!!filters.everyone);
  return request(() => {
    const user = member(actor);
    assert(!filters.everyone || isAdmin(user), 'You don’t have permission to view tokens for the organization.');
    return db.tokens.filter(token => filters.everyone || token.userId === user.id).sort((a, b) => b.createdAt.localeCompare(a.createdAt)).map(viewToken);
  });
}
export function createToken(input: CreateTokenInput, actor: User) {
  if (!USE_MOCKS) return live.createToken(input);
  return request(() => {
    const user = member(actor);
    assert(db.orgSettings.allowExternalAi, 'External AI access is turned off for this workspace.');
    const name = input.name.trim();
    assert(name.length > 0 && name.length <= 60, 'Enter a token name up to 60 characters.');
    assert(isLifetime(input.expiresInDays), 'Choose a 30, 90, or 365 day lifetime.');
    assert(input.expiresInDays <= db.orgSettings.maxTokenLifetimeDays, `Tokens in this workspace can last at most ${db.orgSettings.maxTokenLifetimeDays} days.`);
    assert(!db.tokens.some(token => token.userId === user.id && token.status !== 'revoked' && token.name.toLowerCase() === name.toLowerCase()), 'You already have a token with this name.');
    const secret = mintSecret();
    const token: AccessToken = { id: newId('tok'), userId: user.id, name, prefix: secret.slice(0, 12), scopes: scopesFor(input.scopes, db.orgSettings), createdAt: new Date().toISOString(), lastUsedAt: null, expiresAt: new Date(Date.now() + input.expiresInDays * 86400000).toISOString(), status: 'active' };
    db.tokens.unshift(token);
    return { ...viewToken(token), secret };
  });
}
export function revokeToken(id: string, actor: User) {
  if (!USE_MOCKS) return live.revokeToken(id, actor);
  return request(() => {
    const user = member(actor);
    const token = db.tokens.find(item => item.id === id);
    assert(token, 'This token could not be found.');
    assert(isAdmin(user) || token.userId === user.id, 'You don’t have permission to revoke this token.');
    assert(token.status !== 'revoked', 'This token is already revoked.');
    token.status = 'revoked';
    return viewToken(token);
  });
}
export function listGrants(actor: User, filters: { everyone?: boolean } = {}) {
  if (!USE_MOCKS) return live.listGrants(!!filters.everyone);
  return request(() => {
    const user = member(actor);
    assert(!filters.everyone || isAdmin(user), 'You don’t have permission to view grants for the organization.');
    return db.grants.filter(grant => filters.everyone || grant.userId === user.id).sort((a, b) => b.grantedAt.localeCompare(a.grantedAt)).map(viewGrant);
  });
}
export function revokeGrant(id: string, actor: User) {
  if (!USE_MOCKS) return live.revokeGrant(id, actor);
  return request(() => {
    const user = member(actor);
    const grant = db.grants.find(item => item.id === id);
    assert(grant, 'This connected app could not be found.');
    assert(isAdmin(user) || grant.userId === user.id, 'You don’t have permission to revoke this grant.');
    assert(grant.status !== 'revoked', 'This grant is already revoked.');
    grant.status = 'revoked';
    return viewGrant(grant);
  });
}
export function listAuditLog(actor: User, filters: AuditFilters = {}) {
  if (!USE_MOCKS) return live.listAuditLog(filters);
  return request(() => {
    const user = member(actor);
    assert(!filters.everyone || isAdmin(user), 'You don’t have permission to view activity for the organization.');
    const client = filters.client?.trim().toLowerCase() ?? '';
    return db.audit.filter(event => (filters.everyone || event.userId === user.id) && (!filters.channel || event.channel === filters.channel) && (!filters.status || event.status === filters.status) && (!client || event.clientName.toLowerCase().includes(client))).sort((a, b) => b.time.localeCompare(a.time));
  });
}
export function getOrgSettings(actor: User) {
  if (!USE_MOCKS) return live.getOrgSettings();
  return request(() => { member(actor); return { ...db.orgSettings }; });
}
export function updateOrgSettings(changes: Partial<OrgSettings>, actor: User) {
  if (!USE_MOCKS) return live.updateOrgSettings(changes);
  return request(() => {
    const user = member(actor);
    assert(isAdmin(user), 'You don’t have permission to change organization controls.');
    if (changes.maxTokenLifetimeDays !== undefined) {
      assert(isLifetime(changes.maxTokenLifetimeDays), 'Choose a 30, 90, or 365 day lifetime.');
      db.orgSettings.maxTokenLifetimeDays = changes.maxTokenLifetimeDays;
    }
    if (changes.allowExternalAi !== undefined) db.orgSettings.allowExternalAi = changes.allowExternalAi;
    if (changes.allowWriteScopes !== undefined) db.orgSettings.allowWriteScopes = changes.allowWriteScopes;
    return { ...db.orgSettings };
  });
}
export function getConsentRequest(query: ConsentQuery, actor: User, requestId = '') {
  if (!USE_MOCKS || requestId) {
    if (!requestId) return Promise.reject(new Error('This authorization request could not be found.'));
    return live.getConsentRequest(requestId);
  }
  return request(() => {
    const user = member(actor);
    const appName = query.app?.trim() ?? '';
    const redirectUri = query.redirectUri?.trim() ?? '';
    assert(appName && redirectUri, 'This authorization request could not be found.');
    let redirectDomain = '';
    try {
      const url = new URL(redirectUri);
      assert(url.protocol === 'https:', 'This authorization request could not be found.');
      redirectDomain = url.hostname;
    } catch { assert(false, 'This authorization request could not be found.'); }
    const known = knownApps.some(item => item.name.test(appName) && item.domain === redirectDomain);
    const flag = query.verified?.trim().toLowerCase();
    const verified = flag === '1' || flag === 'true' ? true : flag === '0' || flag === 'false' ? false : known;
    return { appName, redirectDomain, verified, writeRequested: (query.scope ?? '').split(/[\s,]+/).includes('docs:write'), allowWrite: db.orgSettings.allowWriteScopes, externalAccess: db.orgSettings.allowExternalAi, userName: user.name };
  });
}
export function submitConsent(input: ConsentDecision, actor: User, requestId = '') {
  if (!USE_MOCKS || requestId) {
    if (!requestId) return Promise.reject(new Error('This authorization request could not be found.'));
    return live.submitConsent(requestId, input);
  }
  return request(() => {
    const user = member(actor);
    assert(input.decision === 'allow' || input.decision === 'deny', 'Choose allow or deny.');
    if (input.decision === 'deny') return { decision: 'deny' as const };
    assert(db.orgSettings.allowExternalAi, 'External AI access is turned off for this workspace.');
    const appName = input.appName.trim();
    const redirectDomain = input.redirectDomain.trim();
    assert(appName && redirectDomain, 'This authorization request could not be found.');
    const scopes = scopesFor(input.scopes.includes('docs:read') ? input.scopes : ['docs:read', ...input.scopes], db.orgSettings);
    const existing = db.grants.find(grant => grant.userId === user.id && grant.appName === appName && grant.redirectDomain === redirectDomain && grant.status === 'active');
    if (existing) { existing.scopes = scopes; return { decision: 'allow' as const, grantId: existing.id }; }
    const grant: OAuthGrant = { id: newId('grant'), userId: user.id, appName, redirectDomain, verified: knownApps.some(item => item.name.test(appName) && item.domain === redirectDomain), scopes, grantedAt: new Date().toISOString(), lastUsedAt: null, status: 'active' };
    db.grants.unshift(grant);
    return { decision: 'allow' as const, grantId: grant.id };
  });
}
export function listDocumentAccess(documentId: string, actor: User) {
  if (!USE_MOCKS) return live.listDocumentAccess(documentId);
  return request(() => {
    const user = activeUser(actor);
    const doc = db.documents.find(item => item.id === documentId);
    assert(doc, 'This document could not be found. It may have been deleted.');
    assert(canView(user, doc), 'You don’t have access to this document.');
    return db.documentAccess.filter(event => event.documentId === documentId).sort((a, b) => b.time.localeCompare(a.time));
  });
}
