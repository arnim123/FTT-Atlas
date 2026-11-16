import { useState } from 'react';

export function useRecentSearches() {
  const [recent, setRecent] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem('atlas-recent-searches') ?? '[]') as string[]; } catch { return []; } });
  function remember(value: string) { const query = value.trim(); if (!query) return; setRecent(previous => { const next = [query, ...previous.filter(p => p.toLowerCase() !== query.toLowerCase())].slice(0, 6); localStorage.setItem('atlas-recent-searches', JSON.stringify(next)); return next; }); }
  function clear() { setRecent([]); localStorage.removeItem('atlas-recent-searches'); }
  return { recent, remember, clear };
}
