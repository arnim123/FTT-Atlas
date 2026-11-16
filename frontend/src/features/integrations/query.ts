import type { AuditFilters } from '@/types';

export const mineAudit: AuditFilters = { everyone: false, channel: '', status: '', client: '' };

export const integrationQuery = {
  settings: (userId: string) => ['integrations', 'settings', userId] as const,
  tokens: (userId: string, everyone = false) => ['integrations', 'tokens', userId, everyone] as const,
  grants: (userId: string, everyone = false) => ['integrations', 'grants', userId, everyone] as const,
  audit: (userId: string, filters: AuditFilters) => ['integrations', 'audit', userId, filters] as const,
  access: (documentId: string, userId: string) => ['document-access', documentId, userId] as const,
  consent: (userId: string, app: string, redirectUri: string, verified: string, scope: string) => ['consent', userId, app, redirectUri, verified, scope] as const,
};
