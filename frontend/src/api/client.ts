import type { User } from '@/types';
import { db } from '@/mocks/db';

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false';
let nextError = false;
export function simulateNextError() { nextError = true; }
export async function request<T>(operation: () => T | Promise<T>): Promise<T> {
  await new Promise(resolve => setTimeout(resolve, import.meta.env.MODE === 'test' ? 0 : 300));
  if (!USE_MOCKS) throw new Error('The HTTP adapter is not configured. Set VITE_USE_MOCKS=true to use this demo.');
  if (nextError) { nextError = false; throw new Error('We couldn’t connect to the workspace. Please try again.'); }
  return structuredClone(await operation());
}
export function activeUser(actor: User): User {
  const user = db.users.find(u => u.id === actor.id);
  if (!user || user.status !== 'active') throw new Error('Your account is inactive. Contact your workspace administrator.');
  return user;
}
export function assert(condition: unknown, message = 'You don’t have permission to make this change.'): asserts condition {
  if (!condition) throw new Error(message);
}
export function newId(prefix: string) { return `${prefix}-${crypto.randomUUID()}`; }
