import { useState } from 'react';
import { ChevronRight, Folder, FolderOpen, LockKeyhole } from 'lucide-react';
import type { Folder as FolderType } from '@/types';
import { cn } from '@/lib/utils';
export function FolderPicker({ folders, value, onChange, disabledIds = [] }: {
  folders: FolderType[];
  value: string;
  onChange: (id: string) => void;
  disabledIds?: string[];
}) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(folders.map(f => f.id)));
  function render(parentId: string | null, depth: number) {
    return folders.filter(f => f.parentId === parentId).map(folder => {
      const children = folders.some(f => f.parentId === folder.id);
      const isExpanded = expanded.has(folder.id);
      const disabled = folder.restricted || disabledIds.includes(folder.id);
      return <div key={folder.id} role="treeitem" aria-level={depth + 1} aria-selected={folder.id === value} aria-expanded={children ? isExpanded : undefined}>
        <div className={cn('flex items-center rounded-md', value === folder.id && 'bg-accent')} style={{ paddingLeft: depth * 15 + 4 }}>
          <button type="button" aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${folder.name}`} className={cn('icon-button h-7 w-5', !children && 'invisible')} onClick={() => setExpanded(prev => {
            const next = new Set(prev); if (next.has(folder.id))
              next.delete(folder.id);
            else
              next.add(folder.id); return next;
          })}><ChevronRight size={11} className={cn(isExpanded && 'rotate-90')} /></button>
          <button type="button" disabled={disabled} onClick={() => onChange(folder.id)} className={cn('flex min-w-0 flex-1 items-center gap-2 rounded px-1 py-2 text-left text-[11px] disabled:opacity-40', value === folder.id ? 'font-medium text-primary' : 'text-muted-foreground hover:text-foreground')} aria-label={`Select folder ${folder.name}`}>
            {folder.id === value ? <FolderOpen size={14} /> : <Folder size={14} />}
            <span className="truncate">{folder.name}</span>
            {folder.restricted && <LockKeyhole size={10} />}
            {folder.id === value && <span className="ml-auto mr-2 h-1.5 w-1.5 rounded-full bg-primary" />}
          </button>
        </div>
        {children && isExpanded && <div role="group">{render(folder.id, depth + 1)}</div>}
      </div>;
    });
  }
  return <div role="tree" aria-label="Choose a folder" className="max-h-44 overflow-y-auto rounded-md border bg-background/40 p-1.5">{render(null, 0)}</div>;
}
