import { ChevronRight, Home } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Folder } from '@/types';
export function folderPath(folders: Folder[], id: string): Folder[] {
  const path: Folder[] = []; let folder = folders.find(f => f.id === id); const seen = new Set<string>(); while (folder && !seen.has(folder.id)) {
    path.unshift(folder);
    seen.add(folder.id);
    folder = folders.find(f => f.id === folder?.parentId);
  } return path;
}
export function Breadcrumbs({ folders, folderId, documentName }: {
  folders: Folder[];
  folderId: string;
  documentName?: string;
}) {
  return <nav aria-label="Document breadcrumb" className="flex min-w-0 items-center gap-1.5 overflow-x-auto whitespace-nowrap text-[10px] text-muted-foreground">
    <Link to="/documents" className="rounded hover:text-primary" aria-label="All documents"><Home size={12} /></Link>
    {folderPath(folders, folderId).map(folder => <span key={folder.id} className="flex items-center gap-1.5">
      <ChevronRight size={10} />
      <Link to={`/documents?folder=${folder.id}`} className="rounded hover:text-primary">{folder.name}</Link>
    </span>)}
    {documentName && <span className="flex items-center gap-1.5">
      <ChevronRight size={10} />
      <span className="max-w-[220px] truncate text-foreground" aria-current="page">{documentName}</span>
    </span>}
  </nav>;
}
