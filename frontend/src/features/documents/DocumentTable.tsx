import { Link } from 'react-router-dom';
import { GripVertical } from 'lucide-react';
import { useDraggable } from '@dnd-kit/core';
import type { Document, ReferenceData } from '@/types';
import { useAuthStore } from '@/store/auth';
import { canManage } from '@/lib/access';
import { cn, formatDate } from '@/lib/utils';
import { Avatar } from '@/components/shared/Avatar';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { AccessBadge } from '@/components/shared/AccessBadge';
import { Checkbox } from '@/components/ui/checkbox';
import { DocumentMenu } from './DocumentMenu';
interface Props {
  documents: Document[];
  reference: ReferenceData;
  selected: Set<string>;
  toggle: (id: string) => void;
  toggleAll: () => void;
}
export function DocumentTable({ documents, reference, selected, toggle, toggleAll }: Props) {
  return <div className="w-full overflow-x-auto">
    <table className="w-full min-w-[880px] text-left">
      <thead>
        <tr className="table-head">
          <th className="w-10 py-3 pl-4"><Checkbox aria-label="Select all documents" checked={documents.length > 0 && documents.every(doc => selected.has(doc.id)) ? true : selected.size > 0 ? 'indeterminate' : false} onCheckedChange={toggleAll} /></th>
          <th className="px-3 py-3 font-medium">Name</th>
          <th className="px-3 py-3 font-medium">Tags</th>
          <th className="px-3 py-3 font-medium">Department</th>
          <th className="px-3 py-3 font-medium">Owner</th>
          <th className="whitespace-nowrap px-3 py-3 font-medium">Modified</th>
          <th className="px-3 py-3 font-medium">Version</th>
          <th className="px-3 py-3 font-medium">Access</th>
          <th className="w-8">
            <span className="sr-only">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody>{documents.map(doc => <DocumentRow key={doc.id} doc={doc} reference={reference} selected={selected.has(doc.id)} toggle={() => toggle(doc.id)} />)}</tbody>
    </table>
  </div>;
}
function DocumentRow({ doc, reference, selected, toggle }: {
  doc: Document;
  reference: ReferenceData;
  selected: boolean;
  toggle: () => void;
}) {
  const user = useAuthStore(s => s.user);
  const owner = reference.users.find(u => u.id === doc.ownerId);
  const drag = useDraggable({ id: `document:${doc.id}`, data: { name: doc.name }, disabled: !canManage(user, doc) });
  return <tr ref={drag.setNodeRef} className={cn('group border-t transition-colors hover:bg-muted/30', selected && 'bg-accent/50', drag.isDragging && 'opacity-40')}>
    <td className="py-3 pl-4"><Checkbox checked={selected} onCheckedChange={toggle} aria-label={`Select ${doc.name}`} /></td>
    <td className="px-3 py-3">
      <div className="flex items-center gap-2">
        <button {...drag.attributes} {...drag.listeners} aria-label={`Drag ${doc.name}`} disabled={!canManage(user, doc)} className="-ml-2 shrink-0 cursor-grab rounded text-muted-foreground/30 opacity-0 touch-none focus:opacity-100 disabled:pointer-events-none group-hover:opacity-100"><GripVertical size={11} /></button>
        <DocumentIcon type={doc.type} small />
        <Link to={`/documents/${doc.id}`} className="min-w-[165px] max-w-[230px]">
          <p className="truncate text-[11px] font-medium hover:text-primary">{doc.name}</p>
          <p className="mt-1 max-w-[225px] truncate text-[9px] text-muted-foreground">{doc.description}</p>
        </Link>
      </div>
    </td>
    <td className="px-3 py-3">
      <div className="flex items-center gap-1">
        <span className="tag max-w-[95px] truncate">{doc.tags[0] ?? 'Untagged'}</span>
        {doc.tags.length > 1 && <span className="text-[9px] text-muted-foreground" title={doc.tags.slice(1).join(', ')}>+{doc.tags.length - 1}</span>}
      </div>
    </td>
    <td className="px-3 py-3 text-[10px] text-muted-foreground">{reference.departments.find(d => d.id === doc.departmentId)?.name ?? 'Unassigned'}</td>
    <td className="px-3 py-3">{owner && <div className="flex items-center gap-1.5">
      <Avatar name={owner.name} color={owner.color} size="xs" />
      <span className="whitespace-nowrap text-[10px] text-muted-foreground">{owner.name.split(' ')[0]}</span>
    </div>}</td>
    <td className="whitespace-nowrap px-3 py-3 text-[10px] text-muted-foreground">{formatDate(doc.modifiedAt)}</td>
    <td className="px-3 py-3 text-[10px] tabular-nums text-muted-foreground">v{doc.version}.0</td>
    <td className="px-3 py-3"><AccessBadge level={doc.access.level} /></td>
    <td className="pr-3"><DocumentMenu document={doc} /></td>
  </tr>;
}
