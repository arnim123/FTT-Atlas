import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQuery } from '@tanstack/react-query';
import { KeyRound, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import type { CreatedAccessToken, OrgSettings, TokenLifetime, TokenScope } from '@/types';
import { createToken, getOrgSettings } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useRefresh } from '@/hooks/use-data';
import { cn, errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { FormField } from '@/components/shared/FormField';
import { ErrorState } from '@/components/shared/States';
import { copyValue } from './shared';
import { integrationQuery } from './query';

const schema = z.object({ name: z.string().trim().min(1, 'Name this token.').max(60, 'Use 60 characters or fewer.'), preset: z.enum(['read', 'write']), expiresInDays: z.enum(['30', '90', '365']) });

export function CreateTokenDialog({ settings, close }: { settings?: OrgSettings; close: () => void }) {
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const [revealed, setRevealed] = useState<CreatedAccessToken | null>(null);
  const loaded = useQuery({ queryKey: integrationQuery.settings(user.id), queryFn: () => getOrgSettings(user), initialData: settings });
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { name: '', preset: 'read', expiresInDays: '30' } });
  const mutation = useMutation({
    mutationFn: (values: z.infer<typeof schema>) => createToken({ name: values.name, scopes: (values.preset === 'write' ? ['docs:read', 'docs:write'] : ['docs:read']) as TokenScope[], expiresInDays: Number(values.expiresInDays) as TokenLifetime }, user),
    onSuccess: created => { setRevealed(created); void refresh('integrations'); },
    onError: error => toast.error(errorMessage(error)),
  });
  const preset = form.watch('preset');
  const maxDays = loaded.data?.maxTokenLifetimeDays ?? 365;
  return <Dialog open onOpenChange={open => !open && !mutation.isPending && close()}>
    <DialogContent>
      <DialogHeader>
        <KeyRound size={24} className="mb-3 text-primary" />
        <DialogTitle>{revealed ? 'Copy your token' : 'Create an access token'}</DialogTitle>
        <DialogDescription>{revealed ? 'You won’t see this again. Store it somewhere safe before you close this dialog.' : 'Personal tokens act as you. An app can only see the documents you can see.'}</DialogDescription>
      </DialogHeader>
      {loaded.error ? <ErrorState error={loaded.error} retry={() => void loaded.refetch()} /> : revealed ? <div className="space-y-3">
        <p className="rounded-md bg-amber-500/10 p-3 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">Copy it now. You won’t see this again.</p>
        <div className="flex gap-2">
          <Input readOnly value={revealed.secret} aria-label="Access token" className="font-mono" />
          <Button type="button" variant="outline" onClick={() => void copyValue(revealed.secret, 'Token copied')}>Copy</Button>
        </div>
        <p className="text-[10px] text-muted-foreground">The token list will only show the prefix {revealed.prefix}…</p>
        <DialogFooter><Button type="button" onClick={close}>Done</Button></DialogFooter>
      </div> : <form onSubmit={form.handleSubmit(values => mutation.mutate(values))} className="space-y-4">
        <FormField label="Token name" htmlFor="token-name" error={form.formState.errors.name?.message}><Input id="token-name" autoFocus placeholder="ChatGPT on my laptop" {...form.register('name')} /></FormField>
        <fieldset>
          <legend className="field-label">Scope</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {([['read', 'Read-only'], ['write', 'Read & write']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={preset === value} disabled={value === 'write' && loaded.data && !loaded.data.allowWriteScopes} onClick={() => form.setValue('preset', value)} className={cn('rounded-md border px-3 py-3 text-left text-[11px]', preset === value ? 'border-primary bg-accent text-primary' : 'hover:bg-muted')}>
              <span className="block font-medium">{label}</span>
              <span className="mt-1 block text-[10px] text-muted-foreground">{value === 'read' ? 'Default. Apps can read documents you can open.' : 'Apps can also change documents you can edit.'}</span>
            </button>)}
          </div>
          {preset === 'write' && <p className="mt-2 rounded-md bg-amber-500/10 p-3 text-[10px] leading-relaxed text-amber-800 dark:text-amber-300">Write access lets this token change documents you can edit. Only grant it to an app you trust.</p>}
          {loaded.data && !loaded.data.allowWriteScopes && <p className="mt-2 text-[10px] text-muted-foreground">Your organization does not allow write scopes.</p>}
        </fieldset>
        <FormField label="Expires" htmlFor="token-expiry" error={form.formState.errors.expiresInDays?.message}>
          <select id="token-expiry" className="select-input" {...form.register('expiresInDays')}>{([30, 90, 365] as const).map(days => <option key={days} value={days} disabled={days > maxDays}>{days} days</option>)}</select>
        </FormField>
        <p className="text-[10px] text-muted-foreground">The longest lifetime this workspace allows is {maxDays} days.</p>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={close}>Cancel</Button>
          <Button disabled={mutation.isPending || !loaded.data?.allowExternalAi} type="submit">{mutation.isPending && <Loader2 className="animate-spin" />}Create token</Button>
        </DialogFooter>
      </form>}
    </DialogContent>
  </Dialog>;
}
