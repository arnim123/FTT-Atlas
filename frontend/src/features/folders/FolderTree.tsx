import { useState } from 'react';
import { ChevronsDownUp, ChevronsUpDown, FolderPlus, Layers3 } from 'lucide-react';
import type { Folder } from '@/types';
import { FolderNode } from './FolderNode';
import { Button } from '@/components/ui/button';
import { Tooltip } from '@/components/ui/tooltip';
import { useUIStore } from '@/store/ui';
import { useAuthStore } from '@/store/auth';
import { canCreate } from '@/lib/access';
import { cn } from '@/lib/utils';
export function FolderTree({ folders, selected, select, className }: {
  folders: Folder[];
  selected: string;
  select: (id: string) => void;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(new Set(['root', 'products', 'erp', 'hr', 'sales']));
  const ui = useUIStore();
  const user = useAuthStore(s => s.user);
  const toggle = (id: string) => setExpanded(prev => {
    const next = new Set(prev); if (next.has(id))
      next.delete(id);
    else
      next.add(id); return next;
  });
  return <aside className={cn('flex flex-col border-r bg-card', className)} aria-label="Document folders">
    <div className="flex h-14 items-center justify-between border-b px-4">
      <span className="eyebrow">Your library</span>
      <div className="flex items-center">
        <Tooltip content="Expand all folders">
          <button className="icon-button h-6 w-6" onClick={() => setExpanded(new Set(folders.map(f => f.id)))} aria-label="Expand all folders"><ChevronsUpDown size={12} /></button>
        </Tooltip>
        <Tooltip content="Collapse all folders">
          <button className="icon-button h-6 w-6" onClick={() => setExpanded(new Set())} aria-label="Collapse all folders"><ChevronsDownUp size={12} /></button>
        </Tooltip>
      </div>
    </div>
    <div className="px-2.5 pt-3">
      <button onClick={() => select('root')} className={cn('mb-3 flex h-9 w-full items-center gap-2.5 rounded-md px-3 text-[11px] font-medium', selected === 'root' ? 'bg-primary/[0.07] text-primary' : 'text-muted-foreground hover:bg-muted')}><Layers3 size={14} />All documents<span className="ml-auto text-[9px] text-muted-foreground">{folders.find(f => f.id === 'root')?.documentCount}</span></button>
      <p className="eyebrow mb-2 px-3 text-[8px]">Folders</p>
    </div>
    <ul role="tree" aria-label="Company folder tree" className="max-h-[650px] min-h-[260px] flex-1 overflow-auto px-2 pb-4">{folders.filter(f => !f.parentId).map(folder => <FolderNode key={folder.id} folder={folder} folders={folders} depth={0} selected={selected} expanded={expanded} toggle={toggle} select={select} />)}</ul>
    {canCreate(user) && <div className="border-t p-3">
      <Button variant="ghost" size="sm" className="w-full justify-start text-muted-foreground" onClick={() => ui.setFolderDialog({ mode: 'create', parentId: selected })}><FolderPlus />New folder</Button>
    </div>}
    <p className="px-4 pb-4 text-[9px] leading-relaxed text-muted-foreground/70">A little order goes a long way.<br />Drag items into folders to organize.</p>
  </aside>;
}
