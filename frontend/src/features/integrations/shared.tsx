import type { ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import type { TokenScope } from '@/types';
import { cn, copyToClipboard } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';

export function scopeSummary(scopes: TokenScope[]) {
  return scopes.includes('docs:write') ? 'Read & write' : 'Read-only';
}
export function StatusBadge({ status }: { status: string }) {
  const tone = status === 'active' || status === 'ok' ? 'text-primary' : status === 'expired' || status === 'error' ? 'text-amber-700 dark:text-amber-400' : 'text-destructive';
  const label = status === 'ok' ? 'Success' : status;
  return <span className={cn('inline-flex items-center gap-1.5 text-[10px] capitalize', tone)}><span className="h-1.5 w-1.5 rounded-full bg-current" />{label}</span>;
}
export function ChannelBadge({ channel }: { channel: string }) {
  return <span className={cn('rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide', channel === 'Web' ? 'bg-muted text-muted-foreground' : channel === 'API' || channel === 'REST' ? 'border-primary/15 bg-accent text-primary' : 'border-primary/20 bg-primary/10 text-primary')}>{channel}</span>;
}
export function Toggle({ checked, label, disabled, onChange }: {
  checked: boolean; label: string; disabled?: boolean; onChange: (next: boolean) => void;
}) {
  return <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)} className={cn('relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-40', checked ? 'bg-primary' : 'bg-foreground/20')}>
    <span className={cn('absolute top-0.5 h-4 w-4 rounded-full bg-card shadow transition-transform', checked ? 'left-4' : 'left-0.5')} />
  </button>;
}
export async function copyValue(value: string, label: string) {
  try { await copyToClipboard(value); toast.success(label); }
  catch { toast.error('Could not copy to the clipboard.'); }
}
export function CopyBlock({ value, label }: { value: string; label: string }) {
  return <div className="relative">
    <pre className="overflow-x-auto rounded-md border bg-muted/40 p-3 pr-16 font-mono text-[10px] leading-relaxed">{value}</pre>
    <Button type="button" size="sm" variant="outline" className="absolute right-2 top-2 h-7" onClick={() => void copyValue(value, label)}>Copy</Button>
  </div>;
}
export function ConfirmDialog({ title, description, confirmLabel, destructive, pending, onConfirm, onClose, children }: {
  title: string; description: string; confirmLabel: string; destructive?: boolean; pending?: boolean;
  onConfirm: () => void; onClose: () => void; children?: ReactNode;
}) {
  return <Dialog open onOpenChange={open => !open && !pending && onClose()}>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>
      {children}
      <DialogFooter>
        <Button variant="outline" disabled={pending} onClick={onClose}>Cancel</Button>
        <Button variant={destructive ? 'destructive' : 'default'} disabled={pending} onClick={onConfirm}>{pending && <Loader2 className="animate-spin" />}{confirmLabel}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}
