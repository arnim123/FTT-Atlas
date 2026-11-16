import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { FolderInput, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { bulkDocuments, updateFolder } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useFolders, useRefresh } from '@/hooks/use-data';
import { canEdit } from '@/lib/access';
import { errorMessage } from '@/lib/utils';
import { FolderPicker } from '@/features/folders/FolderPicker';
import { ErrorState, PageSkeleton } from '@/components/shared/States';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
export function MoveDialog() {
  const targets = useUIStore(s => s.moveTargets);
  const close = useUIStore(s => s.setMoveTargets);
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const folders = useFolders();
  const [destination, setDestination] = useState('root');
  const disabledIds = folders.data?.filter(f => !canEdit(user, f) || targets.some(t => t.kind === 'folder' && t.id === f.id)).map(f => f.id) ?? [];
  const move = useMutation({
    mutationFn: async () => {
      const docIds = targets.filter(t => t.kind === 'document').map(t => t.id); if (docIds.length)
        await bulkDocuments(docIds, 'move', user, destination); for (const target of targets.filter(t => t.kind === 'folder'))
        await updateFolder(target.id, { parentId: destination }, user);
    }, onSuccess: () => { close([]); void refresh(); toast.success(`${targets.length === 1 ? targets[0].name : `${targets.length} items`} moved`); }, onError: error => toast.error(errorMessage(error))
  });
  return <Dialog open onOpenChange={open => !open && !move.isPending && close([])}>
    <DialogContent>
      <DialogHeader>
        <FolderInput size={25} className="mb-3 text-primary" />
        <DialogTitle>Move {targets.length === 1 ? 'item' : `${targets.length} items`}</DialogTitle>
        <DialogDescription>Choose a new folder for {targets.length === 1 ? `“${targets[0].name}”` : 'the selected items'}. Existing permissions will stay the same.</DialogDescription>
      </DialogHeader>
      {folders.error ? <ErrorState error={folders.error} retry={() => void folders.refetch()} /> : !folders.data ? <PageSkeleton rows={2} /> : <FolderPicker folders={folders.data} value={destination} onChange={setDestination} disabledIds={disabledIds} />}
      <DialogFooter>
        <Button variant="outline" onClick={() => close([])}>Cancel</Button>
        <Button onClick={() => move.mutate()} disabled={move.isPending || !folders.data || disabledIds.includes(destination)}>{move.isPending && <Loader2 className="animate-spin" />}Move here</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
}
