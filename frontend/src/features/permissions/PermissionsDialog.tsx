import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { CheckCheck, Clock3, CloudOff, Loader2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import type { Access, ResourceTarget } from '@/types';
import { getPermissions, retryPermissionSync, updatePermissions } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useReferenceData, useRefresh } from '@/hooks/use-data';
import { DEFAULT_ACCESS } from '@/lib/constants';
import { errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ErrorState, PageSkeleton } from '@/components/shared/States';
import { AccessPicker } from './AccessPicker';
export function PermissionsDialog({ target }: {
  target: ResourceTarget;
}) {
  const user = useAuthStore(s => s.user);
  const close = useUIStore(s => s.setPermissions);
  const refresh = useRefresh();
  const reference = useReferenceData();
  const { data, error, isPending, refetch } = useQuery({ queryKey: ['permissions', target.id, user.id], queryFn: () => getPermissions(target, user) });
  const [access, setAccess] = useState<Access>(DEFAULT_ACCESS);
  useEffect(() => {
    if (data)
      setAccess(data.access);
  }, [data]);
  const save = useMutation({ mutationFn: () => updatePermissions(target, access, user), onSuccess: () => { void refresh(); close(null); toast.success('Permissions updated'); }, onError: error => toast.error(errorMessage(error)) });
  const sync = useMutation({ mutationFn: () => retryPermissionSync(target, user), onSuccess: value => { setAccess(value); void refresh(); toast.success('Google permissions are synced'); }, onError: error => toast.error(errorMessage(error)) });
  const Icon = access.syncStatus === 'synced' ? CheckCheck : access.syncStatus === 'failed' ? CloudOff : Clock3;
  return <Dialog open onOpenChange={open => !open && !save.isPending && close(null)}>
    <DialogContent className="max-w-[550px]">
      <DialogHeader>
        <div className="mb-3 grid h-9 w-9 place-items-center rounded-lg bg-accent text-primary"><ShieldCheck size={19} /></div>
        <DialogTitle>Sharing & permissions</DialogTitle>
        <DialogDescription>Choose who can access “{target.name}”.</DialogDescription>
      </DialogHeader>
      {error || reference.error ? <ErrorState error={error ?? reference.error} retry={() => { void refetch(); void reference.refetch(); }} /> : isPending || !data || !reference.data ? <PageSkeleton rows={2} /> : <>
        <AccessPicker value={access} onChange={setAccess} reference={reference.data} ownerId={data.ownerId} departmentId={data.departmentId} />
        <div className="mt-5 flex items-center justify-between rounded-md bg-muted/60 px-3 py-2.5">
          <span className="flex min-w-0 flex-col gap-1 text-[10px] text-muted-foreground"><span className="flex items-center gap-1.5"><Icon size={13} />Google sync: <span className={access.syncStatus === 'failed' ? 'text-destructive' : 'text-primary'}>{access.syncStatus === 'synced' ? 'Synced' : access.syncStatus === 'failed' ? 'Failed' : 'Pending'}</span></span>{access.syncError && <span className="text-destructive">{access.syncError}</span>}</span>
          {access.syncStatus !== 'synced' && <Button variant="ghost" size="sm" onClick={() => sync.mutate()} disabled={sync.isPending}>{sync.isPending && <Loader2 className="animate-spin" />}{access.syncStatus === 'failed' ? 'Retry' : 'Sync now'}</Button>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => close(null)} disabled={save.isPending}>Cancel</Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending || (access.level === 'custom' && !access.grants.length)}>{save.isPending && <Loader2 className="animate-spin" />}Save permissions</Button>
        </DialogFooter>
      </>}
    </DialogContent>
  </Dialog>;
}
