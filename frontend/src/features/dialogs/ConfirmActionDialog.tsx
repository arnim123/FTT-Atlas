import { useMutation } from '@tanstack/react-query';
import { useNavigate, useLocation } from 'react-router-dom';
import { Archive, Loader2, RotateCcw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { bulkDocuments, deleteFolder, updateFolder } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useRefresh } from '@/hooks/use-data';
import { errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
export function ConfirmActionDialog() {
  const config = useUIStore(s => s.itemAction)!;
  const close = useUIStore(s => s.setItemAction);
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const navigate = useNavigate();
  const location = useLocation();
  const { targets, action } = config;
  const label = action === 'delete' ? 'Delete permanently' : action === 'archive' ? 'Archive' : 'Restore';
  const Icon = action === 'delete' ? Trash2 : action === 'archive' ? Archive : RotateCcw;
  const mutation = useMutation({
    mutationFn: async () => {
      const ids = targets.filter(t => t.kind === 'document').map(t => t.id); if (ids.length)
        await bulkDocuments(ids, action, user); for (const target of targets.filter(t => t.kind === 'folder')) {
          if (action === 'delete')
            await deleteFolder(target.id, user);
          else
            await updateFolder(target.id, { archived: action === 'archive' }, user);
        }
    }, onSuccess: () => {
      close(null); void refresh(); toast.success(action === 'delete' ? 'Items permanently deleted' : action === 'archive' ? 'Moved to archive' : 'Items restored'); if (action !== 'restore' && targets.some(t => location.pathname === `/documents/${t.id}`))
        navigate('/documents');
    }, onError: error => toast.error(errorMessage(error))
  });
  return <Dialog open onOpenChange={open => !open && !mutation.isPending && close(null)}>
    <DialogContent>
      <DialogHeader>
        <span className={`mb-4 inline-flex rounded-lg p-3 ${action === 'delete' ? 'bg-destructive/10 text-destructive' : 'bg-accent text-primary'}`}><Icon size={21} /></span>
        <DialogTitle>{label} {targets.length === 1 ? 'this item' : `${targets.length} items`}?</DialogTitle>
        <DialogDescription>{action === 'delete' ? 'This permanently deletes the selected items and their version history from this workspace. This action cannot be undone.' : action === 'archive' ? 'Archived items leave the active workspace. You can bring them back from Archive whenever you need them.' : 'These items will return to their original folders and become available to people with access.'}</DialogDescription>
      </DialogHeader>
      <div className="max-h-36 overflow-y-auto rounded-md border bg-muted/30 p-3">{targets.map(target => <p key={target.id} className="truncate py-1 text-xs">{target.name}</p>)}</div>
      {targets.some(t => t.kind === 'folder') && <p className="mt-3 text-[11px] text-muted-foreground">This also applies to all subfolders and documents inside.</p>}
      <DialogFooter>
        <Button variant="outline" disabled={mutation.isPending} onClick={() => close(null)}>Cancel</Button>
        <Button variant={action === 'delete' ? 'destructive' : 'default'} disabled={mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending && <Loader2 className="animate-spin" />}{label}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}
