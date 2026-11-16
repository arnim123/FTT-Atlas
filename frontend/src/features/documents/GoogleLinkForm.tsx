import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, Copy, Link2, Loader2, RefreshCw, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { USE_MOCKS, checkGoogleSharing, serviceEmail, validateGoogleUrl } from '@/api';
import { useDebounce } from '@/hooks/use-debounce';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
export function GoogleLinkForm({ value, onChange }: {
  value: string;
  onChange: (url: string) => void;
}) {
  const url = useDebounce(value);
  const valid = validateGoogleUrl(url);
  const [copied, setCopied] = useState(false);
  const { data, isFetching, error, refetch } = useQuery({ queryKey: ['google-sharing', url], queryFn: () => checkGoogleSharing(url), enabled: valid });
  const email = data?.email || serviceEmail();
  async function copy() {
    try {
      await navigator.clipboard.writeText(email);
      setCopied(true);
      toast.success('Service account email copied');
    }
    catch {
      toast.error('Clipboard access is unavailable. Select and copy the email below.');
    }
  }
  return <div className="space-y-3">
    <label htmlFor="google-url" className="field-label">Google document URL</label>
    <div className="relative"><Link2 className="absolute left-3 top-3 text-muted-foreground" size={14} /><Input id="google-url" className="h-10 pl-9" value={value} onChange={e => onChange(e.target.value)} placeholder="https://docs.google.com/document/d/..." aria-invalid={!!url && !valid} /></div>
    {url && !valid ? <p className="text-[10px] text-destructive" role="alert">Enter a valid https://docs.google.com document, spreadsheet, or presentation URL.</p> : isFetching ? <p className="flex items-center gap-1.5 text-[10px] text-muted-foreground" role="status"><Loader2 size={12} className="animate-spin" />Checking document access…</p> : error ? <div role="alert" className="text-[10px] text-destructive">Couldn’t check sharing. <button type="button" onClick={() => void refetch()} className="underline">Try again</button></div> : data?.shared ? <p className="flex items-center gap-1.5 text-[10px] text-primary"><CheckCircle2 size={13} />Link looks good. This document is ready to connect.</p> : data && <div className="rounded-md border border-amber-500/25 bg-amber-500/10 p-3 text-amber-900 dark:text-amber-200">
      <div className="flex items-center gap-2 text-xs font-medium"><ShieldAlert size={16} />One more step before we connect</div>
      <p className="mt-2 text-[10px] leading-relaxed">Share this doc with {email} as Editor</p>
      <div className="mt-2 flex items-center gap-2">
        <code className="min-w-0 flex-1 select-all break-all text-[9px]">{email}</code>
        <Button type="button" variant="outline" size="icon" aria-label="Copy service account email" onClick={copy}>{copied ? <CheckCircle2 /> : <Copy />}</Button>
      </div>
      <Button className="mt-2" type="button" variant="ghost" size="sm" onClick={() => void refetch()}><RefreshCw />Check access again</Button>
    </div>}
    <p className="text-[9px] leading-relaxed text-muted-foreground">Supports Google Docs, Sheets, and Slides. The original stays in Google Drive.</p>
    {USE_MOCKS && import.meta.env.DEV && <p className="text-[9px] text-muted-foreground/70">Demo: use a file ID containing “unshared” to preview the sharing requirement.</p>}
  </div>;
}
