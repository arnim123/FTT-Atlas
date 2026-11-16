import { Link } from 'react-router-dom';
import { ArrowUpRight, Eye, TrendingUp } from 'lucide-react';
import type { Document } from '@/types';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { EmptyState } from '@/components/shared/States';
export function PopularDocuments({ documents }: {
  documents: Document[];
}) {
  return <section className="panel min-w-0">
    <div className="flex items-center justify-between px-5 pb-4 pt-5">
      <div>
        <h2 className="text-[13px] font-semibold">The team's go-to</h2>
        <p className="mt-1.5 text-[10px] text-muted-foreground">Most viewed knowledge</p>
      </div>
      <TrendingUp size={17} className="text-muted-foreground" strokeWidth={1.5} />
    </div>
    {!documents.length ? <EmptyState title="The next team favorite is yours" /> : <div className="px-5">{documents.map((doc, index) => <Link key={doc.id} to={`/documents/${doc.id}`} className="group flex items-center gap-3 border-t py-3.5">
      <span className="w-2.5 text-[9px] tabular-nums text-muted-foreground/60">{String(index + 1).padStart(2, '0')}</span>
      <DocumentIcon type={doc.type} small />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[11px] font-medium group-hover:text-primary">{doc.name}</p>
        <span className="mt-1.5 flex items-center gap-1 text-[9px] text-muted-foreground"><Eye size={10} />{doc.views.toLocaleString()} views</span>
      </div>
      <ArrowUpRight size={13} className="text-muted-foreground/40 group-hover:text-primary" />
    </Link>)}</div>}
  </section>;
}
