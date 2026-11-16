import { Link } from 'react-router-dom';
import { useDraggable } from '@dnd-kit/core';
import { GripVertical } from 'lucide-react';
import type { Document, ReferenceData } from '@/types';
import { Checkbox } from '@/components/ui/checkbox';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { AccessBadge } from '@/components/shared/AccessBadge';
import { Avatar } from '@/components/shared/Avatar';
import { cn, formatDate } from '@/lib/utils';
import { useAuthStore } from '@/store/auth';
import { canManage } from '@/lib/access';
import { DocumentMenu } from './DocumentMenu';
export function DocumentGrid({ documents, reference, selected, toggle }: {
  documents: Document[];
  reference: ReferenceData;
  selected: Set<string>;
  toggle: (id: string) => void;
}) { return <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 2xl:grid-cols-3">{documents.map(doc => <DocumentCard key={doc.id} doc={doc} reference={reference} selected={selected.has(doc.id)} toggle={() => toggle(doc.id)} />)}</div>; }
function DocumentCard({ doc, reference, selected, toggle }: {
  doc: Document;
  reference: ReferenceData;
  selected: boolean;
  toggle: () => void;
}) {
  const user = useAuthStore(s => s.user);
  const owner = reference.users.find(u => u.id === doc.ownerId);
  const drag = useDraggable({ id: `document:${doc.id}`, data: { name: doc.name }, disabled: !canManage(user, doc) });
  return <div ref={drag.setNodeRef} className={cn('panel group overflow-hidden transition-shadow hover:shadow-md', selected && 'border-primary bg-accent/30', drag.isDragging && 'opacity-40')}>
    <div className="relative flex h-28 items-center justify-center border-b bg-muted/40">
      <div className="flex h-24 w-20 translate-y-2 flex-col gap-1.5 rounded-t border bg-card p-3 shadow-soft"><DocumentIcon type={doc.type} small /><div className="h-1 w-full rounded bg-border" /><div className="h-1 w-4/5 rounded bg-border" /><div className="h-1 w-full rounded bg-border" /></div>
      <Checkbox className="absolute left-3 top-3" checked={selected} onCheckedChange={toggle} aria-label={`Select ${doc.name}`} />
      <button {...drag.attributes} {...drag.listeners} disabled={!canManage(user, doc)} aria-label={`Drag ${doc.name}`} className="absolute right-3 top-3 cursor-grab rounded text-muted-foreground touch-none disabled:hidden"><GripVertical size={13} /></button>
    </div>
    <div className="p-4">
      <div className="flex items-start justify-between gap-2">
        <Link to={`/documents/${doc.id}`} className="min-w-0">
          <h3 className="truncate text-xs font-medium hover:text-primary">{doc.name}</h3>
          <p className="mt-1.5 line-clamp-2 h-8 text-[10px] leading-relaxed text-muted-foreground">{doc.description}</p>
        </Link>
        <DocumentMenu document={doc} />
      </div>
      <div className="mt-3 flex gap-1">{doc.tags.slice(0, 2).map(tag => <span key={tag} className="tag truncate">{tag}</span>)}</div>
      <div className="mt-4 flex items-center justify-between border-t pt-3">{owner && <div className="flex items-center gap-1.5">
        <Avatar name={owner.name} color={owner.color} size="xs" />
        <span className="text-[9px] text-muted-foreground">{formatDate(doc.modifiedAt)}</span>
      </div>}<AccessBadge level={doc.access.level} /></div>
    </div>
  </div>;
}
