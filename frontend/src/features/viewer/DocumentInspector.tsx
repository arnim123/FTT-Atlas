import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, CheckCheck, Clock3, CloudOff, LockKeyhole, ShieldCheck, Sparkles, X } from 'lucide-react';
import type { Document, ReferenceData } from '@/types';
import { getRelatedDocuments } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { canManage, canView } from '@/lib/access';
import { ACCESS_LABELS } from '@/lib/constants';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Avatar } from '@/components/shared/Avatar';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { EmptyState, ErrorState, Skeleton } from '@/components/shared/States';
import { DocumentDetails } from './DocumentDetails';
import { VersionHistory } from './VersionHistory';
export function DocumentInspector({ document: doc, reference, close }: {
  document: Document;
  reference: ReferenceData;
  close: () => void;
}) {
  const user = useAuthStore(s => s.user);
  const ui = useUIStore();
  const people = reference.users.filter(u => canView(u, doc));
  const related = useQuery({ queryKey: ['related', doc.id, user.id], queryFn: () => getRelatedDocuments(doc.id, user) });
  const SyncIcon = doc.access.syncStatus === 'synced' ? CheckCheck : doc.access.syncStatus === 'failed' ? CloudOff : Clock3;
  return <aside className="w-full shrink-0 border-l bg-card lg:w-[300px] 2xl:w-[325px]" aria-label="Document information">
    <div className="flex items-center justify-between border-b px-5 py-3.5">
      <p className="text-xs font-semibold">Document information</p>
      <button className="icon-button h-6 w-6" aria-label="Close document information" onClick={close}><X size={14} /></button>
    </div>
    <Tabs defaultValue="details">
      <TabsList className="flex w-full justify-between gap-0 rounded-none border-b bg-transparent px-3 py-2">
        <TabsTrigger className="px-2 text-[9px] data-[state=active]:bg-accent data-[state=active]:text-primary" value="details">Details</TabsTrigger>
        <TabsTrigger className="px-2 text-[9px] data-[state=active]:bg-accent data-[state=active]:text-primary" value="permissions">Permissions</TabsTrigger>
        <TabsTrigger className="px-2 text-[9px] data-[state=active]:bg-accent data-[state=active]:text-primary" value="versions">Versions</TabsTrigger>
        <TabsTrigger className="px-2 text-[9px] data-[state=active]:bg-accent data-[state=active]:text-primary" value="related">Related</TabsTrigger>
        <TabsTrigger className="gap-1 px-1 text-[9px]" value="ai" disabled title="Ask AI about this document – coming in Phase 2"><Sparkles size={10} />AI</TabsTrigger>
      </TabsList>
      <div className="px-5 pb-5">
        <TabsContent value="details"><DocumentDetails document={doc} reference={reference} /></TabsContent>
        <TabsContent value="permissions">
          <div className="rounded-md border bg-muted/30 p-3">
            <ShieldCheck size={22} className="mb-2 text-primary" />
            <p className="text-xs font-medium">{ACCESS_LABELS[doc.access.level]}</p>
            <p className="mt-1.5 text-[10px] text-muted-foreground">Default permission: Can {doc.access.defaultPermission}</p>
            <p className="mt-3 flex items-center gap-1.5 text-[9px] text-muted-foreground"><SyncIcon size={12} />Google sync: <span className="capitalize">{doc.access.syncStatus}</span></p>
          </div>
          <h3 className="mb-3 mt-5 text-[11px] font-medium">Who can access ({people.length})</h3>
          <div className="space-y-3">{people.map(person => <div className="flex items-center gap-2" key={person.id}>
            <Avatar name={person.name} color={person.color} size="sm" />
            <span className="flex-1 text-[10px]">{person.name}</span>
            <span className="text-[8px] text-muted-foreground">{person.id === doc.ownerId ? 'Owner' : person.role === 'guest' ? 'Guest' : 'Member'}</span>
          </div>)}</div>
          {canManage(user, doc) && <Button variant="outline" className="mt-5 w-full" onClick={() => ui.setPermissions({ kind: 'document', id: doc.id, name: doc.name })}><ShieldCheck />Manage permissions</Button>}
        </TabsContent>
        <TabsContent value="versions"><VersionHistory document={doc} reference={reference} /></TabsContent>
        <TabsContent value="related">
          <p className="mb-4 text-[10px] leading-relaxed text-muted-foreground">More knowledge with shared tags or in the same folder.</p>
          {related.error ? <ErrorState error={related.error} retry={() => void related.refetch()} /> : related.isPending ? <div className="space-y-3"><Skeleton className="h-14" /><Skeleton className="h-14" /></div> : !related.data?.length ? <EmptyState title="No related documents yet" description="Add tags to connect this document to your library." /> : related.data.map(item => <Link key={item.id} to={`/documents/${item.id}`} className="group flex items-center gap-2 border-b py-3">
            <DocumentIcon type={item.type} small />
            <span className="min-w-0 flex-1">
              <span className="block text-[10px] font-medium group-hover:text-primary">{item.name}</span>
              <span className="mt-1 block truncate text-[9px] text-muted-foreground">{item.tags.join(' · ')}</span>
            </span>
            <ArrowUpRight size={12} className="text-muted-foreground" />
          </Link>)}
        </TabsContent>
      </div>
    </Tabs>
    <div className="mx-5 mb-6 rounded-lg border border-dashed bg-muted/20 p-3.5">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground"><Sparkles size={12} />A little more intelligence</span>
        <LockKeyhole size={11} className="text-muted-foreground/60" />
      </div>
      <p className="my-3 text-[9px] leading-relaxed text-muted-foreground">Ask AI about this document — coming in Phase 2</p>
      <div className="grid grid-cols-2 gap-2">{['Summary', 'Key Takeaways', 'Keywords', 'Topics'].map(label => <div className="rounded border border-dashed px-2 py-2 text-[8px] text-muted-foreground/65" key={label}>{label}<span className="mt-2 block h-1 w-3/4 rounded-full bg-border" /></div>)}</div>
    </div>
  </aside>;
}
