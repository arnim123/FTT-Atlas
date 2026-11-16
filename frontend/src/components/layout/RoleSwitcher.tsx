import { useState } from 'react';
import { FlaskConical, Loader2, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { getRoleIdentity, simulateNextError } from '@/api';
import { ROLE_LABELS } from '@/lib/constants';
import { errorMessage } from '@/lib/utils';
import type { Role } from '@/types';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
export function RoleSwitcher() {
  const { user, setUser } = useAuthStore();
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const location = useLocation();
  function simulateError() {
    const section = location.pathname.split('/')[1];
    const key = section === 'documents' ? (location.pathname.split('/')[2] ? 'document' : 'documents') : section === 'settings' ? 'taxonomy' : section;
    const active = client.getQueryCache().findAll({ type: 'active' });
    const query = active.find(q => q.queryKey[0] === key) ?? active.find(q => q.queryKey[0] === 'reference');
    if (query) {
      simulateNextError();
      void client.invalidateQueries({ queryKey: query.queryKey, exact: true });
      toast.info('Simulating one failed request. Use Try again to recover.');
    }
  }
  if (!import.meta.env.DEV || import.meta.env.VITE_ENABLE_TEST_LOGIN !== 'true')
    return null;
  async function switchRole(role: Role) {
    setBusy(true); try {
      const identity = await getRoleIdentity(role);
      await client.cancelQueries();
      client.clear();
      useUIStore.setState({ addDocument: null, permissions: null, folderDialog: null, moveTargets: [], itemAction: null, commandOpen: false });
      setUser(identity);
      toast.success(`Viewing as ${ROLE_LABELS[role]}`, { description: identity.name });
    }
      catch (error) {
        toast.error(errorMessage(error));
      }
      finally {
      setBusy(false);
    }
  }
  return <div className="fixed bottom-3 right-4 z-40 flex h-9 items-center gap-2 rounded-full border bg-card/95 pl-3 pr-2 shadow-popover backdrop-blur">
    <span className="text-primary">{busy ? <Loader2 size={13} className="animate-spin" /> : <FlaskConical size={13} />}</span>
    <label htmlFor="view-role" className="text-[9px] text-muted-foreground">View as</label>
    <select id="view-role" aria-label="View as role" className="max-w-[140px] cursor-pointer rounded bg-transparent py-1 text-[10px] font-medium outline-none" value={user.role} disabled={busy} onChange={e => switchRole(e.target.value as Role)}>{Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="rounded-full p-1 text-muted-foreground" aria-label="Demo tools"><ChevronDown size={12} /></button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={simulateError}>Simulate an API error</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  </div>;
}
