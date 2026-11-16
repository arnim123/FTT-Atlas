import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types';
import { USE_MOCKS, getInitialUser } from '@/api';

const blank: User = { id: '', name: '', email: '', role: 'employee', departmentId: '', status: 'active', color: 'sage', lastActive: '' };

interface AuthState {
  user: User;
  authenticated: boolean;
  ready: boolean;
  signIn: (user: User) => void;
  signOut: () => void;
  setUser: (user: User) => void;
  markReady: () => void;
}

const actions = (set: (partial: Partial<AuthState>) => void): AuthState => ({
  user: USE_MOCKS ? getInitialUser() : blank,
  authenticated: USE_MOCKS,
  ready: USE_MOCKS,
  signIn: user => set({ user, authenticated: true, ready: true }),
  signOut: () => set({ user: blank, authenticated: false, ready: true }),
  setUser: user => set({ user, authenticated: true, ready: true }),
  markReady: () => set({ ready: true }),
});

export const useAuthStore = USE_MOCKS
  ? create<AuthState>()(persist(actions, { name: 'atlas-session', version: 2, partialize: state => ({ user: state.user, authenticated: state.authenticated }) }))
  : create<AuthState>()(actions);
