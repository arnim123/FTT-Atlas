import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation } from '@tanstack/react-query';
import { FolderPlus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { createFolder, updateFolder } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useFolders, useRefresh } from '@/hooks/use-data';
import { errorMessage } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { FormField } from '@/components/shared/FormField';
const schema = z.object({ name: z.string().trim().min(1, 'Give your folder a name.').max(80, 'Use 80 characters or fewer.') });
export function FolderDialog() {
  const config = useUIStore(s => s.folderDialog)!;
  const close = useUIStore(s => s.setFolderDialog);
  const user = useAuthStore(s => s.user);
  const refresh = useRefresh();
  const { data: folders } = useFolders();
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { name: config.name ?? '' } });
  const mutation = useMutation({ mutationFn: async ({ name }: z.infer<typeof schema>) => { if (config.mode === 'rename') await updateFolder(config.id!, { name }, user); else await createFolder({ name, parentId: config.parentId ?? 'root', departmentId: user.departmentId }, user); }, onSuccess: () => { close(null); void refresh(); toast.success(config.mode === 'rename' ? 'Folder renamed' : 'Folder created'); }, onError: error => toast.error(errorMessage(error)) });
  return <Dialog open onOpenChange={open => !open && !mutation.isPending && close(null)}>
    <DialogContent>
      <DialogHeader>
        <FolderPlus className="mb-3 text-primary" size={25} />
        <DialogTitle>{config.mode === 'rename' ? 'Rename folder' : 'A new home for your knowledge'}</DialogTitle>
        <DialogDescription>{config.mode === 'rename' ? 'Choose a clear, recognizable name.' : `Create a folder in ${folders?.find(f => f.id === config.parentId)?.name ?? 'Company Knowledge'}.`}</DialogDescription>
      </DialogHeader>
      <form onSubmit={form.handleSubmit(values => mutation.mutate(values))}>
        <FormField label="Folder name" htmlFor="folder-name" error={form.formState.errors.name?.message}><Input autoFocus id="folder-name" placeholder="e.g. Team playbooks" {...form.register('name')} /></FormField>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => close(null)}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending && <Loader2 className="animate-spin" />}{config.mode === 'rename' ? 'Save name' : 'Create folder'}</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}
