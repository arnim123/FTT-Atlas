import { db } from '@/mocks/db';
import type { Role, User } from '@/types';
import { USE_MOCKS, request } from './client';
import * as live from './live';

export function getInitialUser(): User { return structuredClone(db.users[0]); }
export function signIn(input: string = 'success'): Promise<User> {
  if (!USE_MOCKS) return live.signInWithGoogle(input);
  return request(() => {
    if (input === 'domain') throw new Error('This Google account is outside your company domain. Please use your @company.com account.');
    if (input === 'deactivated') throw new Error('Your account has been deactivated. Contact your workspace administrator to restore access.');
    return db.users[0];
  });
}
export function getRoleIdentity(role: Role): Promise<User> {
  if (!USE_MOCKS) return live.getRoleIdentity(role);
  return request(() => {
    const user = db.users.find(u => u.role === role && u.status === 'active');
    if (!user) throw new Error('No active demo account is available for this role.');
    return user;
  });
}
export function getProfile(actor: User) {
  if (!USE_MOCKS) return live.getProfile();
  return request(() => { const user = db.users.find(u => u.id === actor.id); if (!user) throw new Error('Profile not found.'); return user; });
}
export function restoreSession() {
  return USE_MOCKS ? Promise.resolve(getInitialUser()) : live.restoreSession();
}
export function endSession() {
  return USE_MOCKS ? Promise.resolve() : live.endSession();
}
export function loginWithTestEmail(email: string) {
  return live.loginWithTestEmail(email);
}
