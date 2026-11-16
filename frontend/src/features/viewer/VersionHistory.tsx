import { useMutation } from '@tanstack/react-query';
import { Clock3, Download, ExternalLink, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import type { Document, ReferenceData } from '@/types';
import { restoreVersion } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useRefresh } from '@/hooks/use-data';
import { canEdit } from '@/lib/access';
import { errorMessage, formatBytes, formatDate } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { GoogleDocumentLink } from '@/components/shared/GoogleDocumentLink';
import { EmptyState } from '@/components/shared/States';
export function VersionHistory({ document: doc, reference }: {
  document: Document;
  reference: ReferenceData;
}) {
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const restore = useMutation({ mutationFn: (version: number) => restoreVersion(doc.id, version, user), onSuccess: () => { void refresh(); toast.success('Version restored as a new version'); }, onError: error => toast.error(errorMessage(error)) });
  if (doc.type.startsWith('google'))
    return <div className="rounded-md border bg-muted/30 p-4 text-center">
      <Clock3 size={23} className="mx-auto mb-3 text-primary" />
      <h3 className="text-xs font-medium">Every change, kept in Google</h3>
      <p className="my-3 text-[10px] leading-relaxed text-muted-foreground">Google Workspace keeps a complete history of edits. Open it to browse or restore a previous version.</p>
      <Button size="sm" variant="outline" asChild>
        <GoogleDocumentLink document={doc} history>Google version history<ExternalLink /></GoogleDocumentLink>
      </Button>
    </div>;
  if (!doc.versions.length)
    return <EmptyState title="No previous versions" description="Upload a new version to start a version history." />;
  return <div className="space-y-3">
    <p className="mb-4 text-[10px] leading-relaxed text-muted-foreground">Restoring creates a new version. Your full history stays intact.</p>
    {doc.versions.map(version => <div key={version.number} className="rounded-md border p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium">Version {version.number}.0</p>
        {version.number === doc.version && <span className="rounded bg-accent px-1.5 py-0.5 text-[8px] text-primary">Current</span>}
      </div>
      <p className="mt-2 text-[9px] text-muted-foreground">{formatDate(version.createdAt, true)} · {formatBytes(version.size)}</p>
      <p className="mt-1 text-[9px] text-muted-foreground">{reference.users.find(u => u.id === version.uploadedBy)?.name} · {version.note}</p>
      <div className="mt-3 flex gap-2">
        <Button variant="ghost" size="sm" className="h-6 px-1 text-[9px]" asChild>
          <a href={version.fileUrl} download={version.fileName}><Download className="!size-3" />Download</a>
        </Button>
        {version.number !== doc.version && canEdit(user, doc) && !doc.archived && <Button variant="ghost" size="sm" className="h-6 px-1 text-[9px]" disabled={restore.isPending} onClick={() => restore.mutate(version.number)}><RotateCcw className="!size-3" />Restore</Button>}
      </div>
    </div>)}
  </div>;
}
