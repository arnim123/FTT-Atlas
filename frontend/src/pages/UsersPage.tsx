import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { MoreHorizontal, Pencil, Search, UserCheck, UserPlus, UserX } from 'lucide-react';
import { toast } from 'sonner';
import type { User } from '@/types';
import { listTokens, listUsers, updateUser } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useReferenceData, useRefresh } from '@/hooks/use-data';
import { useDebounce } from '@/hooks/use-debounce';
import { isAdmin } from '@/lib/access';
import { ROLE_LABELS } from '@/lib/constants';
import { cn, errorMessage, formatDate } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Avatar } from '@/components/shared/Avatar';
import { EmptyState, ErrorState, PageSkeleton, Skeleton } from '@/components/shared/States';
import { PageHeading } from '@/components/shared/PageHeading';
import { UserDialog } from '@/features/users/UserDialog';
import { RoleMatrix } from '@/features/users/RoleMatrix';
import { integrationQuery } from '@/features/integrations/query';
export function UsersPage() {
  const actor = useAuthStore(s => s.user);
  const reference = useReferenceData();
  const refresh = useRefresh();
  const [query, setQuery] = useState('');
  const debounced = useDebounce(query);
  const [filters, setFilters] = useState({ role: '', departmentId: '', status: '' });
  const [dialog, setDialog] = useState<User | 'invite' | null>(null);
  const users = useQuery({ queryKey: ['users', actor.id, debounced, filters], queryFn: () => listUsers(actor, { ...filters, query: debounced }) });
  const tokens = useQuery({ queryKey: integrationQuery.tokens(actor.id, true), queryFn: () => listTokens(actor, { everyone: true }), enabled: isAdmin(actor) });
  const update = useMutation({ mutationFn: (target: User) => updateUser(target.id, { status: target.status === 'deactivated' ? 'active' : 'deactivated' }, actor), onSuccess: updated => { void refresh('users'); toast.success(`${updated.name} ${updated.status === 'active' ? 'reactivated' : 'deactivated'}`); }, onError: error => toast.error(errorMessage(error)) });
  const allowed = (target: User) => target.id !== actor.id && (actor.role === 'super_admin' || (actor.role === 'admin' ? !['admin', 'super_admin'].includes(target.role) : target.role === 'employee' && actor.departmentId === target.departmentId));
  if (reference.error)
    return <div className="page-container"><ErrorState error={reference.error} retry={() => void reference.refetch()} /></div>;
  if (!reference.data)
    return <PageSkeleton />;
  return <div className="page-container">
    <PageHeading title="The people behind the knowledge." description={actor.role === 'manager' ? 'Manage the people and access in your department.' : 'Bring your team together. Give everyone the right access.'} eyebrow="User management">
      <Button onClick={() => setDialog('invite')}><UserPlus />Invite user</Button>
    </PageHeading>
    <div className="panel overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b p-4">
        <div className="relative min-w-[220px] flex-1"><Search size={14} className="absolute left-3 top-2.5 text-muted-foreground" /><Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Find a teammate by name or email…" className="pl-9" aria-label="Search users" /></div>
        <select className="select-input w-36" value={filters.role} onChange={e => setFilters({ ...filters, role: e.target.value })} aria-label="Filter users by role">
          <option value="">All roles</option>
          {Object.entries(ROLE_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
        <select className="select-input w-40" value={actor.role === 'manager' ? actor.departmentId : filters.departmentId} disabled={actor.role === 'manager'} onChange={e => setFilters({ ...filters, departmentId: e.target.value })} aria-label="Filter users by department">
          <option value="">All departments</option>
          {reference.data.departments.map(dept => <option value={dept.id} key={dept.id}>{dept.name}</option>)}
        </select>
        <select className="select-input w-32" value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })} aria-label="Filter users by status">
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="invited">Invited</option>
          <option value="deactivated">Deactivated</option>
        </select>
      </div>
      {users.error ? <div className="px-5"><ErrorState error={users.error} retry={() => void users.refetch()} /></div> : users.isPending ? <div className="space-y-4 p-5" role="status" aria-label="Loading users">{[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-12" />)}</div> : !users.data.length ? <EmptyState search title="No teammates found" description="Try another name or adjust your filters." action={<Button variant="outline" onClick={() => { setQuery(''); setFilters({ role: '', departmentId: '', status: '' }); }}>Clear filters</Button>} /> : <div className="overflow-x-auto">
        <table className={cn('w-full text-left', isAdmin(actor) ? 'min-w-[860px]' : 'min-w-[720px]')}>
          <thead className="table-head">
            <tr>{['Team member', 'Role', 'Department', 'Status', 'Last active', ...(isAdmin(actor) ? ['API tokens'] : []), ''].map((label, i) => <th key={i} className="px-5 py-3 font-medium">{label || <span className="sr-only">Actions</span>}</th>)}</tr>
          </thead>
          <tbody>{users.data.map(person => <tr key={person.id} className="border-t hover:bg-muted/30">
            <td className="px-5 py-4">
              <div className="flex items-center gap-3">
                <Avatar name={person.name} color={person.color} />
                <div>
                  <p className="text-xs font-medium">{person.name}{person.accountType === 'bot' && <span className="ml-1.5 rounded border border-primary/20 bg-accent px-1.5 py-0.5 align-middle text-[8px] font-semibold uppercase tracking-wide text-primary">Bot</span>}{person.id === actor.id && <span className="ml-1.5 text-[9px] font-normal text-muted-foreground">(you)</span>}</p>
                  <p className="mt-1 text-[10px] text-muted-foreground">{person.email}</p>
                </div>
              </div>
            </td>
            <td className="px-5 py-4">
              <span className={cn('rounded border px-2 py-1 text-[10px]', ['admin', 'super_admin'].includes(person.role) ? 'border-primary/20 bg-accent text-primary' : 'text-muted-foreground')}>{ROLE_LABELS[person.role]}</span>
            </td>
            <td className="px-5 py-4 text-[11px] text-muted-foreground">{reference.data!.departments.find(d => d.id === person.departmentId)?.name}</td>
            <td className="px-5 py-4">
              <span className={cn('inline-flex items-center gap-1.5 text-[10px] capitalize', person.status === 'active' ? 'text-primary' : person.status === 'invited' ? 'text-amber-700 dark:text-amber-400' : 'text-muted-foreground')}><span className="h-1.5 w-1.5 rounded-full bg-current" />{person.status}</span>
            </td>
            <td className="px-5 py-4 text-[10px] text-muted-foreground">{person.status === 'invited' ? 'Not yet' : formatDate(person.lastActive)}</td>
            {isAdmin(actor) && <td className="px-5 py-4 text-[11px] text-muted-foreground">{tokens.isPending ? '…' : tokens.error ? '—' : tokens.data?.filter(token => token.userId === person.id).length ?? 0}</td>}
            <td className="pr-4">{allowed(person) && <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="icon-button" aria-label={`Manage ${person.name}`}><MoreHorizontal size={16} /></button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setDialog(person)}><Pencil />Edit role & department</DropdownMenuItem>
                <DropdownMenuItem disabled={update.isPending} onSelect={() => update.mutate(person)}>{person.status === 'deactivated' ? <UserCheck /> : <UserX />}{person.status === 'deactivated' ? 'Reactivate account' : 'Deactivate account'}</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>}</td>
          </tr>)}</tbody>
        </table>
      </div>}
      <div className="border-t px-5 py-3 text-[10px] text-muted-foreground">{users.data?.length ?? 0} team members · {actor.role === 'manager' ? 'Your department' : 'Acme Workspace'}</div>
    </div>
    <RoleMatrix />
    {dialog && <UserDialog key={typeof dialog === 'string' ? dialog : dialog.id} target={dialog === 'invite' ? undefined : dialog} reference={reference.data} close={() => setDialog(null)} />}
  </div>;
}
