import { ChevronDown, ChevronRight, FilePlus2, FolderPlus, Link2, Menu, Moon, Plus, Search, Sun, Upload, UserRound, LogOut } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Avatar } from '@/components/shared/Avatar';
import { Tooltip } from '@/components/ui/tooltip';
import { endSession } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useTheme } from '@/hooks/use-theme';
import { canCreate } from '@/lib/access';
import { ROLE_LABELS } from '@/lib/constants';
export function Topbar() {
  const user = useAuthStore(s => s.user);
  const signOut = useAuthStore(s => s.signOut);
  const ui = useUIStore();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const client = useQueryClient();
  const section = useLocation().pathname.split('/')[1] || 'dashboard';
  const logout = () => { void endSession().finally(() => { signOut(); client.clear(); navigate('/login'); }); };
  return <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between gap-3 border-b bg-card/95 px-5 backdrop-blur-md md:px-8 xl:px-10">


    <div className="flex min-w-0 items-center gap-3">
      <Button className="lg:hidden" size="icon" variant="ghost" aria-label="Open navigation" onClick={() => ui.setSidebarOpen(true)}><Menu /></Button>
      <div className="hidden items-center gap-2 text-[11px] text-muted-foreground sm:flex">
        <span>Workspace</span>
        <ChevronRight size={12} />
        <span className="font-medium capitalize text-foreground">{section === 'dashboard' ? 'Overview' : section}</span>
      </div>
    </div>


    <div className="flex items-center gap-2 sm:gap-3">
      <button onClick={() => ui.setCommandOpen(true)} className="flex h-8 items-center gap-2.5 rounded-md border bg-background/60 px-2.5 text-[11px] text-muted-foreground transition-colors hover:border-primary/30 sm:w-[230px] xl:w-[274px]" aria-label="Search workspace">
        <Search size={14} />
        <span className="hidden flex-1 text-left sm:block">Search anything...</span>
        <kbd className="hidden rounded border bg-card px-1 py-0.5 text-[9px] leading-none sm:inline">⌘ K</kbd>
      </button>


      {canCreate(user) && <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm"><Plus size={14} />New<ChevronDown className="!size-3" /></Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Add to your workspace</DropdownMenuLabel>
          <DropdownMenuItem onSelect={() => ui.setFolderDialog({ mode: 'create', parentId: 'root' })}><FolderPlus />New folder</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => ui.openAdd('create')}><FilePlus2 />New Google Doc</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => ui.openAdd('link')}><Link2 />Link Google Doc</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => ui.openAdd('upload')}><Upload />Upload file</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>}


      <span className="mx-1 hidden h-5 w-px bg-border sm:block" />
      <Tooltip content={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}>
        <Button variant="ghost" size="icon" onClick={toggle} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} className="text-muted-foreground">{theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}</Button>
      </Tooltip>


      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="flex items-center gap-2 rounded-md" aria-label="Open user menu"><Avatar name={user.name} color={user.color} size="sm" /><ChevronDown size={11} className="hidden text-muted-foreground sm:block" /></button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>
            <span className="block text-xs font-medium text-foreground">{user.name}</span>
            <span className="mt-1 block font-normal">{ROLE_LABELS[user.role]}</span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link to="/profile"><UserRound />Profile</Link>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={logout}><LogOut />Sign out</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>


    </div>


  </header>;
}
