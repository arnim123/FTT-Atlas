import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ArrowUpRight, Eye, PanelRightClose, PanelRightOpen, PencilLine } from 'lucide-react';
import { toast } from 'sonner';
import { USE_MOCKS, getDocument, getEmbed, recordView, updateDocument } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useFolders, useReferenceData, useRefresh } from '@/hooks/use-data';
import { canEdit } from '@/lib/access';
import { cn, errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { GoogleDocumentLink } from '@/components/shared/GoogleDocumentLink';
import { ErrorState, PageSkeleton } from '@/components/shared/States';
import { ViewerHeader } from '@/features/viewer/ViewerHeader';
import { GoogleEmbed } from '@/features/viewer/GoogleEmbed';
import { FilePreview } from '@/features/viewer/FilePreview';
import { DocumentInspector } from '@/features/viewer/DocumentInspector';
export function DocumentViewerPage() {
  const { id = '' } = useParams();
  const user = useAuthStore(s => s.user);
  const reference = useReferenceData();
  const folders = useFolders();
  const refresh = useRefresh();
  const client = useQueryClient();
  const [mode, setMode] = useState<'preview' | 'edit'>('preview');
  const [panel, setPanel] = useState(true);
  const viewed = useRef('');
  const doc = useQuery({ queryKey: ['document', id, user.id], queryFn: () => getDocument(id, user) });
  const embed = useQuery({ queryKey: ['embed', id, user.id], queryFn: () => getEmbed(id), enabled: !!doc.data?.type.startsWith('google') && !USE_MOCKS });
  useEffect(() => { setMode('preview'); }, [id, user.id]);
  useEffect(() => {
    if (doc.data && viewed.current !== `${id}:${user.id}`) {
      viewed.current = `${id}:${user.id}`;
      void recordView(id, user).then(() => { void client.invalidateQueries({ queryKey: ['dashboard'] }); void client.invalidateQueries({ queryKey: ['document-access', id] }); }).catch(() => undefined);
    }
  }, [doc.data, id, user, client]);
  const save = useMutation({ mutationFn: (content: string) => updateDocument(id, { content }, user), onSuccess: () => { void refresh(); toast.success('Document saved'); }, onError: error => toast.error(errorMessage(error)) });
  if (doc.error || reference.error || folders.error)
    return <div className="page-container">
      <Button asChild variant="ghost" className="mb-3">
        <Link to="/documents"><ArrowLeft />Back to documents</Link>
      </Button>
      <ErrorState error={doc.error ?? reference.error ?? folders.error} retry={() => { void doc.refetch(); void reference.refetch(); void folders.refetch(); }} />
    </div>;
  if (!doc.data || !reference.data || !folders.data)
    return <PageSkeleton />;
  const google = doc.data.type.startsWith('google');
  const editable = canEdit(user, doc.data) && !doc.data.archived;
  const editUrl = embed.data?.editUrl ?? null;
  const canGoogleEdit = USE_MOCKS ? editable : editable && !!editUrl;
  return <div className="animate-fade-up">
    <ViewerHeader document={doc.data} folders={folders.data} />
    {doc.data.archived && <p className="border-b bg-amber-500/10 px-8 py-3 text-xs text-amber-700 dark:text-amber-300">This document is archived. Restore it to make changes.</p>}
    <div className="flex flex-col items-stretch lg:flex-row">
      <div className="min-w-0 flex-1">
        <div className="flex h-12 items-center justify-between border-b bg-card/50 px-5">
          <div className="flex items-center gap-1">{google ? <>
            <Button size="sm" variant="ghost" className={cn('h-7', mode === 'preview' && 'bg-accent text-primary')} onClick={() => setMode('preview')} aria-pressed={mode === 'preview'}><Eye className="!size-3" />View</Button>
            {canGoogleEdit && <Button size="sm" variant="ghost" className={cn('h-7', mode === 'edit' && 'bg-accent text-primary')} onClick={() => setMode('edit')} aria-pressed={mode === 'edit'}><PencilLine className="!size-3" />Edit</Button>}
          </> : <span className="text-[10px] text-muted-foreground">Document preview</span>}</div>
          <button className="flex items-center gap-1.5 rounded p-1 text-[10px] text-muted-foreground hover:text-primary" onClick={() => setPanel(!panel)} aria-label={panel ? 'Hide document information' : 'Show document information'}>
            {panel ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
            <span className="hidden sm:inline">{panel ? 'Hide' : 'Show'} details</span>
          </button>
        </div>
        <div className="min-h-[680px] bg-muted/35 p-4 md:p-7">{google ? <GoogleEmbed key={doc.data.id} fileId={doc.data.googleFileId ?? doc.data.id} src={mode === 'edit' ? editUrl : embed.data?.previewUrl} mode={canGoogleEdit ? mode : 'preview'} title={doc.data.name} content={doc.data.content} onSave={content => save.mutate(content)} saving={save.isPending} kind={doc.data.type === 'google-sheet' ? 'spreadsheets' : doc.data.type === 'google-slide' ? 'presentation' : 'document'} /> : <FilePreview key={`${doc.data.id}-${doc.data.version}`} document={doc.data} />}</div>
        {google && <div className="sticky bottom-0 flex items-center justify-center gap-2 border-t bg-card/95 px-4 py-3.5 text-[10px] backdrop-blur">
          <span className="text-muted-foreground">Having trouble?</span>
          <GoogleDocumentLink document={doc.data} className="flex items-center gap-1 text-primary hover:underline">Open in Google Docs<ArrowUpRight size={12} /></GoogleDocumentLink>
        </div>}
      </div>
      {panel && <DocumentInspector key={doc.data.id} document={doc.data} reference={reference.data} close={() => setPanel(false)} />}
    </div>
  </div>;
}
