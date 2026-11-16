import { db } from '@/mocks/db';
import type { Access, ResourceTarget, User } from '@/types';
import { canManage, canView } from '@/lib/access';
import { USE_MOCKS, activeUser, assert, request } from './client';
import * as live from './live';

function resource(target: ResourceTarget) { const result = target.kind === 'document' ? db.documents.find(d => d.id === target.id) : db.folders.find(f => f.id === target.id); assert(result, 'This item no longer exists.'); return result; }
export function getPermissions(target: ResourceTarget, actor: User) {
  if (!USE_MOCKS) return live.getPermissions(target);
  return request(() => { const item = resource(target); assert(canView(activeUser(actor), item)); return { access: item.access, ownerId: item.ownerId, departmentId: item.departmentId }; });
}
export function updatePermissions(target: ResourceTarget, access: Access, actor: User) {
  if (!USE_MOCKS) return live.updatePermissions(target, access);
  return request(() => { const item = resource(target); assert(canManage(activeUser(actor), item)); assert(access.level !== 'custom' || access.grants.length > 0, 'Add at least one person or department for custom access.'); item.access = { ...access, syncStatus: target.kind === 'document' && 'googleFileId' in item && item.googleFileId ? 'pending' : 'synced' }; return item.access; });
}
export function retryPermissionSync(target: ResourceTarget, actor: User) {
  if (!USE_MOCKS) return live.retryPermissionSync(target);
  return request(() => { const item = resource(target); assert(canManage(activeUser(actor), item)); item.access.syncStatus = 'synced'; return item.access; });
}
