import { Link } from 'react-router-dom';
import { ArrowRight, ArrowUpRight } from 'lucide-react';
import type { Document, ReferenceData } from '@/types';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { Avatar } from '@/components/shared/Avatar';
import { formatDate } from '@/lib/utils';
import { EmptyState } from '@/components/shared/States';
export function RecentDocuments({ documents, reference }: {
  documents: Document[];
  reference: ReferenceData;
}) {
  return <section className="panel min-w-0 overflow-hidden">
    <div className="flex items-center justify-between px-5 py-5">
      <div>
        <h2 className="text-[13px] font-semibold">Fresh off the press</h2>
        <p className="mt-1.5 text-[10px] text-muted-foreground">Recent uploads and updates from your team</p>
      </div>
      <Link to="/documents" className="flex items-center gap-1.5 text-[10px] font-medium text-primary">View all<ArrowRight size={12} /></Link>
    </div>
    {!documents.length ? <EmptyState /> : <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="table-head">
            <th className="px-5 py-2.5 font-medium">Document name</th>
            <th className="hidden px-3 py-2.5 font-medium xl:table-cell">Department</th>
            <th className="px-3 py-2.5 font-medium">Added by</th>
            <th className="px-5 py-2.5 font-medium">Updated</th>
            <th>
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>{documents.map(doc => {
          const owner = reference.users.find(u => u.id === doc.ownerId); return <tr key={doc.id} className="group transition-colors hover:bg-muted/30">
            <td className="border-t py-3 pl-5 pr-3">
              <Link to={`/documents/${doc.id}`} className="flex min-w-[190px] items-center gap-3">
                <DocumentIcon type={doc.type} small />
                <div className="min-w-0">
                  <p className="max-w-[240px] truncate text-[11px] font-medium group-hover:text-primary">{doc.name}</p>
                  <p className="mt-1 text-[9px] text-muted-foreground">{doc.tags.slice(0, 2).join(' · ')}</p>
                </div>
              </Link>
            </td>
            <td className="hidden border-t px-3 text-[10px] text-muted-foreground xl:table-cell">{reference.departments.find(d => d.id === doc.departmentId)?.name}</td>
            <td className="border-t px-3">{owner && <div className="flex items-center gap-1.5">
              <Avatar name={owner.name} color={owner.color} size="xs" />
              <span className="whitespace-nowrap text-[10px] text-muted-foreground">{owner.name.split(' ')[0]}</span>
            </div>}</td>
            <td className="whitespace-nowrap border-t px-5 text-[10px] text-muted-foreground">{formatDate(doc.modifiedAt)}</td>
            <td className="border-t pr-4">
              <Link to={`/documents/${doc.id}`} aria-label={`Open ${doc.name}`} className="icon-button h-6 w-6"><ArrowUpRight size={13} /></Link>
            </td>
          </tr>;
        })}</tbody>
      </table>
    </div>}
  </section>;
}
