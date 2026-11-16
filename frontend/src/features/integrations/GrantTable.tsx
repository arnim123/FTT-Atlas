import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import type { OAuthGrant } from '@/types';
import { listGrants, revokeGrant } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useRefresh } from '@/hooks/use-data';
import { errorMessage, formatDate } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { EmptyState, ErrorState, Skeleton } from '@/components/shared/States';
import { ConfirmDialog, scopeSummary, StatusBadge } from './shared';
import { integrationQuery } from './query';

export function GrantTable() {
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const [revoke, setRevoke] = useState<OAuthGrant | null>(null);
  const grants = useQuery({ queryKey: integrationQuery.grants(user.id), queryFn: () => listGrants(user) });
  const mutation = useMutation({ mutationFn: (id: string) => revokeGrant(id, user), onSuccess: () => { setRevoke(null); void refresh('integrations'); toast.success('App disconnected'); }, onError: error => toast.error(errorMessage(error)) });
  if (grants.error) return <ErrorState error={grants.error} retry={() => void grants.refetch()} />;
  if (grants.isPending || !grants.data) return <div className="space-y-3" role="status" aria-label="Loading connected apps"><Skeleton className="h-12" /><Skeleton className="h-12" /></div>;
  if (!grants.data.length) return <div className="panel"><EmptyState title="No connected apps yet" description="When you allow an OAuth connector, it will show up here." /></div>;
  return <div className="panel overflow-hidden">
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left">
        <thead className="table-head"><tr>{['App', 'Redirect domain', 'Scopes', 'Granted on', 'Last used', 'Status', ''].map((label, index) => <th key={index} className="px-4 py-3 font-medium">{label || <span className="sr-only">Actions</span>}</th>)}</tr></thead>
        <tbody>{grants.data.map(grant => <tr key={grant.id} className="border-t">
          <td className="px-4 py-3.5 text-xs font-medium">{grant.appName}{grant.verified && <span className="ml-2 text-[9px] font-normal text-primary">Verified</span>}</td>
          <td className="px-4 py-3.5 font-mono text-[10px] text-muted-foreground">{grant.redirectDomain}</td>
          <td className="px-4 py-3.5 text-[10px]">{scopeSummary(grant.scopes)}</td>
          <td className="px-4 py-3.5 text-[10px] text-muted-foreground">{formatDate(grant.grantedAt)}</td>
          <td className="px-4 py-3.5 text-[10px] text-muted-foreground">{grant.lastUsedAt ? formatDate(grant.lastUsedAt) : 'Never'}</td>
          <td className="px-4 py-3.5"><StatusBadge status={grant.status} /></td>
          <td className="px-4 py-3.5 text-right">{grant.status === 'active' && <Button size="sm" variant="outline" onClick={() => setRevoke(grant)}>Revoke</Button>}</td>
        </tr>)}</tbody>
      </table>
    </div>
    {revoke && <ConfirmDialog title={`Disconnect ${revoke.appName}?`} description={`${revoke.appName} will lose access to Company Knowledge until you allow it again.`} confirmLabel="Revoke access" destructive pending={mutation.isPending} onClose={() => !mutation.isPending && setRevoke(null)} onConfirm={() => mutation.mutate(revoke.id)} />}
  </div>;
}
