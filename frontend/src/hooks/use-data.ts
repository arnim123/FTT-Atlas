import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth';
import { getReferenceData, listFolderTree } from '@/api';

const scopes = {
  library: ['documents', 'document', 'folders', 'dashboard', 'archive', 'search', 'palette', 'permissions', 'related', 'document-access', 'embed', 'reference', 'google-sharing'],
  users: ['users', 'reference'],
  taxonomy: ['taxonomy', 'reference'],
  integrations: ['integrations', 'consent', 'oauth-consent', 'document-access'],
} as const;

export type RefreshScope = keyof typeof scopes;

export function useReferenceData() { const user = useAuthStore(s => s.user); return useQuery({ queryKey: ['reference', user.id], queryFn: () => getReferenceData(user), staleTime: 60_000, enabled: !!user.id }); }
export function useFolders() { const user = useAuthStore(s => s.user); return useQuery({ queryKey: ['folders', user.id], queryFn: () => listFolderTree(user), enabled: !!user.id }); }
export function useRefresh() {
  const client = useQueryClient();
  return (scope: RefreshScope = 'library') => Promise.all(scopes[scope].map(key => client.invalidateQueries({ queryKey: [key] })));
}
