import { ArrowUpRight, FileSearch, Hash, Type } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ReferenceData, SearchResult } from '@/types';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { AccessBadge } from '@/components/shared/AccessBadge';
import { formatDate } from '@/lib/utils';
import { Highlight } from './Highlight';
export function SearchResultCard({ result, query, reference, onOpen }: {
  result: SearchResult;
  query: string;
  reference: ReferenceData;
  onOpen: () => void;
}) {
  const { document: doc, matchedIn, snippet } = result;
  return <article className="panel group p-5 transition-colors hover:border-primary/30">
    <div className="flex items-start gap-3.5">
      <DocumentIcon type={doc.type} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <Link to={`/documents/${doc.id}`} onClick={onOpen} className="min-w-0 text-[13px] font-semibold tracking-tight hover:text-primary"><Highlight text={doc.name} query={query} /></Link>
          <Link to={`/documents/${doc.id}`} onClick={onOpen} className="icon-button h-6 w-6" aria-label={`Open ${doc.name}`}><ArrowUpRight size={14} /></Link>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[9px] text-muted-foreground">
          <span>{reference.departments.find(d => d.id === doc.departmentId)?.name}</span>
          <span>·</span>
          <span>{reference.users.find(u => u.id === doc.ownerId)?.name}</span>
          <span>·</span>
          <span>Updated {formatDate(doc.modifiedAt)}</span>
          {doc.archived && <span className="tag">Archived</span>}
        </div>
        <p className="mt-3 line-clamp-2 text-[11px] leading-[1.8] text-muted-foreground"><Highlight text={snippet} query={query} /></p>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">{matchedIn.length > 0 && <span className="mr-1 text-[8px] text-muted-foreground">Matched in</span>}{matchedIn.map(match => { const Icon = match === 'name' ? Type : match === 'tag' ? Hash : FileSearch; return <span key={match} className="inline-flex items-center gap-1 rounded border bg-muted/40 px-1.5 py-1 text-[8px] capitalize text-muted-foreground"><Icon size={9} />{match}</span>; })}{doc.tags.slice(0, 2).map(tag => <span key={tag} className="tag"><Highlight text={tag} query={query} /></span>)}</div>
          <AccessBadge level={doc.access.level} />
        </div>
      </div>
    </div>
  </article>;
}
