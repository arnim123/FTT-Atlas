import { Check, Minus, ShieldCheck } from 'lucide-react';
import { ROLE_LABELS } from '@/lib/constants';
import type { Role } from '@/types';
const capabilities: {
  role: Role;
  scope: string;
  create: boolean;
  users: string;
  settings: boolean;
}[] = [
    { role: 'super_admin', scope: 'All documents', create: true, users: 'All roles', settings: true },
    { role: 'admin', scope: 'All documents', create: true, users: 'Non-admin roles', settings: true },
    { role: 'manager', scope: 'Accessible documents', create: true, users: 'Own department', settings: false },
    { role: 'employee', scope: 'Accessible documents', create: true, users: '—', settings: false },
    { role: 'guest', scope: 'Explicitly shared', create: false, users: '—', settings: false },
  ];
export function RoleMatrix() {
  return <section className="panel mt-6 overflow-hidden">
    <div className="flex items-center gap-2 border-b px-5 py-4">
      <ShieldCheck size={15} className="text-primary" />
      <h2 className="text-xs font-semibold">A role for everyone</h2>
      <span className="ml-auto text-[9px] text-muted-foreground">Your workspace capability guide</span>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px] text-left text-[10px]">
        <thead className="table-head">
          <tr>{['Role', 'Document scope', 'Create documents', 'Manage users', 'Workspace settings'].map(label => <th className="px-5 py-3 font-medium" key={label}>{label}</th>)}</tr>
        </thead>
        <tbody>{capabilities.map(row => <tr key={row.role} className="border-t">
          <th className="px-5 py-3 font-medium">{ROLE_LABELS[row.role]}</th>
          <td className="px-5 py-3 text-muted-foreground">{row.scope}</td>
          <td className="px-5 py-3">{row.create ? <Check size={13} className="text-primary" aria-label="Allowed" /> : <Minus size={13} className="text-muted-foreground" aria-label="Not allowed" />}</td>
          <td className="px-5 py-3 text-muted-foreground">{row.users}</td>
          <td className="px-5 py-3">{row.settings ? <Check size={13} className="text-primary" aria-label="Allowed" /> : <Minus size={13} className="text-muted-foreground" aria-label="Not allowed" />}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className="border-t bg-muted/20 px-5 py-3 text-[9px] leading-relaxed text-muted-foreground">Document owners manage their own content. Managers manage accessible content in their department. Only administrators can permanently delete items. Custom grants control Guest access.</p>
  </section>;
}
