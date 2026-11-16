import { useEffect, useState } from 'react';
import { Save } from 'lucide-react';
import { USE_MOCKS } from '@/api';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/input';
import { Skeleton } from '@/components/shared/States';
import { MockDocument } from './MockDocument';
export function GoogleEmbed({ fileId, src, mode, title = 'Untitled document', content = '', onSave, saving = false, kind = 'document' }: {
  fileId: string;
  src?: string | null;
  mode: 'preview' | 'edit';
  title?: string;
  content?: string;
  onSave?: (content: string) => void;
  saving?: boolean;
  kind?: 'document' | 'spreadsheets' | 'presentation';
}) {
  const [loaded, setLoaded] = useState(false);
  const [draft, setDraft] = useState(content);
  useEffect(() => { setDraft(content); }, [content]);
  useEffect(() => { setLoaded(false); }, [fileId, mode, src]);
  if (!USE_MOCKS && !src) return <Skeleton className="min-h-[750px]" />;
  if (USE_MOCKS)
    return mode === 'edit' ? <div className="panel mx-auto max-w-[740px] overflow-hidden">
      <div className="flex items-center justify-between border-b p-3">
        <span className="text-[11px] text-muted-foreground">Editing document · Changes stay in this demo session</span>
        <Button size="sm" onClick={() => onSave?.(draft)} disabled={saving || draft === content}><Save />{saving ? 'Saving…' : 'Save changes'}</Button>
      </div>
      <label className="sr-only" htmlFor="document-editor">Document content</label>
      <Textarea id="document-editor" className="min-h-[650px] resize-y rounded-none border-0 p-6 text-sm leading-loose" value={draft} onChange={e => setDraft(e.target.value)} disabled={saving} />
    </div> : <MockDocument title={title} content={content} />;
  return <div className="relative min-h-[750px]">{!loaded && <Skeleton className="absolute inset-0" />}<iframe key={`${fileId}-${mode}-${src}`} title={`${title} · Google ${kind} ${mode}`} src={src ?? undefined} className="h-[750px] w-full rounded border bg-white" onLoad={() => setLoaded(true)} allow="clipboard-read; clipboard-write" /></div>;
}
