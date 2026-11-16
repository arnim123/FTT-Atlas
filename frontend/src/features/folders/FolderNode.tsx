import { useState } from 'react';
import { Archive, ChevronRight, Folder, FolderInput, FolderOpen, FolderPlus, GripVertical, LockKeyhole, MoreHorizontal, Pencil, ShieldCheck, Trash2 } from 'lucide-react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import type { Folder as FolderType } from '@/types';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { canCreate, canEdit, canManage, isAdmin } from '@/lib/access';
import { cn } from '@/lib/utils';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
export function FolderNode({ folder, folders, depth, selected, expanded, toggle, select }: {
  folder: FolderType;
  folders: FolderType[];
  depth: number;
  selected: string;
  expanded: Set<string>;
  toggle: (id: string) => void;
  select: (id: string) => void;
}) {
  const user = useAuthStore(s => s.user);
  const ui = useUIStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const children = folders.filter(f => f.parentId === folder.id);
  const isExpanded = expanded.has(folder.id);
  const managed = canManage(user, folder);
  const isRoot = folder.id === 'root';
  const drag = useDraggable({ id: `folder:${folder.id}`, data: { name: folder.name }, disabled: isRoot || !managed });
  const drop = useDroppable({ id: `drop:${folder.id}`, disabled: !canEdit(user, folder) });
  const target = { kind: 'folder' as const, id: folder.id, name: folder.name };
  return <li role="treeitem" aria-level={depth + 1} aria-selected={selected === folder.id} aria-expanded={children.length ? isExpanded : undefined}>


    <div ref={node => { drag.setNodeRef(node); drop.setNodeRef(node); }} onContextMenu={event => { event.preventDefault(); setMenuOpen(true); }} className={cn('group my-0.5 flex h-9 items-center rounded-md pr-1 transition-colors', selected === folder.id ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted', drop.isOver && 'drop-active', drag.isDragging && 'opacity-40')} style={{ paddingLeft: 5 + depth * 12 }}>


      <button className={cn('grid h-7 w-4 shrink-0 place-items-center rounded-sm', !children.length && 'invisible')} onClick={() => toggle(folder.id)} aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${folder.name}`}><ChevronRight size={11} className={cn('transition-transform', isExpanded && 'rotate-90')} /></button>
      <button disabled={folder.restricted} onClick={() => select(folder.id)} className="flex min-w-0 flex-1 items-center gap-2 rounded py-1 text-left disabled:cursor-not-allowed disabled:opacity-50" aria-label={`Open folder ${folder.name}`}>
        <span className="shrink-0">{selected === folder.id ? <FolderOpen size={14} fill="currentColor" fillOpacity={0.12} /> : <Folder size={14} strokeWidth={1.5} />}</span>
        <span className={cn('truncate text-[10px]', selected === folder.id && 'font-medium')}>{folder.name}</span>
        {(folder.restricted || folder.access.level !== 'organization') && <LockKeyhole size={9} className="shrink-0" />}
      </button>


      <span className="ml-1 text-[9px] text-muted-foreground/65 group-hover:hidden">{folder.documentCount ?? 0}</span>
      <div className="hidden items-center group-focus-within:flex group-hover:flex">
        {!isRoot && managed && <button {...drag.attributes} {...drag.listeners} aria-label={`Drag folder ${folder.name}`} className="cursor-grab rounded p-0.5 touch-none"><GripVertical size={11} /></button>}
        <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
          <DropdownMenuTrigger asChild>
            <button className="rounded p-0.5" aria-label={`Actions for folder ${folder.name}`}><MoreHorizontal size={12} /></button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem disabled={!canCreate(user) || !canEdit(user, folder)} onSelect={() => ui.setFolderDialog({ mode: 'create', parentId: folder.id })}><FolderPlus />New subfolder</DropdownMenuItem>
            <DropdownMenuItem disabled={isRoot || !managed} onSelect={() => ui.setFolderDialog({ mode: 'rename', id: folder.id, name: folder.name })}><Pencil />Rename</DropdownMenuItem>
            <DropdownMenuItem disabled={isRoot || !managed} onSelect={() => ui.setMoveTargets([target])}><FolderInput />Move</DropdownMenuItem>
            <DropdownMenuItem disabled={!managed} onSelect={() => ui.setPermissions(target)}><ShieldCheck />Permissions</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={isRoot || !managed} onSelect={() => ui.setItemAction({ action: 'archive', targets: [target] })}><Archive />Archive</DropdownMenuItem>
            {isAdmin(user) && <DropdownMenuItem className="text-destructive focus:text-destructive" disabled={isRoot} onSelect={() => ui.setItemAction({ action: 'delete', targets: [target] })}><Trash2 />Delete</DropdownMenuItem>}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>


    </div>
    {children.length > 0 && isExpanded && <ul role="group">{children.map(child => <FolderNode key={child.id} folder={child} folders={folders} depth={depth + 1} selected={selected} expanded={expanded} toggle={toggle} select={select} />)}</ul>}


  </li>;
}
