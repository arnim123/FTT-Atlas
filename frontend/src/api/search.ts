import type { DocumentFilters, SearchResult, User } from '@/types';
import { USE_MOCKS, request } from './client';
import { filteredDocuments } from './documents';
import * as live from './live';

export function searchDocuments(query: string, filters: DocumentFilters, actor: User): Promise<SearchResult[]> {
  if (!USE_MOCKS) return live.searchDocuments(query, filters);
  return request(() => {
    const normalized = query.trim().toLowerCase();
    const results = filteredDocuments(actor, { ...filters, query }).map(document => {
      const matchedIn: SearchResult['matchedIn'] = [];
      if (normalized && document.name.toLowerCase().includes(normalized)) matchedIn.push('name');
      if (normalized && document.tags.some(t => t.toLowerCase().includes(normalized))) matchedIn.push('tag');
      if (normalized && document.content.toLowerCase().includes(normalized)) matchedIn.push('content');
      const index = document.content.toLowerCase().indexOf(normalized);
      const start = Math.max(0, index - 40);
      const snippet = normalized ? `${start > 0 ? '…' : ''}${document.content.slice(start, start + 200).replace(/\n/g, ' ')}…` : document.description;
      return { document, matchedIn, snippet, score: (matchedIn.includes('name') ? 10 : 0) + (matchedIn.includes('tag') ? 5 : 0) + (matchedIn.includes('content') ? 1 : 0) };
    });
    return !filters.sort || filters.sort === 'relevance' ? results.sort((a, b) => b.score - a.score) : results;
  });
}
