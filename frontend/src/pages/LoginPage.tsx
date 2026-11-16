import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { AlertCircle, ArrowUpRight, BookOpen, Check, FileText, FolderOpen, Loader2, LockKeyhole, Sparkles } from 'lucide-react';
import { ApiError, USE_MOCKS, loginWithTestEmail, signIn, usePublicConfig } from '@/api';
import { useAuthStore } from '@/store/auth';
import { errorMessage } from '@/lib/utils';
import { Brand } from '@/components/layout/Brand';
import { Button } from '@/components/ui/button';
import { GoogleLogo } from '@/components/shared/GoogleLogo';

function safeAuthorizeNext(raw: string | null): string | null {
  if (!raw) return null;
  let url: URL;
  try { url = new URL(raw); } catch { return null; }
  if (url.pathname !== '/oauth/authorize' || url.username || url.password || url.hash) return null;
  const host = url.hostname.toLowerCase();
  const loopback = host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
  if (url.protocol === 'http:' && loopback) return url.toString();
  if (url.protocol !== 'https:') return null;
  const allowed = new Set([window.location.hostname.toLowerCase()]);
  const api = import.meta.env.VITE_API_BASE_URL;
  if (typeof api === 'string' && api) { try { allowed.add(new URL(api).hostname.toLowerCase()); } catch { /* keep the page host */ } }
  return loopback || allowed.has(host) ? url.toString() : null;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const login = useAuthStore(s => s.signIn);
  const [scenario, setScenario] = useState<'success' | 'domain' | 'deactivated'>(() => params.get('error') === 'domain' ? 'domain' : params.get('error') === 'deactivated' ? 'deactivated' : 'success');
  const [email, setEmail] = useState('alex.morgan@company.com');
  const buttonRef = useRef<HTMLDivElement>(null);
  const config = usePublicConfig();
  const finish = (user: { id: string }) => { login(user as Parameters<typeof login>[0]); const next = safeAuthorizeNext(params.get('next')); if (next) { window.location.assign(next); return; } navigate('/dashboard'); };
  const mutation = useMutation({ mutationFn: (credential?: string) => USE_MOCKS ? signIn(scenario) : signIn(credential || ''), onSuccess: finish });
  const testLogin = useMutation({ mutationFn: () => loginWithTestEmail(email.trim()), onSuccess: finish });
  const clientId = config.data?.googleClientId ?? '';
  const signInRef = useRef(mutation.mutate);
  signInRef.current = mutation.mutate;
  useEffect(() => {
    if (USE_MOCKS || !clientId || !buttonRef.current) return;
    let cancelled = false;
    const render = () => {
      const google = window.google;
      if (cancelled || !google || !buttonRef.current) return;
      google.accounts.id.initialize({ client_id: clientId, callback: response => signInRef.current(response.credential) });
      buttonRef.current.innerHTML = '';
      google.accounts.id.renderButton(buttonRef.current, { theme: 'outline', size: 'large', width: 365, text: 'signin_with' });
    };
    const existing = document.querySelector<HTMLScriptElement>('script[data-gis]');
    if (existing) { if (window.google) render(); else existing.addEventListener('load', render, { once: true }); return () => { cancelled = true; }; }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.dataset.gis = 'true';
    script.onload = render;
    document.head.appendChild(script);
    return () => { cancelled = true; };
  }, [clientId]);
  const failure = mutation.error ?? testLogin.error;
  const failureTitle = failure instanceof ApiError && failure.code === 'DOMAIN_NOT_ALLOWED' ? 'Company account required' : failure instanceof ApiError && failure.code === 'ACCOUNT_DEACTIVATED' ? 'This account is deactivated' : failure instanceof ApiError && failure.code === 'NETWORK' ? 'Can’t reach the workspace' : scenario === 'domain' ? 'Company account required' : scenario === 'deactivated' ? 'This account is deactivated' : 'We couldn’t sign you in';
  return <div className="grid min-h-screen bg-card lg:grid-cols-2">
    <div className="flex min-h-screen flex-col px-8 py-8 sm:px-16 xl:px-24">
      <Brand />
      <div className="mx-auto flex w-full max-w-[365px] flex-1 flex-col justify-center py-16">
        <span className="mb-7 grid h-12 w-12 place-items-center rounded-xl border bg-accent/70 text-primary"><BookOpen size={24} strokeWidth={1.5} /></span>
        <p className="eyebrow mb-3">YOUR TEAM'S SHARED SPACE</p>
        <h1 className="text-[36px] font-semibold leading-tight tracking-[-1.3px]">Good to have<br />you here.</h1>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">A little less searching.<br />A little more moving things forward.</p>
        {USE_MOCKS || !clientId ? <Button size="lg" className="mt-9 w-full gap-3 border border-input bg-card font-medium text-foreground shadow-soft hover:bg-muted" onClick={() => mutation.mutate(undefined)} disabled={mutation.isPending}>{mutation.isPending ? <Loader2 className="animate-spin" /> : <GoogleLogo />}{mutation.isPending ? 'Signing you in…' : 'Sign in with Google'}</Button> : <div ref={buttonRef} className="mt-9 flex min-h-11 justify-center" />}
        <p className="mt-3 text-center text-[11px] text-muted-foreground">Use your company Google account</p>
        {import.meta.env.VITE_ENABLE_TEST_LOGIN === 'true' && !USE_MOCKS && <form className="mt-4 space-y-2" onSubmit={event => { event.preventDefault(); testLogin.mutate(); }}>
          <label className="block text-[10px] text-muted-foreground" htmlFor="test-email">Local test sign-in</label>
          <input id="test-email" className="select-input" value={email} onChange={event => setEmail(event.target.value)} autoComplete="username" />
          <Button type="submit" variant="outline" className="w-full" disabled={testLogin.isPending}>{testLogin.isPending ? 'Signing you in…' : 'Continue with test account'}</Button>
        </form>}
        {failure && <div className="mt-5 flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3" role="alert">
          <AlertCircle size={16} className="mt-0.5 shrink-0 text-destructive" />
          <div>
            <p className="text-xs font-medium text-destructive">{failureTitle}</p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{errorMessage(failure)}</p>
          </div>
        </div>}
        <div className="my-7 border-t" />
        <p className="flex items-center justify-center gap-1.5 text-[10px] text-muted-foreground"><LockKeyhole size={12} />Secure access for the Acme team</p>
        {USE_MOCKS && import.meta.env.DEV && <label className="mt-7 flex items-center justify-center gap-2 text-[9px] text-muted-foreground/80">Demo sign-in scenario<select aria-label="Demo sign-in scenario" className="max-w-40 rounded border bg-background px-2 py-1.5 text-[9px]" value={scenario} onChange={e => { setScenario(e.target.value as typeof scenario); mutation.reset(); }}>
          <option value="success">Successful sign-in</option>
          <option value="domain">Unauthorized domain</option>
          <option value="deactivated">Deactivated account</option>
        </select></label>}
      </div>
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>© {new Date().getFullYear()} Acme Workspace</span>
        <a href="mailto:knowledge@company.com" className="flex items-center gap-1 hover:text-primary">Need a hand?<ArrowUpRight size={11} /></a>
      </div>
    </div>
    <div className="relative hidden min-h-screen flex-col justify-between overflow-hidden bg-[#174f40] p-14 text-white lg:flex xl:p-20">
      <div className="absolute inset-0 opacity-[.07]" style={{ backgroundImage: 'radial-gradient(white .8px, transparent .8px)', backgroundSize: '24px 24px' }} />
      <div className="relative">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3 py-1.5 text-[10px] text-[#c4d5c2]"><Sparkles size={12} />Knowledge that brings us together</span>
        <h2 className="mt-8 text-[42px] font-medium leading-[1.16] tracking-[-1.3px] xl:text-[48px]">What your team knows.<br /><span className="text-[#a5c5a5]">Where your team grows.</span></h2>
        <p className="mt-5 max-w-sm text-[13px] leading-relaxed text-[#c0d1c3]">One home for the documents, ideas, and little details that make great work possible.</p>
      </div>
      <div className="relative mx-auto my-12 w-full max-w-[390px] py-8">
        <div className="absolute inset-0 rounded-full border border-white/10" />
        <div className="relative ml-3 w-[85%] -rotate-6 rounded-xl border border-[#819b7c]/30 bg-[#2b6551] p-5 shadow-xl">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-[#437861] p-2.5"><FolderOpen size={22} className="text-[#c4d9b7]" /></span>
            <div>
              <p className="text-xs font-medium">Company Knowledge</p>
              <p className="mt-1 text-[9px] text-[#b3c9b1]">Everything, in the right place.</p>
            </div>
          </div>
        </div>
        <div className="relative ml-10 mt-1 rotate-3 rounded-xl border border-[#d6dfca] bg-[#f6f7ed] p-5 text-[#33533d] shadow-2xl">
          <div className="flex items-center gap-3 border-b border-[#e1e6d7] pb-4">
            <span className="rounded-md bg-[#e5ebd8] p-2"><FileText size={20} strokeWidth={1.5} /></span>
            <div>
              <p className="text-xs font-semibold">Your team's next great idea</p>
              <p className="mt-1 text-[9px] text-[#8b9880]">Shared with your organization</p>
            </div>
            <Check className="ml-auto text-[#749266]" size={15} />
          </div>
          <div className="my-5 space-y-2.5"><div className="h-1.5 w-4/5 rounded-full bg-[#dce4ce]" /><div className="h-1.5 w-full rounded-full bg-[#e5e9dc]" /><div className="h-1.5 w-3/4 rounded-full bg-[#e5e9dc]" /></div>
          <div className="flex items-center justify-between">
            <div className="flex -space-x-2">{['AM', 'SC', 'JW'].map((name, i) => <span key={name} className="grid h-6 w-6 place-items-center rounded-full border-2 border-[#f6f7ed] text-[7px] font-medium" style={{ background: ['#d6e2c8', '#e9ddcc', '#d5dee1'][i] }}>{name}</span>)}</div>
            <span className="text-[8px] text-[#7b8e73]">Better, together.</span>
          </div>
        </div>
      </div>
      <div className="relative border-t border-white/15 pt-6">
        <p className="text-[15px] leading-relaxed text-[#d9e3d1]">“The best thing you can do with knowledge<br />is make it easy to share.”</p>
        <p className="mt-3 text-[10px] text-[#94b59c]">The Atlas way of working</p>
      </div>
    </div>
  </div>;
}
