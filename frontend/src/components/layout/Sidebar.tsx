import { Archive, ArrowUpRight, BookOpen, ChevronDown, CircleHelp, FileText, Folder, LayoutDashboard, LockKeyhole, Plug, Search, Settings2, Users, X } from 'lucide-react';
import { NavLink, Link } from 'react-router-dom';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDashboard } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { isAdmin, canManageUsers, canUseIntegrations } from '@/lib/access';
import { cn } from '@/lib/utils';
import { Brand } from './Brand';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
export function Sidebar({ mobile = false }: {
  mobile?: boolean;
}) {
  const user = useAuthStore(s => s.user);
  const close = useUIStore(s => s.setSidebarOpen);
  const [help, setHelp] = useState(false);
  const { data } = useQuery({ queryKey: ['dashboard', user.id], queryFn: () => getDashboard(user) });
  const links = [{ to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' }, { to: '/documents', icon: FileText, label: 'Documents', count: data?.totalDocuments }, { to: '/search', icon: Search, label: 'Search' }, { to: '/archive', icon: Archive, label: 'Archive' }, ...(canUseIntegrations(user) ? [{ to: '/integrations', icon: Plug, label: 'Integrations' }] : [])];
  return <>
    <aside className={cn('flex h-full w-[224px] shrink-0 flex-col bg-card', !mobile && 'fixed inset-y-0 left-0 z-30 hidden border-r lg:flex')}>


      <div className="flex h-[76px] items-center justify-between px-6">
        <Link aria-label="Atlas home" to="/dashboard" onClick={() => close(false)}><Brand /></Link>
        {mobile && <Button variant="ghost" size="icon" aria-label="Close navigation" onClick={() => close(false)}><X /></Button>}
      </div>


      <div className="mx-4 mb-6 flex items-center gap-2.5 rounded-md border bg-background/70 p-2.5">
        <span className="grid h-7 w-7 place-items-center rounded border bg-card text-xs font-semibold">a<span className="sr-only">Acme</span></span>
        <div className="flex-1">
          <p className="text-[11px] font-semibold">Acme Workspace</p>
          <p className="mt-0.5 text-[9px] text-muted-foreground">Company knowledge</p>
        </div>
        <ChevronDown size={13} className="text-muted-foreground" aria-hidden="true" />
      </div>


      <nav aria-label="Main navigation" className="px-3">
        <p className="eyebrow mb-2.5 px-3">Workspace</p>
        <div className="space-y-1">{links.map(({ to, label, icon: Icon, count }) => <NavLink key={to} to={to} onClick={() => close(false)} className={({ isActive }) => cn('group flex h-10 items-center gap-3 rounded-md px-3 text-xs font-medium transition-colors', isActive ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
          <Icon size={17} strokeWidth={1.7} />
          <span className="flex-1">{label}</span>
          {count !== undefined && <span className="rounded bg-foreground/[.045] px-1.5 py-0.5 text-[9px] font-medium text-muted-foreground">{count}</span>}
        </NavLink>)}</div>


        {canManageUsers(user) && <div className="mt-6">
          <p className="eyebrow mb-2.5 px-3">Management</p>
          <NavLink to="/users" onClick={() => close(false)} className={({ isActive }) => cn('flex h-10 items-center gap-3 rounded-md px-3 text-xs font-medium', isActive ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted')}><Users size={17} strokeWidth={1.7} />Users</NavLink>
          {isAdmin(user) && <NavLink to="/settings" onClick={() => close(false)} className={({ isActive }) => cn('mt-1 flex h-10 items-center gap-3 rounded-md px-3 text-xs font-medium', isActive ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted')}><Settings2 size={17} strokeWidth={1.7} />Settings</NavLink>}
        </div>}


        <div className="mt-7">
          <div className="mb-2.5 flex items-center justify-between px-3">
            <p className="eyebrow">Quick access</p>
            <BookOpen size={12} className="text-muted-foreground/60" />
          </div>
          {[{ name: 'People & Culture', id: 'hr', color: 'text-[#a39a7a]' }, { name: 'Product resources', id: 'products', color: 'text-[#63937b]' }, { name: 'Sales enablement', id: 'sales', color: 'text-[#899bb0]' }].map(folder => <Link key={folder.id} to={`/documents?folder=${folder.id}`} onClick={() => close(false)} className="flex h-9 items-center gap-3 rounded-md px-3 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"><Folder size={15} className={folder.color} fill="currentColor" fillOpacity={0.13} strokeWidth={1.6} />{folder.name}</Link>)}
        </div>


      </nav>


      <div className="mt-auto px-4 pb-5 pt-8">
        <div className="knowledge-pattern rounded-lg border border-primary/10 bg-accent/40 p-3.5">
          <BookOpen size={18} className="mb-2.5 text-primary" strokeWidth={1.5} />
          <p className="text-[11px] font-semibold">Good knowledge travels.</p>
          <p className="mt-1.5 text-[10px] leading-relaxed text-muted-foreground">Make it easy for your team to find what matters.</p>
          <Link to="/documents" onClick={() => close(false)} className="mt-3 flex items-center gap-1.5 text-[10px] font-medium text-primary">Explore your library<ArrowUpRight size={12} /></Link>
        </div>
        <button onClick={() => setHelp(true)} className="mt-5 flex w-full items-center gap-2.5 px-2 text-[11px] text-muted-foreground hover:text-foreground"><CircleHelp size={15} />Help & shortcuts<span className="ml-auto rounded border px-1 text-[9px]">?</span></button>
        <div className="mt-4 flex items-center gap-1.5 border-t px-2 pt-4 text-[9px] text-muted-foreground"><LockKeyhole size={10} />Your knowledge. Securely connected.</div>
      </div>


    </aside>
    <Dialog open={help} onOpenChange={setHelp}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>A little help, whenever you need it.</DialogTitle>
          <DialogDescription>Find your way around the Atlas workspace.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-xs">
          <p><kbd className="mr-2 rounded border bg-muted px-2 py-1">⌘ / Ctrl + K</kbd>Search your entire workspace.</p>
          <p><kbd className="mr-2 rounded border bg-muted px-2 py-1">Esc</kbd>Close the current dialog or search palette.</p>
          <p><kbd className="mr-2 rounded border bg-muted px-2 py-1">Tab</kbd>Move between interactive controls.</p>
          <p className="border-t pt-4 leading-relaxed text-muted-foreground">Drag documents onto folders to organize your library. You can also use the Move action in any item menu. Permissions determine what each teammate can view and edit.</p>
          <p className="text-muted-foreground">Need access? Contact <a className="text-primary underline" href="mailto:knowledge@company.com">knowledge@company.com</a>.</p>
        </div>
      </DialogContent>
    </Dialog>
  </>;
}
