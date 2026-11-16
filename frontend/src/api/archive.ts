import { db } from '@/mocks/db';
import type { ArchiveItem, User } from '@/types';
import { canManage } from '@/lib/access';
import { USE_MOCKS, activeUser, request } from './client';
import * as live from './live';

export function listArchived(actor: User): Promise<ArchiveItem[]> {
  if (!USE_MOCKS) return live.listArchived();
  return request(() => { const user = activeUser(actor); return [
    ...db.folders.filter(f => f.archived && canManage(user, f)).map(f => ({ kind: 'folder' as const, id: f.id, name: f.name, departmentId: f.departmentId, ownerId: f.ownerId })),
    ...db.documents.filter(d => d.archived && canManage(user, d)).map(d => ({ kind: 'document' as const, id: d.id, name: d.name, departmentId: d.departmentId, ownerId: d.ownerId, type: d.type, modifiedAt: d.modifiedAt })),
  ]; });
}
