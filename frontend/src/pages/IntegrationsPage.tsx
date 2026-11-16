import { useSearchParams } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { isAdmin } from '@/lib/access';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeading } from '@/components/shared/PageHeading';
import { ConnectApps } from '@/features/integrations/ConnectApps';
import { TokenTable } from '@/features/integrations/TokenTable';
import { GrantTable } from '@/features/integrations/GrantTable';
import { ActivityLog } from '@/features/integrations/ActivityLog';
import { OrgControls } from '@/features/integrations/OrgControls';

const baseTabs = [
  { id: 'connect', label: 'Connect an AI app' },
  { id: 'tokens', label: 'My access tokens' },
  { id: 'apps', label: 'Connected apps' },
  { id: 'activity', label: 'Activity' },
];

export function IntegrationsPage() {
  const user = useAuthStore(s => s.user);
  const [params, setParams] = useSearchParams();
  const tabs = isAdmin(user) ? [...baseTabs, { id: 'organization', label: 'Organization controls' }] : baseTabs;
  const requested = params.get('tab') ?? 'connect';
  const tab = tabs.some(item => item.id === requested) ? requested : 'connect';
  return <div className="page-container">
    <PageHeading eyebrow="Integrations" title="Your knowledge, ready for the tools you trust." description="Connect ChatGPT, Claude, Grok, Cursor, or your own API client. They only see what you can see." />
    <div className="mb-5 flex items-start gap-2.5 rounded-lg border border-primary/15 bg-accent/60 px-4 py-3 text-[11px] leading-relaxed">
      <ShieldCheck size={16} className="mt-0.5 shrink-0 text-primary" />
      <p>AI apps can only see what YOU can see. Read-only unless you grant write access.</p>
    </div>
    <Tabs value={tab} onValueChange={value => setParams(value === 'connect' ? {} : { tab: value }, { replace: true })}>
      <TabsList className="flex h-auto w-full flex-wrap justify-start">
        {tabs.map(item => <TabsTrigger key={item.id} value={item.id}>{item.label}</TabsTrigger>)}
      </TabsList>
      <TabsContent value="connect"><ConnectApps /></TabsContent>
      <TabsContent value="tokens"><TokenTable /></TabsContent>
      <TabsContent value="apps"><GrantTable /></TabsContent>
      <TabsContent value="activity"><ActivityLog /></TabsContent>
      {isAdmin(user) && <TabsContent value="organization"><OrgControls /></TabsContent>}
    </Tabs>
  </div>;
}
