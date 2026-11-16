import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import type { ReactNode } from 'react';
import type { OrgSettings, TokenLifetime } from '@/types';
import { getOrgSettings, listAuditLog, listGrants, listTokens, revokeGrant, revokeToken, updateOrgSettings } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useReferenceData, useRefresh } from '@/hooks/use-data';
import { errorMessage, formatDate } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ErrorState, Skeleton } from '@/components/shared/States';
import { ConfirmDialog, scopeSummary, StatusBadge, Toggle } from './shared';
import { integrationQuery } from './query';

export function OrgControls() {
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const reference = useReferenceData();
  const [confirmOff, setConfirmOff] = useState(false);
  const [revoke, setRevoke] = useState<{ kind: 'token' | 'grant'; id: string; label: string } | null>(null);
  const settings = useQuery({ queryKey: integrationQuery.settings(user.id), queryFn: () => getOrgSettings(user) });
  const tokens = useQuery({ queryKey: integrationQuery.tokens(user.id, true), queryFn: () => listTokens(user, { everyone: true }) });
  const grants = useQuery({ queryKey: integrationQuery.grants(user.id, true), queryFn: () => listGrants(user, { everyone: true }) });
  const audit = useQuery({ queryKey: integrationQuery.audit(user.id, { everyone: true, channel: '', status: '', client: '' }), queryFn: () => listAuditLog(user, { everyone: true }) });
  const save = useMutation({ mutationFn: (changes: Partial<OrgSettings>) => updateOrgSettings(changes, user), onSuccess: () => { setConfirmOff(false); void refresh('integrations'); toast.success('Organization controls updated'); }, onError: error => toast.error(errorMessage(error)) });
  const remove = useMutation({
    mutationFn: async (target: NonNullable<typeof revoke>) => { if (target.kind === 'token') await revokeToken(target.id, user); else await revokeGrant(target.id, user); },
    onSuccess: () => { setRevoke(null); void refresh('integrations'); toast.success('Access revoked'); },
    onError: error => toast.error(errorMessage(error)),
  });
  const nameOf = (id: string) => reference.data?.users.find(person => person.id === id)?.name ?? 'Unknown user';
  if (settings.error) return <ErrorState error={settings.error} retry={() => void settings.refetch()} />;
  if (settings.isPending || !settings.data) return <div className="space-y-3" role="status" aria-label="Loading organization controls"><Skeleton className="h-24" /><Skeleton className="h-40" /></div>;
  const usage = Object.values((audit.data ?? []).reduce<Record<string, { clientName: string; calls: number }>>((map, row) => {
    map[row.clientName] = map[row.clientName] ?? { clientName: row.clientName, calls: 0 };
    map[row.clientName].calls += 1;
    return map;
  }, {})).sort((a, b) => b.calls - a.calls);
  const maxCalls = Math.max(...usage.map(item => item.calls), 1);
  return <div className="space-y-5">
    <section className="panel space-y-5 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xs font-semibold">Allow external AI access</h2>
          <p className="mt-1 max-w-xl text-[11px] leading-relaxed text-muted-foreground">Master switch for every token and OAuth grant. Turning this off stops external apps from reading or changing company documents.</p>
        </div>
        <Toggle checked={settings.data.allowExternalAi} disabled={save.isPending} label="Allow external AI access" onChange={next => next ? save.mutate({ allowExternalAi: true }) : setConfirmOff(true)} />
      </div>
      <div className="flex items-start justify-between gap-4 border-t pt-5">
        <div>
          <h2 className="text-xs font-semibold">Allow write scopes</h2>
          <p className="mt-1 max-w-xl text-[11px] leading-relaxed text-muted-foreground">When this is off, new tokens and consent grants cannot include docs:write. Existing write tokens stay until you revoke them.</p>
        </div>
        <Toggle checked={settings.data.allowWriteScopes} disabled={save.isPending} label="Allow write scopes" onChange={next => save.mutate({ allowWriteScopes: next })} />
      </div>
      <div className="border-t pt-5">
        <label htmlFor="token-lifetime" className="field-label">Max token lifetime</label>
        <select id="token-lifetime" className="select-input max-w-xs" disabled={save.isPending} value={settings.data.maxTokenLifetimeDays} onChange={event => save.mutate({ maxTokenLifetimeDays: Number(event.target.value) as TokenLifetime })}>
          <option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>365 days</option>
        </select>
      </div>
    </section>
    <section className="panel p-5">
      <h2 className="text-xs font-semibold">Usage by client</h2>
      <p className="mt-1 text-[10px] text-muted-foreground">External calls recorded for this workspace.</p>
      {audit.error ? <ErrorState error={audit.error} retry={() => void audit.refetch()} /> : audit.isPending ? <Skeleton className="mt-4 h-24" /> : <div className="mt-4 space-y-3" role="img" aria-label={usage.map(item => `${item.clientName}: ${item.calls} calls`).join(', ')}>
        {usage.map(item => <div key={item.clientName}>
          <div className="mb-1 flex justify-between text-[10px]"><span>{item.clientName}</span><span className="text-muted-foreground">{item.calls}</span></div>
          <div className="h-1.5 rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${(item.calls / maxCalls) * 100}%` }} /></div>
        </div>)}
      </div>}
    </section>
    <Inventory title="All tokens" error={tokens.error} pending={tokens.isPending || !tokens.data} retry={() => void tokens.refetch()} count={tokens.data?.length ?? 0} empty="No tokens have been created.">
      <table className="w-full min-w-[760px] text-left">
        <thead className="table-head"><tr>{['User', 'Name', 'Token', 'Scopes', 'Last used', 'Status', ''].map((label, index) => <th key={index} className="px-4 py-3 font-medium">{label || <span className="sr-only">Actions</span>}</th>)}</tr></thead>
        <tbody>{tokens.data?.map(token => <tr key={token.id} className="border-t">
          <td className="px-4 py-3 text-[11px]">{nameOf(token.userId)}</td>
          <td className="px-4 py-3 text-xs font-medium">{token.name}</td>
          <td className="px-4 py-3 font-mono text-[10px] text-muted-foreground">{token.prefix}…</td>
          <td className="px-4 py-3 text-[10px]">{scopeSummary(token.scopes)}</td>
          <td className="px-4 py-3 text-[10px] text-muted-foreground">{token.lastUsedAt ? formatDate(token.lastUsedAt) : 'Never'}</td>
          <td className="px-4 py-3"><StatusBadge status={token.status} /></td>
          <td className="px-4 py-3 text-right">{token.status !== 'revoked' && <Button size="sm" variant="outline" onClick={() => setRevoke({ kind: 'token', id: token.id, label: `${token.name} for ${nameOf(token.userId)}` })}>Revoke</Button>}</td>
        </tr>)}</tbody>
      </table>
    </Inventory>
    <Inventory title="All OAuth grants" error={grants.error} pending={grants.isPending || !grants.data} retry={() => void grants.refetch()} count={grants.data?.length ?? 0} empty="No apps have been connected.">
      <table className="w-full min-w-[720px] text-left">
        <thead className="table-head"><tr>{['User', 'App', 'Redirect domain', 'Scopes', 'Last used', 'Status', ''].map((label, index) => <th key={index} className="px-4 py-3 font-medium">{label || <span className="sr-only">Actions</span>}</th>)}</tr></thead>
        <tbody>{grants.data?.map(grant => <tr key={grant.id} className="border-t">
          <td className="px-4 py-3 text-[11px]">{nameOf(grant.userId)}</td>
          <td className="px-4 py-3 text-xs font-medium">{grant.appName}</td>
          <td className="px-4 py-3 font-mono text-[10px] text-muted-foreground">{grant.redirectDomain}</td>
          <td className="px-4 py-3 text-[10px]">{scopeSummary(grant.scopes)}</td>
          <td className="px-4 py-3 text-[10px] text-muted-foreground">{grant.lastUsedAt ? formatDate(grant.lastUsedAt) : 'Never'}</td>
          <td className="px-4 py-3"><StatusBadge status={grant.status} /></td>
          <td className="px-4 py-3 text-right">{grant.status === 'active' && <Button size="sm" variant="outline" onClick={() => setRevoke({ kind: 'grant', id: grant.id, label: `${grant.appName} for ${nameOf(grant.userId)}` })}>Revoke</Button>}</td>
        </tr>)}</tbody>
      </table>
    </Inventory>
    {confirmOff && <ConfirmDialog title="Turn off external AI access?" description="Connected apps and tokens will stop being able to read or change company documents until you turn this back on." confirmLabel="Turn off access" destructive pending={save.isPending} onClose={() => setConfirmOff(false)} onConfirm={() => save.mutate({ allowExternalAi: false })} />}
    {revoke && <ConfirmDialog title="Revoke this access?" description={revoke.label} confirmLabel="Revoke" destructive pending={remove.isPending} onClose={() => setRevoke(null)} onConfirm={() => remove.mutate(revoke)} />}
  </div>;
}
function Inventory({ title, error, pending, retry, count, empty, children }: {
  title: string; error: unknown; pending: boolean; retry: () => void; count: number; empty: string; children: ReactNode;
}) {
  return <section className="panel overflow-hidden">
    <h2 className="border-b px-4 py-3 text-xs font-semibold">{title}</h2>
    {error ? <div className="px-4"><ErrorState error={error} retry={retry} /></div> : pending ? <div className="space-y-3 p-4" role="status" aria-label={`Loading ${title}`}><Skeleton className="h-10" /><Skeleton className="h-10" /></div> : count === 0 ? <p className="px-4 py-8 text-center text-[11px] text-muted-foreground">{empty}</p> : <div className="overflow-x-auto">{children}</div>}
  </section>;
}
