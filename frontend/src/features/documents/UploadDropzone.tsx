import { useRef, useState } from 'react';
import { Check, FileUp, UploadCloud, X } from 'lucide-react';
import { toast } from 'sonner';
import { validateUpload } from '@/api';
import { ACCEPTED_FILES } from '@/lib/constants';
import { cn, errorMessage, formatBytes } from '@/lib/utils';
import { Button } from '@/components/ui/button';
export function UploadDropzone({ files, onChange, progress, disabled }: {
  files: File[];
  onChange: (files: File[]) => void;
  progress: Record<string, number>;
  disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  function addFiles(incoming: FileList | File[]) {
    const accepted: File[] = []; Array.from(incoming).forEach(file => {
      try {
        validateUpload(file);
        if (!files.some(f => f.name === file.name && f.size === file.size))
          accepted.push(file);
      }
      catch (error) {
        toast.error(errorMessage(error));
      }
    }); onChange([...files, ...accepted].slice(0, 10)); if (incoming.length + files.length > 10)
      toast.info('Upload up to 10 files at a time.');
  }
  return <div className="space-y-3">
    <div className={cn('rounded-lg border border-dashed bg-muted/30 px-5 py-7 text-center transition-colors', over && 'border-primary bg-accent')} onDragOver={e => {
      e.preventDefault(); if (!disabled)
        setOver(true);
    }} onDragLeave={() => setOver(false)} onDrop={e => {
      e.preventDefault(); setOver(false); if (!disabled)
        addFiles(e.dataTransfer.files);
    }}>
      <span className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-lg border bg-card text-primary"><UploadCloud size={23} strokeWidth={1.5} /></span>
      <p className="text-xs font-medium">Drop your files here</p>
      <p className="my-2 text-[10px] text-muted-foreground">or choose them from your computer</p>
      <Button type="button" variant="outline" size="sm" onClick={() => input.current?.click()} disabled={disabled}>Browse files</Button>
      <input ref={input} type="file" multiple accept={ACCEPTED_FILES} onChange={e => {
        if (e.target.files)
          addFiles(e.target.files); e.target.value = '';
      }} className="sr-only" aria-label="Choose files to upload" disabled={disabled} />
      <p className="mt-4 text-[9px] leading-relaxed text-muted-foreground">PDF, DOCX, PPT, XLSX, TXT, and images<br />Up to 25 MB per file · 10 files at a time</p>
    </div>
    {files.map((file, index) => <div key={`${file.name}-${file.size}`} className="rounded-md border p-3">
      <div className="flex items-center gap-2.5">
        <FileUp size={20} className="shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[11px] font-medium">{file.name}</p>
          <p className="mt-1 text-[9px] text-muted-foreground">{formatBytes(file.size)}{progress[file.name] !== undefined && ` · ${progress[file.name] === 100 ? 'Complete' : `${progress[file.name]}% uploaded`}`}</p>
        </div>
        {progress[file.name] === 100 ? <Check size={15} className="text-primary" /> : <button type="button" className="icon-button h-6 w-6" disabled={disabled} aria-label={`Remove ${file.name}`} onClick={() => onChange(files.filter((_, i) => i !== index))}><X size={13} /></button>}
      </div>
      {progress[file.name] !== undefined && <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label={`Uploading ${file.name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress[file.name]}><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress[file.name]}%` }} /></div>}
    </div>)}
  </div>;
}
