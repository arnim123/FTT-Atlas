import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowLeft, FileText, History, LockKeyhole } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { getDocument, updateDocument } from '@/api';
import { useAuthStore } from '@/store/auth';
import { canEdit } from '@/lib/access';
import { errorMessage } from '@/lib/utils';
import { useRefresh } from '@/hooks/use-data';
import { GoogleEmbed } from '@/features/viewer/GoogleEmbed';
import { ErrorState, PageSkeleton } from '@/components/shared/States';
import { Button } from '@/components/ui/button';
export function GooglePreviewPage() {
  const { id = '' } = useParams();
  const [params] = useSearchParams();
  const user = useAuthStore(s => s.user);
  const [editing, setEditing] = useState(false);
  const refresh = useRefresh();
  const doc = useQuery({ queryKey: ['document', id, user.id], queryFn: () => getDocument(id, user) });
  const save = useMutation({ mutationFn: (content: string) => updateDocument(id, { content }, user), onSuccess: () => { void refresh(); toast.success('Demo document saved'); }, onError: e => toast.error(errorMessage(e)) });
  if (doc.error)
    return <ErrorState error={doc.error} retry={() => void doc.refetch()} />;
  if (!doc.data)
    return <PageSkeleton />;
  return <div className="min-h-screen bg-muted">
    <header className="flex flex-wrap items-center justify-between gap-4 border-b bg-card px-6 py-4">
      <div className="flex items-center gap-3">
        <FileText className="text-primary" />
        <div>
          <h1 className="text-sm font-medium">{doc.data.name}</h1>
          <p className="mt-1 text-[10px] text-muted-foreground">Google Workspace preview · Demo document</p>
        </div>
      </div>
      <div className="flex gap-2">
        {canEdit(user, doc.data) && !doc.data.archived && <Button variant="outline" onClick={() => setEditing(!editing)}>{editing ? 'View document' : 'Edit document'}</Button>}
        <Button asChild>
          <Link to={`/documents/${id}`}><ArrowLeft />Back to Atlas</Link>
        </Button>
      </div>
    </header>
    <div className="mx-auto max-w-[900px] p-5">
      <p className="mb-5 flex items-center justify-center gap-1.5 text-center text-[10px] text-muted-foreground"><LockKeyhole size={11} />This is a local demo preview. Live Google documents open in Google Workspace.</p>
      {params.has('history') && <div className="panel mb-5 p-5">
        <h2 className="flex items-center gap-2 text-sm font-medium"><History size={16} />Google version history</h2>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">In a connected workspace, Google maintains and displays every revision here. This sample has no live Google revision history. Document edits are available in this demo session.</p>
      </div>}
      <GoogleEmbed fileId={doc.data.googleFileId!} mode={editing ? 'edit' : 'preview'} title={doc.data.name} content={doc.data.content} onSave={content => save.mutate(content)} saving={save.isPending} />
    </div>
  </div>;
}
