import { Building2, Globe2, LockKeyhole, Plus, ShieldAlert, Users, X } from 'lucide-react';
import type { Access, AccessLevel, Permission, ReferenceData } from '@/types';
import { Button } from '@/components/ui/button';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { canView } from '@/lib/access';
import { Avatar } from '@/components/shared/Avatar';
const levels: {
  value: AccessLevel;
  label: string;
  description: string;
  icon: typeof Users;
}[] = [
    { value: 'private', label: 'Private', description: 'Only you and administrators', icon: LockKeyhole },
    { value: 'department', label: 'Department', description: 'People in this department', icon: Building2 },
    { value: 'organization', label: 'Organization-wide', description: 'Everyone in your company', icon: Globe2 },
    { value: 'custom', label: 'Custom', description: 'Specific people and teams', icon: Users },
  ];
export function AccessPicker({ value, onChange, reference, ownerId, departmentId, compact = false }: {
  value: Access;
  onChange: (access: Access) => void;
  reference: ReferenceData;
  ownerId: string;
  departmentId: string;
  compact?: boolean;
}) {
  const [principal, setPrincipal] = useState('');
  const [permission, setPermission] = useState<Permission>('view');
  const resource = { access: value, ownerId, departmentId };
  const people = reference.users.filter(u => canView(u, resource));
  const hasGuest = value.level === 'custom' && value.grants.some(g => g.principalType === 'user' && reference.users.find(u => u.id === g.principalId)?.role === 'guest');
  function addPrincipal() {
    if (!principal)
      return; const [principalType, principalId] = principal.split(':') as [
        'user' | 'department',
        string
      ]; if (!value.grants.some(g => g.principalType === principalType && g.principalId === principalId))
      onChange({ ...value, grants: [...value.grants, { principalType, principalId, permission }] }); setPrincipal('');
  }
  return <div className="space-y-4">
    <fieldset>
      <legend className="field-label">General access</legend>
      <div className="grid grid-cols-2 gap-2">{levels.map(({ value: level, label, description, icon: Icon }) => <label key={level} className={cn('relative flex cursor-pointer gap-2.5 rounded-md border p-3 transition-colors', level === value.level ? 'border-primary/50 bg-accent/70' : 'hover:bg-muted/50')}>
        <input type="radio" name={`access-${ownerId}`} value={level} checked={value.level === level} onChange={() => onChange({ ...value, level })} className="sr-only peer" />
        <Icon size={16} className={cn('mt-0.5 shrink-0', level === value.level ? 'text-primary' : 'text-muted-foreground')} />
        <span>
          <span className="block text-[11px] font-medium">{label}</span>
          <span className="mt-1 block text-[9px] leading-relaxed text-muted-foreground">{description}</span>
        </span>
        <span className="pointer-events-none absolute inset-0 rounded-md peer-focus-visible:ring-2 peer-focus-visible:ring-ring" />
      </label>)}</div>
    </fieldset>


    {value.level !== 'private' && value.level !== 'custom' && <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2">
      <div>
        <label htmlFor="default-access" className="text-[11px] font-medium">Default access</label>
        <p className="mt-0.5 text-[9px] text-muted-foreground">What people with access can do</p>
      </div>
      <select id="default-access" className="select-input w-24" value={value.defaultPermission} onChange={e => onChange({ ...value, defaultPermission: e.target.value as Permission })}>
        <option value="view">Can view</option>
        <option value="edit">Can edit</option>
      </select>
    </div>}


    {value.level === 'custom' && <div className="space-y-2">
      <label htmlFor="add-principal" className="field-label">Add people or departments</label>
      <div className="flex gap-1.5">
        <select id="add-principal" className="select-input flex-1" value={principal} onChange={e => setPrincipal(e.target.value)}>
          <option value="">Select a person or team</option>
          <optgroup label="People">{reference.users.filter(u => u.status !== 'deactivated' && u.id !== ownerId).map(u => <option key={u.id} value={`user:${u.id}`}>{u.name}{u.role === 'guest' ? ' (Guest)' : ''}</option>)}</optgroup>
          <optgroup label="Departments">{reference.departments.map(d => <option key={d.id} value={`department:${d.id}`}>{d.name}</option>)}</optgroup>
        </select>
        <select className="select-input w-24" aria-label="New principal permission" value={permission} onChange={e => setPermission(e.target.value as Permission)}>
          <option value="view">Can view</option>
          <option value="edit">Can edit</option>
        </select>
        <Button size="icon" variant="outline" onClick={addPrincipal} type="button" disabled={!principal} aria-label="Add principal"><Plus /></Button>
      </div>
      {value.grants.map((grant, index) => <div key={`${grant.principalType}-${grant.principalId}`} className="flex items-center gap-2 rounded border bg-muted/20 p-2">
        <span className="flex-1 text-[10px]">{grant.principalType === 'user' ? reference.users.find(u => u.id === grant.principalId)?.name : reference.departments.find(d => d.id === grant.principalId)?.name}</span>
        <select className="select-input h-7 w-24" aria-label={`Permission for ${grant.principalId}`} value={grant.permission} onChange={e => onChange({ ...value, grants: value.grants.map((g, i) => i === index ? { ...g, permission: e.target.value as Permission } : g) })}>
          <option value="view">Can view</option>
          <option value="edit">Can edit</option>
        </select>
        <button type="button" onClick={() => onChange({ ...value, grants: value.grants.filter((_, i) => i !== index) })} className="icon-button h-6 w-6" aria-label="Remove access"><X size={12} /></button>
      </div>)}
    </div>}


    {hasGuest && <div className="flex gap-2 rounded-md border border-amber-500/25 bg-amber-500/10 p-3 text-[10px] leading-relaxed text-amber-800 dark:text-amber-300" role="status">
      <ShieldAlert size={16} className="shrink-0" />
      <span>This document will be shared with a Guest outside your company. Make sure it is appropriate to share externally.</span>
    </div>}


    <div className="border-t pt-4">
      <h3 className="text-[11px] font-medium">Who can access <span className="text-muted-foreground">({people.length})</span></h3>
      <div className={cn('mt-3 space-y-3 overflow-y-auto', compact ? 'max-h-28' : 'max-h-44')}>{people.map(person => <div className="flex items-center gap-2.5" key={person.id}>
        <Avatar name={person.name} color={person.color} size="sm" />
        <div className="flex-1">
          <p className="text-[10px] font-medium">{person.name}{person.role === 'guest' && <span className="ml-1.5 tag">Guest</span>}</p>
          {!compact && <p className="mt-0.5 text-[9px] text-muted-foreground">{person.email}</p>}
        </div>
        <span className="text-[9px] text-muted-foreground">{person.id === ownerId ? 'Owner' : ['admin', 'super_admin'].includes(person.role) ? 'Admin' : 'Member'}</span>
      </div>)}</div>
    </div>


  </div>;
}
