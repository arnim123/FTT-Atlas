import { useQuery } from '@tanstack/react-query';
import { listDocumentAccess } from '@/api';
import { useAuthStore } from '@/store/auth';
import { formatDateTime } from '@/lib/utils';
import { ErrorState, Skeleton } from '@/components/shared/States';
import { ChannelBadge } from '@/features/integrations/shared';
import { integrationQuery } from '@/features/integrations/query';

export function RecentAccess({ documentId }: { documentId: string }) {
  const user = useAuthStore(s => s.user);
  const access = useQuery({ queryKey: integrationQuery.access(documentId, user.id), queryFn: () => listDocumentAccess(documentId, user) });
  const rows = access.data?.slice(0, 5) ?? [];
  return <div className="border-t pt-4">
    <p className="eyebrow mb-3 text-[8px]">Recent access</p>
    {access.error ? <ErrorState error={access.error} retry={() => void access.refetch()} /> : access.isPending ? <div className="space-y-2" role="status" aria-label="Loading recent access"><Skeleton className="h-8" /><Skeleton className="h-8" /></div> : !rows.length ? <p className="rounded-md border border-dashed px-3 py-4 text-center text-[10px] leading-relaxed text-muted-foreground">No one has opened this document from the web, API, or an AI app yet.</p> : <ul className="space-y-2.5">
      {rows.map(event => <li key={event.id} className="flex items-center gap-2">
        <ChannelBadge channel={event.channel} />
        <span className="min-w-0 flex-1 truncate text-[10px]">{event.clientName}</span>
        <span className="shrink-0 text-[9px] text-muted-foreground">{formatDateTime(event.time)}</span>
      </li>)}
    </ul>}
    {!access.error && (access.data?.length ?? 0) > 5 && <p className="mt-2 text-[9px] text-muted-foreground">Showing the latest 5.</p>}
  </div>;
}
