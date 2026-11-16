import { useState } from 'react';
import { Download, FileCheck2 } from 'lucide-react';
import type { Document } from '@/types';
import { DocumentIcon } from '@/components/shared/DocumentIcon';
import { EmptyState, Skeleton } from '@/components/shared/States';
import { Button } from '@/components/ui/button';
import { TYPE_LABELS } from '@/lib/constants';
import { formatBytes } from '@/lib/utils';
export function FilePreview({ document: doc }: {
  document: Document;
}) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const download = <Button asChild>
    <a href={doc.fileUrl} download={doc.fileName}><Download />Download file</a>
  </Button>;
  if (failed)
    return <EmptyState title="This preview isn’t available" description="You can still download the original file." action={download} />;
  if (doc.type === 'image')
    return <div className="relative grid min-h-[500px] place-items-center rounded-lg border bg-card p-6">{!loaded && <Skeleton className="absolute inset-5" />}<img src={doc.fileUrl} alt={doc.name} className="max-h-[750px] max-w-full rounded object-contain" onLoad={() => setLoaded(true)} onError={() => setFailed(true)} /></div>;
  if (doc.type === 'pdf')
    return <div className="relative min-h-[720px] overflow-hidden rounded border bg-card">
      {!loaded && <Skeleton className="absolute inset-0" />}
      <iframe title={`${doc.name} PDF preview`} src={`${doc.fileUrl}#toolbar=0&navpanes=0`} className="h-[720px] w-full" onLoad={() => setLoaded(true)} onError={() => setFailed(true)} />
      <p className="p-3 text-center text-[10px] text-muted-foreground">PDF preview unavailable in your browser? <a href={doc.fileUrl} download={doc.fileName} className="text-primary underline">Download the original</a></p>
    </div>;
  if (doc.type === 'txt')
    return <div className="panel min-h-[600px] p-6">
      <p className="mb-6 flex items-center gap-2 border-b pb-4 text-[11px] text-muted-foreground"><FileCheck2 size={15} />{doc.fileName}</p>
      <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{doc.content}</pre>
    </div>;
  return <div className="panel flex min-h-[500px] flex-col items-center justify-center gap-4 p-8 text-center">
    <DocumentIcon type={doc.type} className="h-16 w-14 [&_svg]:h-9 [&_svg]:w-9" />
    <div>
      <h2 className="text-base font-semibold">{doc.name}</h2>
      <p className="mt-2 text-xs text-muted-foreground">{TYPE_LABELS[doc.type]} · {formatBytes(doc.size)} · Version {doc.version}.0</p>
    </div>
    <p className="max-w-sm text-xs leading-relaxed text-muted-foreground">This file is best viewed in its original application. Download a copy to see the full document.</p>
    {download}
  </div>;
}
