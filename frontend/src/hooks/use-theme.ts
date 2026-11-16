import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useTheme = create<{ theme: 'light' | 'dark'; toggle: () => void }>()(persist((set) => ({ theme: 'light', toggle: () => set(state => ({ theme: state.theme === 'light' ? 'dark' : 'light' })) }), { name: 'atlas-theme' }));
