import { useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Archive, ArrowUpRight, Download, MoreHorizontal, ShieldCheck, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import type { Document, Folder } from '@/types';
import { uploadVersion } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useRefresh } from '@/hooks/use-data';
import { canEdit, canManage, isAdmin } from '@/lib/access';
import { ACCEPTED_FILES, TYPE_LABELS } from '@/lib/constants';
import { errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { GoogleDocumentLink } from '@/components/shared/GoogleDocumentLink';
import { AccessBadge } from '@/components/shared/AccessBadge';
import { Breadcrumbs } from '@/features/folders/Breadcrumbs';
export function ViewerHeader({ document: doc, folders }: {
  document: Document;
  folders: Folder[];
}) {
  const user = useAuthStore(s => s.user);
  const ui = useUIStore();
  const refresh = useRefresh();
  const input = useRef<HTMLInputElement>(null);
  const google = doc.type.startsWith('google');
  const target = { kind: 'document' as const, id: doc.id, name: doc.name };
  const upload = useMutation({ mutationFn: (file: File) => uploadVersion(doc.id, file, user), onSuccess: () => { void refresh(); toast.success('New version uploaded'); }, onError: error => toast.error(errorMessage(error)) });
  return <div className="border-b bg-card px-5 py-5 md:px-8">
    <Breadcrumbs folders={folders} folderId={doc.folderId} documentName={doc.name} />
    <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <DocumentIcon type={doc.type} />
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">{doc.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-[10px] text-muted-foreground">{TYPE_LABELS[doc.type]}</span>
            <span className="text-muted-foreground/40">·</span>
            <AccessBadge level={doc.access.level} />
            <span className="rounded border px-1.5 py-0.5 text-[9px] text-muted-foreground">v{doc.version}.0</span>
            {doc.archived && <span className="tag">Archived</span>}
          </div>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">{google ? <Button asChild>
        <GoogleDocumentLink document={doc}>Open in Google Docs<ArrowUpRight /></GoogleDocumentLink>
      </Button> : <Button asChild>
        <a href={doc.fileUrl} download={doc.fileName}><Download />Download</a>
      </Button>}{canManage(user, doc) && <Button variant="outline" onClick={() => ui.setPermissions(target)}><ShieldCheck />Permissions</Button>}{!google && canEdit(user, doc) && !doc.archived && <>
        <Button variant="outline" disabled={upload.isPending} onClick={() => input.current?.click()}><Upload />{upload.isPending ? 'Uploading…' : 'New version'}</Button>
        <input ref={input} type="file" className="sr-only" aria-label="Upload new version" accept={ACCEPTED_FILES} onChange={e => {
          const file = e.target.files?.[0]; if (file)
            upload.mutate(file); e.target.value = '';
        }} />
      </>}{canManage(user, doc) && <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="icon" className="h-9 w-9" aria-label="Document actions"><MoreHorizontal /></Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => ui.setItemAction({ action: doc.archived ? 'restore' : 'archive', targets: [target] })}><Archive />{doc.archived ? 'Restore document' : 'Archive document'}</DropdownMenuItem>
          {isAdmin(user) && <DropdownMenuItem className="text-destructive" onSelect={() => ui.setItemAction({ action: 'delete', targets: [target] })}><Trash2 />Delete permanently</DropdownMenuItem>}
        </DropdownMenuContent>
      </DropdownMenu>}</div>
    </div>
  </div>;
}
