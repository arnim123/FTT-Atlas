import { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, FilePlus2, Link2, Loader2, ShieldCheck, Upload } from 'lucide-react';
import { toast } from 'sonner';
import type { Access, DocumentType } from '@/types';
import { USE_MOCKS, createDocument, validateGoogleUrl, validateUpload } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore, type DocumentTab } from '@/store/ui';
import { useFolders, useReferenceData, useRefresh } from '@/hooks/use-data';
import { DEFAULT_ACCESS } from '@/lib/constants';
import { errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { ErrorState, PageSkeleton } from '@/components/shared/States';
import { AccessPicker } from '@/features/permissions/AccessPicker';
import { GoogleLinkForm } from './GoogleLinkForm';
import { UploadDropzone } from './UploadDropzone';
import { MetadataForm, metadataSchema, type MetadataValues } from './MetadataForm';
export function AddDocumentDrawer() {
  const ui = useUIStore();
  const user = useAuthStore(s => s.user);
  const reference = useReferenceData();
  const folders = useFolders();
  const navigate = useNavigate();
  const refresh = useRefresh();
  const [tab, setTab] = useState<DocumentTab>(ui.addDocument ?? 'create');
  const [type, setType] = useState<DocumentType>('google-doc');
  const [template, setTemplate] = useState('blank');
  const [url, setUrl] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [access, setAccess] = useState<Access>(structuredClone(DEFAULT_ACCESS));
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [sharing, setSharing] = useState(false);
  const activeFile = useRef<string | null>(null);
  const form = useForm<MetadataValues>({ resolver: zodResolver(metadataSchema), defaultValues: { name: '', description: '', tags: [], categoryId: 'guide', departmentId: user.departmentId, folderId: ui.addFolderId } });
  useEffect(() => {
    if (!reference.data) return;
    if (!reference.data.categories.some(item => item.id === form.getValues('categoryId')) && reference.data.categories[0]) form.setValue('categoryId', reference.data.categories[0].id);
    if (!reference.data.departments.some(item => item.id === form.getValues('departmentId'))) {
      const mine = reference.data.departments.find(item => item.id === user.departmentId) ?? reference.data.departments[0];
      if (mine) form.setValue('departmentId', mine.id);
    }
  }, [reference.data, user.departmentId, form]);
  const mutation = useMutation({
    mutationFn: async (metadata: MetadataValues) => {
      if (tab === 'link' && (!validateGoogleUrl(url) || (USE_MOCKS && url.toLowerCase().includes('unshared'))))
        throw new Error('Add a valid Google URL and share the document with the service account.');
      if (tab === 'upload' && !files.length)
        throw new Error('Choose at least one file to upload.');
      if (access.level === 'custom' && !access.grants.length)
        throw new Error('Choose at least one person or department for custom access.');
      files.forEach(validateUpload);
      if (tab === 'upload') {
        const created = [];
        for (const file of files) {
          activeFile.current = file.name;
          setProgress(prev => ({ ...prev, [file.name]: USE_MOCKS ? 10 : 0 }));
          const timer = USE_MOCKS ? setInterval(() => setProgress(prev => ({ ...prev, [file.name]: Math.min((prev[file.name] ?? 0) + 20, 90) })), 75) : 0;
          try {
            const doc = await createDocument({ ...metadata, name: files.length > 1 ? file.name.replace(/\.[^.]+$/, '') : metadata.name, type: validateUpload(file), access, file }, user, percent => setProgress(prev => ({ ...prev, [file.name]: percent })));
            created.push(doc);
            setProgress(prev => ({ ...prev, [file.name]: 100 }));
          }
          finally {
            if (timer) clearInterval(timer);
          }
        }
        return created;
      }
      const linkedType: DocumentType = url.includes('/spreadsheets/') ? 'google-sheet' : url.includes('/presentation/') ? 'google-slide' : 'google-doc';
      return [await createDocument({ ...metadata, type: tab === 'link' ? linkedType : type, access, template, googleUrl: tab === 'link' ? url : undefined }, user)];
    }, onSuccess: docs => {
      void refresh(); toast.success(docs.length > 1 ? `${docs.length} documents added` : 'Your document is ready', { description: 'A little more knowledge, shared with your team.' }); ui.closeAdd(); if (docs.length === 1)
        navigate(`/documents/${docs[0].id}`);
      else
        navigate(`/documents?folder=${form.getValues('folderId')}`);
    }, onError: error => {
      toast.error(errorMessage(error)); if (activeFile.current)
        setFiles(prev => prev.filter(file => progress[file.name] !== 100)); void refresh();
    }
  });
  function changeFiles(next: File[]) {
    setFiles(next); if (!form.getValues('name') && next.length)
      form.setValue('name', next[0].name.replace(/\.[^.]+$/, ''), { shouldValidate: true });
  }
  return <Dialog open onOpenChange={open => !open && !mutation.isPending && ui.closeAdd()}>
    <DialogContent drawer>
      <div className="border-b px-6 py-6">
        <div className="mb-3 flex items-center gap-2 text-[10px] font-medium text-primary"><span className="grid h-7 w-7 place-items-center rounded-md bg-accent"><FilePlus2 size={14} /></span>GROW YOUR SHARED KNOWLEDGE</div>
        <DialogTitle>Add a document</DialogTitle>
        <DialogDescription>Good ideas deserve a place your team can find them.</DialogDescription>
      </div>
      {reference.error || folders.error ? <div className="px-6"><ErrorState error={reference.error ?? folders.error} retry={() => { void reference.refetch(); void folders.refetch(); }} /></div> : !reference.data || !folders.data ? <PageSkeleton rows={3} /> : <form className="flex min-h-0 flex-1 flex-col" onSubmit={form.handleSubmit(values => mutation.mutate(values))}>
        <fieldset disabled={mutation.isPending} className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <Tabs value={tab} onValueChange={value => setTab(value as DocumentTab)}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="create"><FilePlus2 size={13} />Create new</TabsTrigger>
              <TabsTrigger value="link"><Link2 size={13} />Link existing</TabsTrigger>
              <TabsTrigger value="upload"><Upload size={13} />Upload file</TabsTrigger>
            </TabsList>
            <TabsContent value="create">
              <div className="space-y-4 rounded-lg border bg-muted/20 p-4">
                <div>
                  <label className="field-label" htmlFor="google-title">Google document title</label>
                  <Input id="google-title" placeholder="Give your next great idea a name" value={form.watch('name')} onChange={e => form.setValue('name', e.target.value, { shouldValidate: true })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="google-type" className="field-label">Document type</label>
                    <select id="google-type" className="select-input" value={type} onChange={e => setType(e.target.value as DocumentType)}>
                      <option value="google-doc">Google Doc</option>
                      <option value="google-sheet">Google Sheet</option>
                      <option value="google-slide">Google Slide</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="google-template" className="field-label">Start from</label>
                    <select id="google-template" className="select-input" value={template} onChange={e => setTemplate(e.target.value)}>
                      <option value="blank">Blank document</option>
                      <option value="Meeting notes">Meeting notes</option>
                      <option value="Standard procedure">Standard procedure</option>
                      <option value="Project brief">Project brief</option>
                    </select>
                  </div>
                </div>
              </div>
            </TabsContent>
            <TabsContent value="link"><GoogleLinkForm value={url} onChange={setUrl} /></TabsContent>
            <TabsContent value="upload"><UploadDropzone files={files} onChange={changeFiles} progress={progress} disabled={mutation.isPending} />{files.length > 1 && <p className="mt-3 text-[10px] text-muted-foreground">Each file keeps its filename. The metadata below applies to all {files.length} documents.</p>}</TabsContent>
          </Tabs>
          <div className="my-6 border-t" />
          <MetadataForm form={form} reference={reference.data} folders={folders.data} />
          <div className="my-5 border-t" />
          <button type="button" aria-expanded={sharing} onClick={() => setSharing(!sharing)} className="flex w-full items-center gap-2 text-xs font-medium"><ShieldCheck size={15} className="text-primary" />Access & permissions<span className="ml-auto text-[10px] capitalize text-muted-foreground">{access.level} · {sharing ? 'Hide' : 'Manage'}</span></button>
          {sharing && <div className="mt-4"><AccessPicker value={access} onChange={setAccess} reference={reference.data} ownerId={user.id} departmentId={form.watch('departmentId')} compact /></div>}
        </fieldset>
        <div className="flex items-center justify-between gap-2 border-t bg-card px-6 py-4">
          <span className="hidden text-[9px] text-muted-foreground sm:block">A shared workspace. A smarter team.</span>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={ui.closeAdd} disabled={mutation.isPending}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? <Loader2 className="animate-spin" /> : <ArrowRight />}{mutation.isPending ? 'Adding document…' : tab === 'upload' ? `Upload${files.length > 1 ? ` ${files.length} files` : ' document'}` : tab === 'link' ? 'Link document' : 'Create document'}</Button>
          </div>
        </div>
      </form>}
    </DialogContent>
  </Dialog>;
}
