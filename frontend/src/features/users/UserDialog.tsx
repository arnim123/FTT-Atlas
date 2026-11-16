import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation } from '@tanstack/react-query';
import { Loader2, UserPlus, UserRoundCog } from 'lucide-react';
import { toast } from 'sonner';
import type { ReferenceData, Role, User } from '@/types';
import { inviteUser, updateUser } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useRefresh } from '@/hooks/use-data';
import { ROLE_LABELS } from '@/lib/constants';
import { errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { FormField } from '@/components/shared/FormField';
const schema = z.object({ email: z.email('Enter a valid email address.'), role: z.enum(['super_admin', 'admin', 'manager', 'employee', 'guest']), departmentId: z.string().min(1, 'Select a department.'), accountType: z.enum(['person', 'bot']) });
export function UserDialog({ target, reference, close }: {
  target?: User;
  reference: ReferenceData;
  close: () => void;
}) {
  const actor = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { email: target?.email ?? '', role: target?.role ?? 'employee', departmentId: target?.departmentId ?? actor.departmentId, accountType: target?.accountType ?? 'person' } });
  const allowedRoles = (Object.keys(ROLE_LABELS) as Role[]).filter(role => actor.role === 'super_admin' || (actor.role === 'admin' ? !['super_admin', 'admin'].includes(role) : role === 'employee'));
  const accountType = form.watch('accountType');
  const role = form.watch('role');
  const mutation = useMutation({ mutationFn: (values: z.infer<typeof schema>) => target ? updateUser(target.id, { role: values.role, departmentId: values.departmentId }, actor) : inviteUser({ email: values.email, role: values.role, departmentId: values.departmentId, accountType: values.role === 'guest' ? 'person' : values.accountType }, actor), onSuccess: (_result, values) => { void refresh('users'); close(); toast.success(target ? 'Team member updated' : values.accountType === 'bot' && values.role !== 'guest' ? 'Service user added' : 'Invitation added', { description: target ? undefined : values.accountType === 'bot' && values.role !== 'guest' ? 'Bots have no Google login. Create an API token so this service user can connect. No email is sent.' : 'This is a mock invitation. No email is sent.' }); }, onError: error => toast.error(errorMessage(error)) });
  return <Dialog open onOpenChange={open => !open && !mutation.isPending && close()}>
    <DialogContent>
      <DialogHeader>
        {target ? <UserRoundCog size={25} className="mb-3 text-primary" /> : <UserPlus size={25} className="mb-3 text-primary" />}
        <DialogTitle>{target ? `Edit ${target.name}` : 'A little more knowledge, together.'}</DialogTitle>
        <DialogDescription>{target ? 'Update this teammate’s role and department.' : 'Invite a teammate to your company’s shared knowledge.'}</DialogDescription>
      </DialogHeader>
      <form onSubmit={form.handleSubmit(values => mutation.mutate(values))} className="space-y-4">
        <FormField label="Email address" htmlFor="invite-email" error={form.formState.errors.email?.message}><Input id="invite-email" type="email" autoFocus disabled={!!target} placeholder="teammate@company.com" {...form.register('email')} /></FormField>
        <FormField label="Role" htmlFor="invite-role" error={form.formState.errors.role?.message}>
          <select id="invite-role" className="select-input" {...form.register('role')}>{allowedRoles.map(role => <option key={role} value={role}>{ROLE_LABELS[role]}</option>)}</select>
        </FormField>
        <FormField label="Department" htmlFor="invite-department" error={form.formState.errors.departmentId?.message}>
          <select id="invite-department" className="select-input" {...form.register('departmentId')}>{reference.departments.filter(d => actor.role !== 'manager' || d.id === actor.departmentId).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
        </FormField>
        {role === 'guest' && <p className="rounded-md bg-amber-500/10 p-3 text-[10px] leading-relaxed text-amber-800 dark:text-amber-300">Guests can only access documents explicitly shared with them. A partner email address is allowed for Guest accounts.</p>}
        {!target && role !== 'guest' && <label className="flex items-start gap-3 rounded-md border p-3">
          <Checkbox className="mt-0.5" checked={accountType === 'bot'} onCheckedChange={checked => form.setValue('accountType', checked === true ? 'bot' : 'person')} aria-label="Invite as bot or service user" />
          <span>
            <span className="block text-xs font-medium">Invite as bot / service user</span>
            <span className="mt-1 block text-[10px] leading-relaxed text-muted-foreground">Bots have no Google login. They cannot use Sign in with Google and only reach the workspace through API tokens you create for them.</span>
          </span>
        </label>}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={close}>Cancel</Button>
          <Button disabled={mutation.isPending} type="submit">{mutation.isPending && <Loader2 className="animate-spin" />}{target ? 'Save changes' : 'Invite user'}</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}
