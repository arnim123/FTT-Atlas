import type { Document, ReferenceData } from '@/types';
import { Avatar } from '@/components/shared/Avatar';
import { AccessBadge } from '@/components/shared/AccessBadge';
import { TYPE_LABELS } from '@/lib/constants';
import { formatBytes, formatDate } from '@/lib/utils';
import { RecentAccess } from './RecentAccess';
export function DocumentDetails({ document: doc, reference }: {
  document: Document;
  reference: ReferenceData;
}) {
  const owner = reference.users.find(u => u.id === doc.ownerId);
  return <div className="space-y-5">
    <div>
      <p className="eyebrow mb-2 text-[8px]">Document name</p>
      <p className="text-xs font-medium">{doc.name}</p>
    </div>
    <div>
      <p className="eyebrow mb-2 text-[8px]">About this document</p>
      <p className="text-[11px] leading-relaxed text-muted-foreground">{doc.description || 'No description has been added yet.'}</p>
    </div>
    <div>
      <p className="eyebrow mb-2 text-[8px]">Tags</p>
      <div className="flex flex-wrap gap-1.5">{doc.tags.length ? doc.tags.map(tag => <span className="tag" key={tag}>{tag}</span>) : <span className="text-[10px] text-muted-foreground">No tags yet</span>}</div>
    </div>
    <dl className="space-y-4 border-t pt-4">
      {[['Category', reference.categories.find(c => c.id === doc.categoryId)?.name ?? 'Uncategorized'], ['Department', reference.departments.find(d => d.id === doc.departmentId)?.name ?? 'Unassigned']].map(([label, value]) => <div key={label} className="flex justify-between gap-3 text-[10px]">
        <dt className="text-muted-foreground">{label}</dt>
        <dd className="text-right">{value}</dd>
      </div>)}
      <div className="flex items-center justify-between text-[10px]">
        <dt className="text-muted-foreground">Owner</dt>
        <dd className="flex items-center gap-1.5">{owner && <>
          <Avatar name={owner.name} color={owner.color} size="xs" />
          {owner.name}
        </>}</dd>
      </div>
      {[['Uploaded', formatDate(doc.createdAt, true)], ['Last modified', formatDate(doc.modifiedAt, true)], ['Version', `v${doc.version}.0`], ['Source', TYPE_LABELS[doc.type]], ['File size', formatBytes(doc.size)]].map(([label, value]) => <div key={label} className="flex justify-between gap-3 text-[10px]">
        <dt className="text-muted-foreground">{label}</dt>
        <dd>{value}</dd>
      </div>)}
      <div className="flex items-center justify-between text-[10px]">
        <dt className="text-muted-foreground">Access level</dt>
        <dd><AccessBadge level={doc.access.level} /></dd>
      </div>
    </dl>
    <RecentAccess documentId={doc.id} />
  </div>;
}
