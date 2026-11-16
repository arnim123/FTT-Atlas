import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { toast } from 'sonner';
import type { AccessToken } from '@/types';
import { getOrgSettings, listTokens, revokeToken } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useRefresh } from '@/hooks/use-data';
import { errorMessage, formatDate } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { EmptyState, ErrorState, Skeleton } from '@/components/shared/States';
import { ConfirmDialog, scopeSummary, StatusBadge } from './shared';
import { CreateTokenDialog } from './CreateTokenDialog';
import { integrationQuery } from './query';

export function TokenTable() {
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const [creating, setCreating] = useState(false);
  const [revoke, setRevoke] = useState<AccessToken | null>(null);
  const settings = useQuery({ queryKey: integrationQuery.settings(user.id), queryFn: () => getOrgSettings(user) });
  const tokens = useQuery({ queryKey: integrationQuery.tokens(user.id), queryFn: () => listTokens(user) });
  const mutation = useMutation({ mutationFn: (id: string) => revokeToken(id, user), onSuccess: () => { setRevoke(null); void refresh('integrations'); toast.success('Token revoked'); }, onError: error => toast.error(errorMessage(error)) });
  if (tokens.error || settings.error) return <ErrorState error={tokens.error ?? settings.error} retry={() => { void tokens.refetch(); void settings.refetch(); }} />;
  if (tokens.isPending || settings.isPending || !tokens.data || !settings.data) return <div className="space-y-3" role="status" aria-label="Loading tokens"><Skeleton className="h-12" /><Skeleton className="h-12" /><Skeleton className="h-12" /></div>;
  return <div className="panel overflow-hidden">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
      <div>
        <h2 className="text-xs font-semibold">Tokens on your account</h2>
        <p className="mt-1 text-[10px] text-muted-foreground">{settings.data.allowExternalAi ? 'Read-only is the default. Write access is a separate choice.' : 'External AI access is off, so new tokens are paused.'}</p>
      </div>
      <Button onClick={() => setCreating(true)} disabled={!settings.data.allowExternalAi}><Plus />Create token</Button>
    </div>
    {!tokens.data.length ? <EmptyState title="No access tokens yet" description="Create a token when an app asks you to paste one." action={<Button onClick={() => setCreating(true)} disabled={!settings.data.allowExternalAi}>Create token</Button>} /> : <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left">
        <thead className="table-head"><tr>{['Name', 'Token', 'Scopes', 'Created', 'Last used', 'Expires', 'Status', ''].map((label, index) => <th key={index} className="px-4 py-3 font-medium">{label || <span className="sr-only">Actions</span>}</th>)}</tr></thead>
        <tbody>{tokens.data.map(token => <tr key={token.id} className="border-t">
          <td className="px-4 py-3.5 text-xs font-medium">{token.name}</td>
          <td className="px-4 py-3.5 font-mono text-[10px] text-muted-foreground">{token.prefix}…</td>
          <td className="px-4 py-3.5 text-[10px]">{scopeSummary(token.scopes)}</td>
          <td className="px-4 py-3.5 text-[10px] text-muted-foreground">{formatDate(token.createdAt)}</td>
          <td className="px-4 py-3.5 text-[10px] text-muted-foreground">{token.lastUsedAt ? formatDate(token.lastUsedAt) : 'Never'}</td>
          <td className="px-4 py-3.5 text-[10px] text-muted-foreground">{formatDate(token.expiresAt)}</td>
          <td className="px-4 py-3.5"><StatusBadge status={token.status} /></td>
          <td className="px-4 py-3.5 text-right">{token.status !== 'revoked' && <Button size="sm" variant="outline" onClick={() => setRevoke(token)}>Revoke</Button>}</td>
        </tr>)}</tbody>
      </table>
    </div>}
    {creating && <CreateTokenDialog settings={settings.data} close={() => setCreating(false)} />}
    {revoke && <ConfirmDialog title={`Revoke ${revoke.name}?`} description="Apps using this token lose access immediately. This cannot be undone." confirmLabel="Revoke token" destructive pending={mutation.isPending} onClose={() => !mutation.isPending && setRevoke(null)} onConfirm={() => mutation.mutate(revoke.id)} />}
  </div>;
}
