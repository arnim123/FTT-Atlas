import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { DndContext, DragOverlay, KeyboardSensor, PointerSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core';
import { ArrowDownWideNarrow, CheckCheck, ChevronLeft, ChevronRight, FolderTree as FolderTreeIcon, LayoutGrid, List, Plus, Search, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';
import { bulkDocuments, listDocuments, updateFolder } from '@/api';
import type { Document, DocumentFilters as Filters, Folder } from '@/types';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useFolders, useReferenceData, useRefresh } from '@/hooks/use-data';
import { useDebounce } from '@/hooks/use-debounce';
import { canCreate } from '@/lib/access';
import { cn, errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { PageHeading } from '@/components/shared/PageHeading';
import { EmptyState, ErrorState, PageSkeleton, Skeleton } from '@/components/shared/States';
import { Breadcrumbs } from '@/features/folders/Breadcrumbs';
import { FolderTree } from '@/features/folders/FolderTree';
import { DocumentTable } from '@/features/documents/DocumentTable';
import { DocumentGrid } from '@/features/documents/DocumentGrid';
import { DocumentFilters } from '@/features/documents/DocumentFilters';
import { BulkToolbar } from '@/features/documents/BulkToolbar';
export function DocumentsPage() {
  const [params, setParams] = useSearchParams();
  const folderId = params.get('folder') ?? 'root';
  const user = useAuthStore(s => s.user);
  const ui = useUIStore();
  const refresh = useRefresh();
  const client = useQueryClient();
  const reference = useReferenceData();
  const folders = useFolders();
  const [filters, setFilters] = useState<Filters>({ sort: 'modified' });
  const [query, setQuery] = useState('');
  const debounced = useDebounce(query);
  const [view, setView] = useState<'list' | 'grid'>('list');
  const [filterOpen, setFilterOpen] = useState(false);
  const [treeOpen, setTreeOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dragged, setDragged] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }), useSensor(KeyboardSensor));
  const docs = useQuery({ queryKey: ['documents', user.id, folderId, filters, debounced], queryFn: () => listDocuments(user, { ...filters, folderId, query: debounced }) });
  useEffect(() => { setSelected(new Set()); setPage(1); }, [folderId, filters, debounced, user.id]);
  useEffect(() => {
    if (docs.data)
      setSelected(prev => new Set([...prev].filter(id => docs.data.some(d => d.id === id))));
  }, [docs.data]);
  useEffect(() => {
    if (docs.data)
      setPage(prev => Math.min(prev, Math.max(1, Math.ceil(docs.data.length / (view === 'list' ? 12 : 9)))));
  }, [docs.data, view]);
  const move = useMutation({
    mutationFn: async ({ active, over }: DragEndEvent) => {
      if (!over) return;
      const [kind, id] = String(active.id).split(':');
      const destination = String(over.id).replace('drop:', '');
      if (kind === 'document') await bulkDocuments(selected.has(id) ? [...selected] : [id], 'move', user, destination);
      else await updateFolder(id, { parentId: destination }, user);
    },
    onMutate: async ({ active, over }) => {
      if (!over) return;
      await client.cancelQueries({ queryKey: ['documents'] });
      await client.cancelQueries({ queryKey: ['folders'] });
      const documents = client.getQueriesData<Document[]>({ queryKey: ['documents'] });
      const folderRows = client.getQueriesData<Folder[]>({ queryKey: ['folders'] });
      const [kind, id] = String(active.id).split(':');
      const destination = String(over.id).replace('drop:', '');
      if (kind === 'document') {
        const ids = selected.has(id) ? selected : new Set([id]);
        client.setQueriesData<Document[]>({ queryKey: ['documents'] }, current => current?.map(doc => ids.has(doc.id) ? { ...doc, folderId: destination } : doc));
      } else {
        client.setQueriesData<Folder[]>({ queryKey: ['folders'] }, current => current?.map(folder => folder.id === id ? { ...folder, parentId: destination } : folder));
      }
      return { documents, folders: folderRows };
    },
    onError: (error, _event, context) => {
      context?.documents.forEach(([key, data]) => client.setQueryData(key, data));
      context?.folders.forEach(([key, data]) => client.setQueryData(key, data));
      toast.error(errorMessage(error));
    },
    onSuccess: () => { void refresh(); setSelected(new Set()); toast.success('Moved to folder'); },
  });
  const retry = () => { void docs.refetch(); void reference.refetch(); void folders.refetch(); };
  if (reference.error || folders.error)
    return <div className="page-container"><ErrorState error={reference.error ?? folders.error} retry={retry} /></div>;
  if (!reference.data || !folders.data)
    return <PageSkeleton />;
  const currentFolder = folders.data.find(f => f.id === folderId);
  const pageSize = view === 'list' ? 12 : 9;
  const pageCount = Math.ceil((docs.data?.length ?? 0) / pageSize);
  const paged = docs.data?.slice((page - 1) * pageSize, page * pageSize) ?? [];
  const toggle = (id: string) => setSelected(prev => {
    const next = new Set(prev); if (next.has(id))
      next.delete(id);
    else
      next.add(id); return next;
  });
  const toggleAll = () => setSelected(selected.size === docs.data?.length ? new Set() : new Set(docs.data?.map(d => d.id)));
  const selectFolder = (id: string) => { setParams(id === 'root' ? {} : { folder: id }); setTreeOpen(false); };
  return <div className="page-container">
    <PageHeading title="Your knowledge, organized." description="One shared library. Everything you need to do your best work." eyebrow="Documents">{canCreate(user) && <Button onClick={() => ui.openAdd('upload', folderId)}><Plus />Add document</Button>}</PageHeading>
    <DndContext sensors={sensors} onDragStart={event => setDragged(String(event.active.data.current.name ?? 'Item'))} onDragEnd={event => {
      setDragged(null); if (event.over)
        move.mutate(event);
    }} onDragCancel={() => setDragged(null)}>
      <div className="panel flex min-h-[690px] overflow-hidden">
        <FolderTree folders={folders.data} selected={folderId} select={selectFolder} className={cn('w-[215px] shrink-0', treeOpen ? 'flex' : 'hidden xl:flex')} />
        <section className={cn('min-w-0 flex-1', treeOpen && 'hidden sm:block')}>


          <div className="flex h-14 items-center justify-between gap-3 border-b px-4">
            <div className="flex min-w-0 items-center gap-2">
              <Button variant="ghost" size="icon" className="xl:hidden" onClick={() => setTreeOpen(!treeOpen)} aria-label="Toggle folder tree"><FolderTreeIcon /></Button>
              <Breadcrumbs folders={folders.data} folderId={folderId} />
            </div>
            <span className="hidden items-center gap-1.5 whitespace-nowrap text-[9px] text-muted-foreground md:flex"><CheckCheck size={12} className="text-primary" />All changes saved</span>
          </div>


          <div className="flex flex-wrap items-center justify-between gap-3 px-4 pb-4 pt-5">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold">{folderId === 'root' ? 'All documents' : currentFolder?.name ?? 'Folder not found'}</h2>
              <span className="rounded-full bg-muted px-2 py-0.5 text-[9px] text-muted-foreground">{docs.data?.length ?? '…'}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="flex rounded-md border p-0.5">
                <Button className={cn('h-6 w-6', view === 'list' && 'bg-muted')} variant="ghost" size="icon" aria-label="List view" aria-pressed={view === 'list'} onClick={() => { setView('list'); setPage(1); }}><List className="!size-3.5" /></Button>
                <Button className={cn('h-6 w-6', view === 'grid' && 'bg-muted')} variant="ghost" size="icon" aria-label="Grid view" aria-pressed={view === 'grid'} onClick={() => { setView('grid'); setPage(1); }}><LayoutGrid className="!size-3.5" /></Button>
              </div>
            </div>
          </div>


          <div className="flex flex-wrap items-center gap-2 border-b px-4 pb-4">
            <div className="relative min-w-[150px] flex-1"><Search size={13} className="absolute left-2.5 top-2.5 text-muted-foreground" /><Input className="h-8 pl-8 text-[10px]" placeholder="Search in this folder..." value={query} onChange={e => setQuery(e.target.value)} aria-label="Search documents in folder" /></div>
            <Button size="sm" variant="outline" className={cn(filterOpen && 'border-primary/30 bg-accent text-primary')} onClick={() => setFilterOpen(!filterOpen)} aria-expanded={filterOpen}><SlidersHorizontal className="!size-3" />Filters{Object.keys(filters).filter(k => k !== 'sort' && filters[k as keyof Filters]).length > 0 && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}</Button>
            <div className="flex items-center gap-1 rounded-md border bg-card pl-2">
              <ArrowDownWideNarrow size={12} className="text-muted-foreground" />
              <select className="h-[30px] max-w-[135px] rounded bg-transparent pr-2 text-[10px]" aria-label="Sort documents" value={filters.sort} onChange={e => setFilters({ ...filters, sort: e.target.value as Filters['sort'] })}>
                <option value="modified">Last modified</option>
                <option value="name">Name A–Z</option>
                <option value="views">Most viewed</option>
                <option value="oldest">Oldest first</option>
              </select>
            </div>
          </div>


          {filterOpen && <DocumentFilters filters={filters} onChange={setFilters} reference={reference.data} />}
          {selected.size > 0 && <BulkToolbar selected={docs.data?.filter(d => selected.has(d.id)) ?? []} clear={() => setSelected(new Set())} />}


          {docs.error ? <div className="px-4"><ErrorState error={docs.error} retry={() => void docs.refetch()} /></div> : docs.isPending ? <div className="space-y-4 p-5" role="status" aria-label="Loading documents">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div> : !currentFolder ? <EmptyState title="This folder is no longer available" description="It may have been archived or deleted." action={<Button onClick={() => selectFolder('root')}>Back to all documents</Button>} /> : !docs.data?.length ? <EmptyState title={query || Object.keys(filters).length > 1 ? 'No documents match these filters' : 'Room for something useful'} description="Try a different filter, or add the first document to this folder." search={!!query} action={canCreate(user) && <Button onClick={() => ui.openAdd('upload', folderId)}><Plus />Add document</Button>} /> : view === 'list' ? <DocumentTable documents={paged} reference={reference.data} selected={selected} toggle={toggle} toggleAll={toggleAll} /> : <DocumentGrid documents={paged} reference={reference.data} selected={selected} toggle={toggle} />}


          {!!docs.data?.length && <div className="flex items-center justify-between gap-3 border-t px-4 py-3.5">
            <p className="text-[9px] text-muted-foreground">Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, docs.data.length)} of {docs.data.length} documents</p>
            <div className="flex items-center gap-1.5">
              <Button variant="outline" size="icon" className="h-6 w-6" disabled={page <= 1} onClick={() => setPage(p => p - 1)} aria-label="Previous page"><ChevronLeft className="!size-3" /></Button>
              <span className="px-1 text-[9px] text-muted-foreground">{page} / {pageCount}</span>
              <Button variant="outline" size="icon" className="h-6 w-6" disabled={page >= pageCount} onClick={() => setPage(p => p + 1)} aria-label="Next page"><ChevronRight className="!size-3" /></Button>
            </div>
          </div>}


        </section>
      </div>
      <DragOverlay>{dragged && <div className="rounded-lg border bg-card px-4 py-3 text-xs shadow-popover">Moving {dragged}</div>}</DragOverlay>
    </DndContext>
  </div>;
}
