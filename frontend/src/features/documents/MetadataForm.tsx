import { z } from 'zod';
import type { UseFormReturn } from 'react-hook-form';
import type { Folder, ReferenceData } from '@/types';
import { Input, Textarea } from '@/components/ui/input';
import { FormField } from '@/components/shared/FormField';
import { FolderPicker } from '@/features/folders/FolderPicker';
import { TagInput } from './TagInput';
import { useAuthStore } from '@/store/auth';
import { canEdit, isAdmin } from '@/lib/access';
export const metadataSchema = z.object({ name: z.string().trim().min(1, 'Give your document a name.').max(150, 'Use 150 characters or fewer.'), description: z.string().max(1000, 'Use 1,000 characters or fewer.'), tags: z.array(z.string()).max(15, 'Choose up to 15 tags.'), categoryId: z.string().min(1, 'Choose a category.'), departmentId: z.string().min(1, 'Choose a department.'), folderId: z.string().min(1, 'Choose a folder.') });
export type MetadataValues = z.infer<typeof metadataSchema>;
export function MetadataForm({ form, reference, folders }: {
  form: UseFormReturn<MetadataValues>;
  reference: ReferenceData;
  folders: Folder[];
}) {
  const user = useAuthStore(s => s.user);
  const errors = form.formState.errors;
  return <div className="space-y-4">
    <div>
      <p className="eyebrow mb-4">Make it easy to find</p>
      <FormField label="Document name" htmlFor="document-name" error={errors.name?.message}><Input id="document-name" placeholder="e.g. Your team's getting started guide" {...form.register('name')} aria-invalid={!!errors.name} /></FormField>
    </div>
    <FormField label="Description" htmlFor="document-description" optional error={errors.description?.message}><Textarea id="document-description" className="min-h-20" placeholder="A little context goes a long way…" {...form.register('description')} /></FormField>
    <FormField label="Tags" optional error={errors.tags?.message}><TagInput value={form.watch('tags')} onChange={tags => form.setValue('tags', tags, { shouldDirty: true, shouldValidate: true })} suggestions={reference.tags.map(t => t.name)} /></FormField>
    <div className="grid grid-cols-2 gap-4">
      <FormField label="Category" htmlFor="document-category" error={errors.categoryId?.message}>
        <select id="document-category" className="select-input" {...form.register('categoryId')}>
          <option value="">Choose a category</option>
          {reference.categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </FormField>
      <FormField label="Department" htmlFor="document-department" error={errors.departmentId?.message}>
        <select id="document-department" className="select-input" {...form.register('departmentId')}>{reference.departments.filter(d => isAdmin(user) || d.id === user.departmentId).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
      </FormField>
    </div>
    <FormField label="Folder" error={errors.folderId?.message}><FolderPicker folders={folders} value={form.watch('folderId')} onChange={folderId => form.setValue('folderId', folderId, { shouldDirty: true })} disabledIds={folders.filter(f => !canEdit(user, f)).map(f => f.id)} /></FormField>
  </div>;
}
