import { Archive, ArrowUpRight, Copy, Download, FolderInput, Link2, MoreHorizontal, ShieldCheck, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import type { Document } from '@/types';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { canManage, isAdmin } from '@/lib/access';
import { copyToClipboard } from '@/lib/utils';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
export function DocumentMenu({ document: doc }: {
  document: Document;
}) {
  const user = useAuthStore(s => s.user);
  const ui = useUIStore();
  const navigate = useNavigate();
  const target = { kind: 'document' as const, id: doc.id, name: doc.name };
  const managed = canManage(user, doc);
  return <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <button className="icon-button h-7 w-7" aria-label={`Actions for ${doc.name}`}><MoreHorizontal size={16} /></button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end">
      <DropdownMenuItem onSelect={() => navigate(`/documents/${doc.id}`)}><ArrowUpRight />Open document</DropdownMenuItem>
      <DropdownMenuItem onSelect={() => { void copyToClipboard(doc.id).then(() => toast.success('Document ID copied')).catch(() => toast.error('Could not copy to the clipboard.')); }}><Copy />Copy document ID</DropdownMenuItem>
      <DropdownMenuItem onSelect={() => { void copyToClipboard(`${window.location.origin}/documents/${doc.id}`).then(() => toast.success('Link copied for AI apps')).catch(() => toast.error('Could not copy to the clipboard.')); }}><Link2 />Copy link for AI</DropdownMenuItem>
      {doc.fileUrl && <DropdownMenuItem asChild>
        <a href={doc.fileUrl} download={doc.fileName}><Download />Download</a>
      </DropdownMenuItem>}
      <DropdownMenuSeparator />
      <DropdownMenuItem disabled={!managed} onSelect={() => ui.setMoveTargets([target])}><FolderInput />Move to folder</DropdownMenuItem>
      <DropdownMenuItem disabled={!managed} onSelect={() => ui.setPermissions(target)}><ShieldCheck />Permissions</DropdownMenuItem>
      <DropdownMenuItem disabled={!managed} onSelect={() => ui.setItemAction({ action: 'archive', targets: [target] })}><Archive />Archive</DropdownMenuItem>
      {isAdmin(user) && <>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive focus:text-destructive" onSelect={() => ui.setItemAction({ action: 'delete', targets: [target] })}><Trash2 />Delete permanently</DropdownMenuItem>
      </>}
    </DropdownMenuContent>
  </DropdownMenu>;
}
