import { Command } from 'cmdk';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowUpRight, FileText, LayoutDashboard, CornerDownLeft, Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useUIStore } from '@/store/ui';
import { useAuthStore } from '@/store/auth';
import { useDebounce } from '@/hooks/use-debounce';
import { searchDocuments } from '@/api';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
export function CommandPalette() {
  const open = useUIStore(s => s.commandOpen);
  const setOpen = useUIStore(s => s.setCommandOpen);
  const user = useAuthStore(s => s.user);
  const [search, setSearch] = useState('');
  const query = useDebounce(search);
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ['palette', user.id, query], queryFn: () => searchDocuments(query, {}, user), enabled: open && !!query });
  useEffect(() => {
    if (!open)
      setSearch('');
  }, [open]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen(!useUIStore.getState().commandOpen);
      }
    }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, [setOpen]);
  const go = (path: string) => { navigate(path); setOpen(false); };
  const itemClass = 'flex cursor-pointer items-center gap-3 rounded-md px-3 py-3 text-xs data-[selected=true]:bg-accent data-[selected=true]:text-primary';
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogContent className="top-[22%] max-w-[600px] translate-y-0 overflow-hidden p-0">
      <DialogTitle className="sr-only">Search your workspace</DialogTitle>
      <DialogDescription className="sr-only">Find documents or navigate to a page. Use the arrow keys to select a result.</DialogDescription>
      <Command shouldFilter={false} loop>
        <div className="flex items-center gap-3 border-b px-5 py-4"><Search size={19} className="text-primary" /><Command.Input autoFocus value={search} onValueChange={setSearch} placeholder="Search your team's knowledge..." className="w-full bg-transparent pr-7 text-sm outline-none" aria-label="Search command" /></div>
        <Command.List className="max-h-[360px] overflow-y-auto p-2.5">{!search ? <Command.Group heading={<p className="eyebrow px-3 py-2">Jump to</p>}>{[{ label: 'Workspace overview', path: '/dashboard', icon: LayoutDashboard }, { label: 'Browse documents', path: '/documents', icon: FileText }, { label: 'Advanced search', path: '/search', icon: Search }].map(({ label, path, icon: Icon }) => <Command.Item key={path} onSelect={() => go(path)} className={itemClass}><Icon size={16} />{label}<ArrowUpRight size={13} className="ml-auto opacity-50" /></Command.Item>)}</Command.Group> : <>
          {isLoading || query !== search ? <div className="flex items-center justify-center gap-2 p-8 text-xs text-muted-foreground"><Loader2 className="animate-spin" size={16} />Searching your workspace…</div> : error ? <div role="alert" className="p-6 text-center text-xs">Search is temporarily unavailable. <button onClick={() => void refetch()} className="text-primary underline">Try again</button></div> : !data?.length ? <div className="p-8 text-center text-xs text-muted-foreground">No documents found. Try a different search.</div> : <Command.Group heading={<p className="eyebrow px-3 py-2">Documents</p>}>{data.slice(0, 6).map(({ document: doc }) => <Command.Item key={doc.id} value={doc.id} className={itemClass} onSelect={() => go(`/documents/${doc.id}`)}>
            <DocumentIcon type={doc.type} small />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{doc.name}</p>
              <p className="mt-1 truncate text-[10px] text-muted-foreground">{doc.description}</p>
            </div>
            <CornerDownLeft size={13} className="opacity-40" />
          </Command.Item>)}</Command.Group>}
          <Command.Item onSelect={() => go(`/search?q=${encodeURIComponent(search)}`)} className={itemClass}><Search size={15} />View all results for “{search}”<ArrowUpRight size={14} className="ml-auto" /></Command.Item>
        </>}</Command.List>
        <div className="flex justify-between border-t bg-muted/40 px-5 py-3 text-[9px] text-muted-foreground">
          <span>↑ ↓ to navigate · ↵ to open</span>
          <span>esc to close</span>
        </div>
      </Command>
    </DialogContent>
  </Dialog>;
}
