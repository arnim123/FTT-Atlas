import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Loader2, ShieldCheck } from 'lucide-react';
import type { TokenScope } from '@/types';
import { getConsentRequest, submitConsent } from '@/api';
import { useAuthStore } from '@/store/auth';
import { canUseIntegrations } from '@/lib/access';
import { cn, errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Brand } from '@/components/layout/Brand';
import { AccessDenied, EmptyState, ErrorState, Skeleton } from '@/components/shared/States';
import { integrationQuery } from '@/features/integrations/query';

export function OAuthConsentPage() {
  const user = useAuthStore(s => s.user);
  const [params] = useSearchParams();
  const [write, setWrite] = useState(false);
  const requestId = params.get('request') ?? '';
  const query = { app: params.get('app') ?? '', redirectUri: params.get('redirect_uri') ?? '', verified: params.get('verified') ?? '', scope: params.get('scope') ?? '' };
  const live = requestId.length > 0;
  const consent = useQuery({ queryKey: live ? ['oauth-consent', requestId] : integrationQuery.consent(user.id, query.app, query.redirectUri, query.verified, query.scope), queryFn: () => getConsentRequest(query, user, requestId), enabled: live || canUseIntegrations(user) });
  const decision = useMutation<{ decision: 'allow' | 'deny'; grantId?: string; redirectTo?: string }, Error, 'allow' | 'deny'>({ mutationFn: (choice: 'allow' | 'deny') => {
    const scopes = (write ? ['docs:read', 'docs:write'] : ['docs:read']) as TokenScope[];
    return submitConsent({ decision: choice, appName: consent.data?.appName ?? query.app, redirectDomain: consent.data?.redirectDomain ?? '', scopes }, user, requestId);
  }, onSuccess: result => { if (result.redirectTo) window.location.assign(result.redirectTo); } });
  useEffect(() => { document.title = 'Atlas · Authorize access'; }, []);
  const person = consent.data?.userName || user.name;
  return <div className="flex min-h-screen flex-col bg-background">
    <header className="flex h-16 items-center px-6"><Brand /></header>
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center px-5 py-10">
      {!live && !canUseIntegrations(user) ? <AccessDenied /> : consent.isPending ? <div className="space-y-3" role="status" aria-label="Loading authorization request"><Skeleton className="h-8" /><Skeleton className="h-48" /></div> : consent.error || !consent.data ? (errorMessage(consent.error).includes('could not be found') ? <EmptyState title="This request is not available" description={errorMessage(consent.error)} /> : <ErrorState error={consent.error ?? 'This authorization request could not be found.'} retry={() => void consent.refetch()} />) : decision.data ? <section className="panel p-6">
        <ShieldCheck className="mb-4 text-primary" />
        <h1 className="text-xl font-semibold tracking-tight">{decision.data.decision === 'allow' ? `You allowed ${consent.data.appName}` : `You denied ${consent.data.appName}`}</h1>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{decision.data.decision === 'allow' ? (live ? `Sending you back to ${consent.data.redirectDomain}.` : `Access was granted for ${consent.data.redirectDomain}. You can revoke it anytime from Connected apps. This demo does not send your browser there.`) : 'No access was granted.'}</p>
        {!live && <Button asChild className="mt-6"><Link to={decision.data.decision === 'allow' ? '/integrations?tab=apps' : '/integrations'}>{decision.data.decision === 'allow' ? 'Review connected apps' : 'Back to integrations'}</Link></Button>}
      </section> : <section className="panel p-6">
        <p className="eyebrow mb-3">Authorization</p>
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.6px]">{`${consent.data.appName} wants to access Company Knowledge as ${person}`}</h1>
        <div className="mt-5 flex items-center justify-between gap-3 rounded-md border bg-muted/30 px-3 py-3">
          <div>
            <p className="text-[10px] text-muted-foreground">Redirect domain</p>
            <p className="mt-1 font-mono text-xs">{consent.data.redirectDomain}</p>
          </div>
          <span className={cn('rounded-full border px-2 py-0.5 text-[10px] font-medium', consent.data.verified ? 'border-primary/20 bg-accent text-primary' : 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-300')}>{consent.data.verified ? 'Verified' : 'Unverified'}</span>
        </div>
        {!consent.data.externalAccess && <p className="mt-4 rounded-md bg-amber-500/10 p-3 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300" role="alert">External AI access is turned off for this workspace. You can deny this request, but you cannot allow it.</p>}
        <div className="mt-5 space-y-2">
          <label className="flex items-start gap-3 rounded-md border p-3">
            <Checkbox checked disabled aria-label="Read documents" className="mt-0.5" />
            <span>
              <span className="block text-xs font-medium">Read documents</span>
              <span className="mt-1 block text-[10px] leading-relaxed text-muted-foreground">docs:read is required. The app can only read documents you can already open.</span>
            </span>
          </label>
          <label className="flex items-start gap-3 rounded-md border p-3">
            <Checkbox checked={write} disabled={!consent.data.allowWrite || !consent.data.externalAccess} onCheckedChange={checked => setWrite(checked === true)} aria-label="Change documents" className="mt-0.5" />
            <span>
              <span className="block text-xs font-medium">Change documents</span>
              <span className="mt-1 block text-[10px] leading-relaxed text-muted-foreground">docs:write lets this app edit documents you can edit.</span>
            </span>
          </label>
        </div>
        {write && <p className="mt-3 rounded-md bg-amber-500/10 p-3 text-[10px] leading-relaxed text-amber-800 dark:text-amber-300">Write access can change company documents. Leave this off unless you mean to allow edits.</p>}
        {consent.data.writeRequested && !write && <p className="mt-3 text-[10px] leading-relaxed text-muted-foreground">This app asked for write access. It stays off until you check it.</p>}
        {!consent.data.allowWrite && <p className="mt-3 text-[10px] text-muted-foreground">Your organization does not allow write scopes.</p>}
        {decision.error && <p className="mt-3 text-[11px] text-destructive" role="alert">{errorMessage(decision.error)}</p>}
        <div className="mt-6 flex gap-2">
          <Button className="flex-1" disabled={!consent.data.externalAccess || decision.isPending} onClick={() => decision.mutate('allow')}>{decision.isPending && <Loader2 className="animate-spin" />}Allow</Button>
          <Button className="flex-1" variant="outline" disabled={decision.isPending} onClick={() => decision.mutate('deny')}>Deny</Button>
        </div>
      </section>}
    </main>
  </div>;
}
