import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Braces, Code2, MessageSquare, Sparkles, Bot } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { USE_MOCKS, getOrgSettings, usePublicConfig } from '@/api';
import { MCP_SERVER_URL } from '@/lib/constants';
import { useAuthStore } from '@/store/auth';
import { Dialog } from '@/components/ui/dialog';
import { ErrorState, Skeleton } from '@/components/shared/States';
import { connectorGuides, connectors } from './connectors';
import { ConnectorDrawer } from './ConnectorDrawer';
import { integrationQuery } from './query';

const icons: Record<string, LucideIcon> = { chatgpt: MessageSquare, claude: Sparkles, grok: Bot, cursor: Code2, custom: Braces };

export function ConnectApps() {
  const user = useAuthStore(s => s.user);
  const [active, setActive] = useState<string | null>(null);
  const settings = useQuery({ queryKey: integrationQuery.settings(user.id), queryFn: () => getOrgSettings(user) });
  const config = usePublicConfig();
  const base = (config.data?.publicBaseUrl || 'http://127.0.0.1:8000').replace(/\/$/, '');
  const guides = USE_MOCKS ? connectors : connectorGuides(base);
  const mcpUrl = USE_MOCKS ? MCP_SERVER_URL : `${base}/mcp`;
  const guide = guides.find(item => item.id === active);
  if (settings.error || config.error) return <ErrorState error={settings.error ?? config.error} retry={() => { void settings.refetch(); void config.refetch(); }} />;
  if (settings.isPending || !settings.data || (!USE_MOCKS && config.isPending)) return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" role="status" aria-label="Loading integrations">{[1, 2, 3, 4, 5].map(item => <Skeleton key={item} className="h-36" />)}</div>;
  return <>
    {!settings.data.allowExternalAi && <p className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">External AI access is turned off for this workspace. Connectors stay here, and new tokens and consent grants are refused until an admin turns it back on.</p>}
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {guides.map(item => {
        const Icon = icons[item.id] ?? Sparkles;
        return <button key={item.id} type="button" onClick={() => setActive(item.id)} className="panel flex flex-col items-start p-5 text-left transition-colors hover:border-primary/30">
          <span className="mb-4 grid h-10 w-10 place-items-center rounded-md bg-accent text-primary"><Icon size={18} strokeWidth={1.6} /></span>
          <span className="text-sm font-semibold">{item.name}</span>
          <span className="mt-2 flex-1 text-[11px] leading-relaxed text-muted-foreground">{item.summary}</span>
          <span className="mt-4 text-[10px] font-medium text-primary">{item.auth === 'oauth' ? 'OAuth connector' : item.auth === 'rest' ? 'REST API' : 'Access token'}</span>
        </button>;
      })}
    </div>
    <Dialog open={!!guide} onOpenChange={open => !open && setActive(null)}>
      {guide && <ConnectorDrawer guide={guide} mcpUrl={mcpUrl} />}
    </Dialog>
  </>;
}
