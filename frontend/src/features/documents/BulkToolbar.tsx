import { Archive, FolderInput, Trash2, X } from 'lucide-react';
import type { Document } from '@/types';
import { useUIStore } from '@/store/ui';
import { useAuthStore } from '@/store/auth';
import { canManage, isAdmin } from '@/lib/access';
import { Button } from '@/components/ui/button';
export function BulkToolbar({ selected, clear }: {
  selected: Document[];
  clear: () => void;
}) {
  const user = useAuthStore(s => s.user);
  const ui = useUIStore();
  const targets = selected.map(d => ({ kind: 'document' as const, id: d.id, name: d.name }));
  const allowed = selected.every(d => canManage(user, d));
  return <div className="flex flex-wrap items-center gap-2 border-b bg-accent px-4 py-2">
    <span className="mr-2 text-[11px] font-medium text-primary">{selected.length} selected</span>
    <Button variant="outline" size="sm" disabled={!allowed} onClick={() => ui.setMoveTargets(targets)}><FolderInput />Move</Button>
    <Button variant="outline" size="sm" disabled={!allowed} onClick={() => ui.setItemAction({ action: 'archive', targets })}><Archive />Archive</Button>
    {isAdmin(user) && <Button variant="outline" size="sm" className="text-destructive" onClick={() => ui.setItemAction({ action: 'delete', targets })}><Trash2 />Delete</Button>}
    <button className="icon-button ml-auto" onClick={clear} aria-label="Clear selection"><X size={14} /></button>
    {!allowed && <p className="w-full text-[10px] text-muted-foreground">Some selected documents are managed by another owner.</p>}
  </div>;
}
