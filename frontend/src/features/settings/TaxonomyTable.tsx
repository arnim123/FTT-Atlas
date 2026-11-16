import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Check, Loader2, Pencil, Plus, Search, Trash2, X } from 'lucide-react';
import { toast } from 'sonner';
import type { Taxonomy, TaxonomyKind } from '@/types';
import { deleteTaxonomy, listTaxonomy, saveTaxonomy } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useRefresh } from '@/hooks/use-data';
import { errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { EmptyState, ErrorState, Skeleton } from '@/components/shared/States';
export function TaxonomyTable({ kind }: {
  kind: TaxonomyKind;
}) {
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState<{
    id?: string;
    name: string;
    description: string;
  } | null>(null);
  const [deleting, setDeleting] = useState<Taxonomy | null>(null);
  const singular = kind === 'categories' ? 'category' : kind === 'departments' ? 'department' : 'tag';
  const entries = useQuery({ queryKey: ['taxonomy', kind, user.id], queryFn: () => listTaxonomy(kind, user) });
  const save = useMutation({ mutationFn: () => saveTaxonomy(kind, editing!, user), onSuccess: () => { setEditing(null); void refresh('taxonomy'); toast.success('Workspace updated'); }, onError: error => toast.error(errorMessage(error)) });
  const remove = useMutation({ mutationFn: () => deleteTaxonomy(kind, deleting!.id, user), onSuccess: () => { setDeleting(null); void refresh('taxonomy'); toast.success(`${singular[0].toUpperCase() + singular.slice(1)} deleted`); }, onError: error => toast.error(errorMessage(error)) });
  const filtered = entries.data?.filter(entry => `${entry.name} ${entry.description}`.toLowerCase().includes(query.toLowerCase()));
  const editor = <tr className="border-t bg-accent/30">
    <td className="px-5 py-3"><Input autoFocus aria-label={`${singular} name`} value={editing?.name ?? ''} maxLength={80} onChange={e => setEditing(prev => prev && ({ ...prev, name: e.target.value }))} placeholder={`New ${singular} name`} onKeyDown={e => {
      if (e.key === 'Enter' && editing?.name.trim())
        save.mutate(); if (e.key === 'Escape')
        setEditing(null);
    }} /></td>
    <td className="px-5 py-3"><Input aria-label={`${singular} description`} value={editing?.description ?? ''} maxLength={200} onChange={e => setEditing(prev => prev && ({ ...prev, description: e.target.value }))} placeholder="A short description" /></td>
    <td className="px-5 py-3">
      <div className="flex items-center gap-1">
        <Button size="icon" aria-label={`Save ${singular}`} disabled={!editing?.name.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? <Loader2 className="animate-spin" /> : <Check />}</Button>
        <Button size="icon" variant="ghost" aria-label="Cancel editing" onClick={() => setEditing(null)}><X /></Button>
      </div>
    </td>
  </tr>;
  return <>
    <div className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">
        <div className="relative min-w-48"><Search size={14} className="absolute left-3 top-2.5 text-muted-foreground" /><Input aria-label={`Search ${kind}`} placeholder={`Search ${kind}…`} value={query} onChange={e => setQuery(e.target.value)} className="w-full pl-9 sm:w-72" /></div>
        <Button size="sm" onClick={() => { setEditing({ name: '', description: '' }); setQuery(''); }} disabled={!!editing}><Plus />Add {singular}</Button>
      </div>
      {entries.error ? <div className="px-5"><ErrorState error={entries.error} retry={() => void entries.refetch()} /></div> : entries.isPending ? <div className="space-y-3 p-5" role="status" aria-label={`Loading ${kind}`}><Skeleton className="h-12" /><Skeleton className="h-12" /><Skeleton className="h-12" /></div> : !filtered?.length && !editing ? <EmptyState title={`No ${kind} found`} description={`Create a ${singular} or try a different search.`} action={<Button variant="outline" onClick={() => setEditing({ name: '', description: '' })}><Plus />Add {singular}</Button>} /> : <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-left">
          <thead className="table-head">
            <tr>
              <th className="w-[32%] px-5 py-3 font-medium">Name</th>
              <th className="px-5 py-3 font-medium">Description</th>
              <th className="w-28 px-5 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>{editing && !editing.id && editor}{filtered?.map(entry => editing?.id === entry.id ? <EditorRow key={entry.id}>{editor}</EditorRow> : <tr key={entry.id} className="border-t hover:bg-muted/30">
            <td className="px-5 py-4 text-xs font-medium">
              <span className="flex items-center gap-2">{kind === 'tags' ? <span className="text-muted-foreground">#</span> : <span className="h-2 w-2 rounded-full bg-primary/40" style={{ backgroundColor: entry.color }} />}{entry.name}</span>
            </td>
            <td className="px-5 py-4 text-[11px] text-muted-foreground">{entry.description || 'No description yet'}</td>
            <td className="px-5 py-4">
              <div className="flex items-center gap-1">
                <button className="icon-button h-7 w-7" aria-label={`Edit ${entry.name}`} onClick={() => setEditing(entry)} disabled={!!editing}><Pencil size={13} /></button>
                <button className="icon-button h-7 w-7 hover:text-destructive" aria-label={`Delete ${entry.name}`} onClick={() => setDeleting(entry)}><Trash2 size={13} /></button>
              </div>
            </td>
          </tr>)}</tbody>
        </table>
      </div>}
      <p className="border-t px-5 py-3 text-[9px] text-muted-foreground">{entries.data?.length ?? 0} {kind} · Changes apply across your workspace</p>
    </div>
    <Dialog open={!!deleting} onOpenChange={open => !open && setDeleting(null)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete “{deleting?.name}”?</DialogTitle>
          <DialogDescription>{kind === 'tags' ? 'This tag will also be removed from documents. The documents themselves will stay in your workspace.' : `This ${singular} can only be deleted when it is no longer in use. Reassign any linked items first.`}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate()}>{remove.isPending && <Loader2 className="animate-spin" />}Delete {singular}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </>;
}
function EditorRow({ children }: {
  children: React.ReactNode;
}) { return <>{children}</>; }
