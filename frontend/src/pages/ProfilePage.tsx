import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { CheckCheck, LogOut, Moon, ShieldCheck, Sun } from 'lucide-react';
import { endSession, getProfile } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useReferenceData } from '@/hooks/use-data';
import { useTheme } from '@/hooks/use-theme';
import { ROLE_LABELS } from '@/lib/constants';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar } from '@/components/shared/Avatar';
import { GoogleLogo } from '@/components/shared/GoogleLogo';
import { ErrorState, PageSkeleton } from '@/components/shared/States';
import { PageHeading } from '@/components/shared/PageHeading';
export function ProfilePage() {
  const { user, signOut } = useAuthStore();
  const reference = useReferenceData();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const client = useQueryClient();
  const profile = useQuery({ queryKey: ['profile', user.id], queryFn: () => getProfile(user) });
  if (profile.error || reference.error)
    return <div className="page-container"><ErrorState error={profile.error ?? reference.error} retry={() => { void profile.refetch(); void reference.refetch(); }} /></div>;
  if (!profile.data || !reference.data)
    return <PageSkeleton rows={3} />;
  const person = profile.data;
  return <div className="page-container">
    <PageHeading title="Your corner of the workspace." description="A few details about you and how you connect with your team." eyebrow="My profile" />
    <div className="grid max-w-[1040px] grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
      <section className="panel p-6">
        <div className="flex items-center gap-5 border-b pb-6">
          <Avatar name={person.name} color={person.color} size="lg" />
          <div>
            <h2 className="text-xl font-semibold tracking-tight">{person.name}</h2>
            <p className="mt-1.5 text-xs text-muted-foreground">{person.email}</p>
            <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-accent px-2.5 py-1 text-[10px] text-primary"><ShieldCheck size={11} />{ROLE_LABELS[person.role]}</span>
          </div>
        </div>
        <div className="mt-6 grid gap-5 sm:grid-cols-2">{[['Full name', person.name], ['Email address', person.email], ['Role', ROLE_LABELS[person.role]], ['Department', reference.data.departments.find(d => d.id === person.departmentId)?.name ?? 'Unassigned']].map(([label, value]) => <div key={label}>
          <label htmlFor={`profile-${label.replace(' ', '-')}`} className="field-label">{label}</label>
          <Input id={`profile-${label.replace(' ', '-')}`} value={value} readOnly className="bg-muted/40 text-muted-foreground" />
        </div>)}</div>
        <p className="mt-5 flex items-center gap-1.5 text-[10px] leading-relaxed text-muted-foreground"><GoogleLogo size={12} />Your name, email, and avatar are provided by Google. Contact an admin to update your role or department.</p>
      </section>
      <div className="space-y-5">
        <section className="panel p-5">
          <h2 className="mb-4 text-xs font-semibold">Connected account</h2>
          <div className="flex items-center gap-3 rounded-md border bg-muted/20 p-3">
            <GoogleLogo size={22} />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium">Google Workspace</p>
              <p className="mt-1 truncate text-[10px] text-muted-foreground">{person.email}</p>
            </div>
            <CheckCheck className="text-primary" size={16} />
          </div>
          <p className="mt-3 text-[10px] text-muted-foreground">Signed in securely with your company account.</p>
        </section>
        <section className="panel p-5">
          <h2 className="mb-4 text-xs font-semibold">Make yourself at home</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium">Appearance</p>
              <p className="mt-1 text-[10px] text-muted-foreground">Currently using {theme} mode</p>
            </div>
            <Button variant="outline" size="sm" onClick={toggle}>{theme === 'light' ? <Moon /> : <Sun />}{theme === 'light' ? 'Dark' : 'Light'} mode</Button>
          </div>
        </section>
        <section className="rounded-lg border border-dashed p-5">
          <p className="text-xs font-medium">See you again soon.</p>
          <p className="mb-4 mt-2 text-[10px] leading-relaxed text-muted-foreground">Sign out of Atlas on this device. Your team’s knowledge will be right here when you return.</p>
          <Button variant="outline" onClick={() => { void endSession().finally(() => { signOut(); client.clear(); navigate('/login'); }); }}><LogOut />Sign out</Button>
        </section>
      </div>
    </div>
  </div>;
}
