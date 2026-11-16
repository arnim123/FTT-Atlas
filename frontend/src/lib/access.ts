import type { Access, Document, Folder, MyAccess, User } from '@/types';

type Resource = Pick<Document | Folder, 'ownerId' | 'departmentId' | 'access'> & { myAccess?: MyAccess };
export const isAdmin = (user: User) => user.role === 'admin' || user.role === 'super_admin';
export const canManageUsers = (user: User) => isAdmin(user) || user.role === 'manager';
export const canCreate = (user: User) => user.role !== 'guest';
export const canUseIntegrations = (user: User) => user.role !== 'guest';
function grantFor(user: User, access: Access) {
  return access.grants.filter(g => (g.principalType === 'user' && g.principalId === user.id) || (g.principalType === 'department' && g.principalId === user.departmentId && user.role !== 'guest'));
}
export function canView(user: User, resource: Resource): boolean {
  if (resource.myAccess) return user.status === 'active' && resource.myAccess !== 'none';
  if (user.status !== 'active') return false;
  if (isAdmin(user) || resource.ownerId === user.id) return true;
  if (user.role === 'guest') return resource.access.level === 'custom' && grantFor(user, resource.access).length > 0;
  if (resource.access.level === 'organization') return true;
  if (resource.access.level === 'department') return resource.departmentId === user.departmentId;
  if (resource.access.level === 'custom') return grantFor(user, resource.access).length > 0;
  return false;
}
export function canEdit(user: User, resource: Resource): boolean {
  if (resource.myAccess) return user.status === 'active' && (resource.myAccess === 'edit' || resource.myAccess === 'manage');
  if (!canView(user, resource)) return false;
  if (isAdmin(user) || resource.ownerId === user.id) return true;
  if (user.role === 'manager' && resource.departmentId === user.departmentId) return true;
  if (resource.access.level === 'custom') return grantFor(user, resource.access).some(g => g.permission === 'edit');
  return resource.access.defaultPermission === 'edit';
}
export function canManage(user: User, resource: Resource): boolean {
  if (resource.myAccess) return user.status === 'active' && resource.myAccess === 'manage';
  return isAdmin(user) || resource.ownerId === user.id || (user.role === 'manager' && resource.departmentId === user.departmentId && canView(user, resource));
}
