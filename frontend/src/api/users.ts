import { db } from '@/mocks/db';
import type { Role, User, UserStatus } from '@/types';
import { canManageUsers, isAdmin } from '@/lib/access';
import { USE_MOCKS, activeUser, assert, newId, request } from './client';
import * as live from './live';

export function listUsers(actor: User, filters: { query?: string; role?: string; departmentId?: string; status?: string } = {}) {
  if (!USE_MOCKS) return live.listUsers(filters);
  return request(() => { const user = activeUser(actor); assert(canManageUsers(user)); return db.users.filter(u => (isAdmin(user) || u.departmentId === user.departmentId) && (!filters.query || `${u.name} ${u.email}`.toLowerCase().includes(filters.query.toLowerCase())) && (!filters.role || u.role === filters.role) && (!filters.departmentId || u.departmentId === filters.departmentId) && (!filters.status || u.status === filters.status)); });
}
export function inviteUser(input: { email: string; role: Role; departmentId: string; accountType?: 'person' | 'bot' }, actor: User) {
  if (!USE_MOCKS) return live.inviteUser(input);
  return request(() => {
    const user = activeUser(actor); assert(canManageUsers(user));
    assert(input.accountType !== 'bot' || input.role !== 'guest', 'Service users need an internal role.');
    assert(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.email), 'Enter a valid email address.');
    assert(input.role === 'guest' || input.email.toLowerCase().endsWith('@company.com'), 'Internal roles require a @company.com email address.');
    assert(db.departments.some(d => d.id === input.departmentId), 'Select a valid department.');
    assert(!db.users.some(u => u.email.toLowerCase() === input.email.toLowerCase()), 'A user with this email already exists.');
    assert(user.role !== 'manager' || (input.role === 'employee' && input.departmentId === user.departmentId), 'Managers can invite employees to their own department.');
    assert(user.role === 'super_admin' || !['super_admin', 'admin'].includes(input.role), 'Only a Super Admin can assign administrator roles.');
    const invited: User = { id: newId('user'), name: input.email.split('@')[0].replace(/[._]/g, ' '), email: input.email.toLowerCase(), role: input.role, departmentId: input.departmentId, status: input.accountType === 'bot' ? 'active' : 'invited', color: 'sage', lastActive: new Date().toISOString(), ...(input.accountType === 'bot' ? { accountType: 'bot' as const } : {}) };
    db.users.push(invited); return invited;
  });
}
export function updateUser(id: string, changes: { role?: Role; departmentId?: string; status?: UserStatus }, actor: User) {
  if (!USE_MOCKS) return live.updateUser(id, changes);
  return request(() => {
    const user = activeUser(actor); const target = db.users.find(u => u.id === id); assert(target, 'User not found.'); assert(canManageUsers(user));
    assert(user.id !== id, 'You cannot change your own role or account status.');
    assert(user.role !== 'manager' || (target.departmentId === user.departmentId && target.role === 'employee' && (!changes.departmentId || changes.departmentId === user.departmentId) && (!changes.role || changes.role === 'employee')), 'Managers can manage employees in their own department only.');
    assert(user.role === 'super_admin' || (target.role !== 'super_admin' && target.role !== 'admin' && (!changes.role || !['super_admin', 'admin'].includes(changes.role))), 'Only a Super Admin can manage administrator accounts.');
    if (changes.departmentId) assert(db.departments.some(d => d.id === changes.departmentId), 'Select a valid department.');
    if (changes.role && changes.role !== 'guest') assert(target.email.endsWith('@company.com'), 'Internal roles require a @company.com email address.');
    Object.assign(target, changes); return target;
  });
}
