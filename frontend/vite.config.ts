import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let dndAlias = {};
try { require.resolve('@dnd-kit/core'); } catch { dndAlias = { '@dnd-kit/core': fileURLToPath(new URL('./src/lib/dnd-fallback.tsx', import.meta.url)) }; }

const apiTarget = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/oauth': { target: apiTarget, changeOrigin: true },
      '/.well-known': { target: apiTarget, changeOrigin: true },
      '/mcp': { target: apiTarget, changeOrigin: true },
    },
  },
  preview: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/oauth': { target: apiTarget, changeOrigin: true },
      '/.well-known': { target: apiTarget, changeOrigin: true },
      '/mcp': { target: apiTarget, changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          core: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query', 'zustand'],
          charts: ['recharts'],
          forms: ['react-hook-form', '@hookform/resolvers', 'zod'],
        },
      },
    },
  },
  resolve: { alias: { ...dndAlias, '@': fileURLToPath(new URL('./src', import.meta.url)) } },
});
