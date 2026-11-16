import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { AuditFilters, AuditStatus, AuditChannel } from '@/types';
import { listAuditLog } from '@/api';
import { useAuthStore } from '@/store/auth';
import { isAdmin } from '@/lib/access';
import { cn, formatDateTime } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EmptyState, ErrorState, Skeleton } from '@/components/shared/States';
import { ChannelBadge, StatusBadge } from './shared';
import { integrationQuery, mineAudit } from './query';

export function ActivityLog() {
  const user = useAuthStore(s => s.user);
  const admin = isAdmin(user);
  const [filters, setFilters] = useState<AuditFilters>({ ...mineAudit });
  const audit = useQuery({ queryKey: integrationQuery.audit(user.id, filters), queryFn: () => listAuditLog(user, filters) });
  const update = (patch: Partial<AuditFilters>) => setFilters(current => ({ ...current, ...patch }));
  return <div className="panel overflow-hidden">
    <div className="flex flex-wrap items-center gap-3 border-b p-4">
      {admin && <div className="inline-flex rounded-md border p-0.5" role="group" aria-label="Activity scope">
        {([[false, 'Mine'], [true, 'Everyone']] as const).map(([everyone, label]) => <button key={label} type="button" aria-pressed={Boolean(filters.everyone) === everyone} onClick={() => update({ everyone })} className={cn('rounded px-2.5 py-1.5 text-[10px] font-medium', Boolean(filters.everyone) === everyone ? 'bg-accent text-primary' : 'text-muted-foreground')}>{label}</button>)}
      </div>}
      <select className="select-input w-32" aria-label="Filter by channel" value={filters.channel ?? ''} onChange={event => update({ channel: event.target.value as AuditChannel | '' })}>
        <option value="">All channels</option><option value="REST">REST</option><option value="MCP">MCP</option>
      </select>
      <select className="select-input w-32" aria-label="Filter by status" value={filters.status ?? ''} onChange={event => update({ status: event.target.value as AuditStatus | '' })}>
        <option value="">All statuses</option><option value="ok">Success</option><option value="error">Error</option><option value="denied">Denied</option>
      </select>
      <Input className="w-44" aria-label="Filter by client" placeholder="Filter by client" value={filters.client ?? ''} onChange={event => update({ client: event.target.value })} />
      {!admin && <p className="text-[10px] text-muted-foreground">Showing calls made with your account.</p>}
    </div>
    {audit.error ? <div className="px-5"><ErrorState error={audit.error} retry={() => void audit.refetch()} /></div> : audit.isPending || !audit.data ? <div className="space-y-3 p-5" role="status" aria-label="Loading activity"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div> : !audit.data.length ? <EmptyState search title="No external calls match these filters" description={filters.everyone ? 'Nothing in the workspace matches. Try another client or channel.' : 'Nothing on your account matches. Try another client or channel.'} action={<Button variant="outline" onClick={() => setFilters({ ...mineAudit, everyone: filters.everyone })}>Clear filters</Button>} /> : <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left">
        <thead className="table-head"><tr>{['Time', 'Channel', 'Client', 'Tool or endpoint', 'Status', 'Duration'].map(label => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead>
        <tbody>{audit.data.map(row => <tr key={row.id} className="border-t">
          <td className="px-4 py-3 text-[10px] text-muted-foreground">{formatDateTime(row.time)}</td>
          <td className="px-4 py-3"><ChannelBadge channel={row.channel} /></td>
          <td className="px-4 py-3 text-[11px]">{row.clientName}</td>
          <td className="px-4 py-3 font-mono text-[10px] text-muted-foreground">{row.toolOrEndpoint}</td>
          <td className="px-4 py-3"><StatusBadge status={row.status} /></td>
          <td className="px-4 py-3 text-[10px] text-muted-foreground">{row.durationMs < 1000 ? `${row.durationMs} ms` : `${(row.durationMs / 1000).toFixed(1)} s`}</td>
        </tr>)}</tbody>
      </table>
      <p className="border-t px-4 py-3 text-[10px] text-muted-foreground">{audit.data.length} calls · {filters.everyone ? 'Everyone in the workspace' : 'Your account'}</p>
    </div>}
  </div>;
}
