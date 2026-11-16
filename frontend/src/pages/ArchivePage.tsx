import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Archive, Folder, RotateCcw, Search, Trash2 } from 'lucide-react';
import { listArchived } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useReferenceData } from '@/hooks/use-data';
import { isAdmin } from '@/lib/access';
import { formatDate } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { EmptyState, ErrorState, PageSkeleton } from '@/components/shared/States';
import { PageHeading } from '@/components/shared/PageHeading';
export function ArchivePage() {
  const user = useAuthStore(s => s.user);
  const ui = useUIStore();
  const reference = useReferenceData();
  const [query, setQuery] = useState('');
  const items = useQuery({ queryKey: ['archive', user.id], queryFn: () => listArchived(user) });
  if (items.error || reference.error)
    return <div className="page-container"><ErrorState error={items.error ?? reference.error} retry={() => { void items.refetch(); void reference.refetch(); }} /></div>;
  if (!items.data || !reference.data)
    return <PageSkeleton />;
  const filtered = items.data.filter(item => item.name.toLowerCase().includes(query.toLowerCase()));
  return <div className="page-container">
    <PageHeading title="Out of the way. Still within reach." description="A home for knowledge you’re not using right now. Restore it whenever you need it." eyebrow="Archive" />
    <div className="mb-5 flex items-start gap-3 rounded-lg border bg-card px-5 py-4">
      <Archive size={17} className="shrink-0 text-primary" />
      <p className="text-[11px] leading-relaxed text-muted-foreground">Archived documents keep their versions and permissions. Restoring them puts them back in their original folder.{isAdmin(user) && ' Only administrators can permanently delete items.'}</p>
    </div>
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between gap-4 border-b p-4">
        <h2 className="text-xs font-semibold">Archived items <span className="ml-1.5 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{items.data.length}</span></h2>
        <div className="relative w-full max-w-64"><Search size={13} className="absolute left-2.5 top-2.5 text-muted-foreground" /><Input className="pl-8" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search archive…" aria-label="Search archive" /></div>
      </div>
      {!filtered.length ? <EmptyState title={query ? 'No archived items match' : 'Nothing tucked away yet'} description={query ? 'Try another search term.' : 'Items you archive will appear here. Your active library is in Documents.'} /> : <div className="overflow-x-auto">
        <table className="w-full min-w-[650px] text-left">
          <thead className="table-head">
            <tr>{['Name', 'Department', 'Owner', 'Last modified', 'Actions'].map(label => <th key={label} className="px-5 py-3 font-medium">{label}</th>)}</tr>
          </thead>
          <tbody>{filtered.map(item => <tr key={item.id} className="border-t hover:bg-muted/30">
            <td className="px-5 py-4">
              <div className="flex items-center gap-3">
                {item.type ? <DocumentIcon type={item.type} small /> : <Folder size={22} className="text-primary" />}
                <div>
                  <p className="text-xs font-medium">{item.name}</p>
                  <p className="mt-1 text-[9px] capitalize text-muted-foreground">{item.kind}</p>
                </div>
              </div>
            </td>
            <td className="px-5 py-4 text-[10px] text-muted-foreground">{reference.data!.departments.find(d => d.id === item.departmentId)?.name}</td>
            <td className="px-5 py-4 text-[10px] text-muted-foreground">{reference.data!.users.find(u => u.id === item.ownerId)?.name}</td>
            <td className="px-5 py-4 text-[10px] text-muted-foreground">{item.modifiedAt ? formatDate(item.modifiedAt, true) : '—'}</td>
            <td className="px-5 py-4">
              <div className="flex items-center gap-1.5">
                <Button variant="outline" size="sm" onClick={() => ui.setItemAction({ action: 'restore', targets: [item] })}><RotateCcw className="!size-3" />Restore</Button>
                {isAdmin(user) && <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive" aria-label={`Delete permanently ${item.name}`} onClick={() => ui.setItemAction({ action: 'delete', targets: [item] })}><Trash2 className="!size-3.5" /></Button>}
              </div>
            </td>
          </tr>)}</tbody>
        </table>
      </div>}
    </div>
  </div>;
}
