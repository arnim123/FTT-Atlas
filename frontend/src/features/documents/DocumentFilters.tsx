import type { DocumentFilters as Filters, ReferenceData } from '@/types';
import { TYPE_LABELS } from '@/lib/constants';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
export function DocumentFilters({ filters, onChange, reference, vertical = false, dates = false }: {
  filters: Filters;
  onChange: (value: Filters) => void;
  reference: ReferenceData;
  vertical?: boolean;
  dates?: boolean;
}) {
  const fields: {
    key: keyof Filters;
    label: string;
    options: {
      id: string;
      name: string;
    }[];
  }[] = [{ key: 'departmentId', label: 'Department', options: reference.departments }, { key: 'categoryId', label: 'Category', options: reference.categories }, { key: 'tag', label: 'Tag', options: reference.tags.map(t => ({ id: t.name, name: t.name })) }, { key: 'type', label: 'File type', options: Object.entries(TYPE_LABELS).map(([id, name]) => ({ id, name })) }, { key: 'ownerId', label: 'Owner', options: reference.users }];
  const active = fields.some(f => filters[f.key]) || filters.from || filters.to || filters.includeArchived;
  return <div className={vertical ? 'space-y-5' : 'grid grid-cols-2 gap-3 border-b bg-muted/20 px-4 py-4 md:grid-cols-3 xl:grid-cols-6'}>{fields.map(field => <div key={field.key}>
    <label htmlFor={`filter-${field.key}`} className="mb-2 block text-[10px] font-medium">{field.label}</label>
    <select id={`filter-${field.key}`} className="select-input h-8 text-[10px]" value={String(filters[field.key] ?? '')} onChange={e => onChange({ ...filters, [field.key]: e.target.value || undefined })}>
      <option value="">All {field.label === 'Owner' ? 'people' : field.label.toLowerCase() + 's'}</option>
      {field.options.map(option => <option key={option.id} value={option.id}>{option.name}</option>)}
    </select>
  </div>)}{dates && <div className="space-y-2">
    <label htmlFor="date-from" className="mb-2 block text-[10px] font-medium">Last modified</label>
    <input id="date-from" type="date" aria-label="Modified from date" className="select-input text-[10px]" max={filters.to} value={filters.from ?? ''} onChange={e => onChange({ ...filters, from: e.target.value || undefined })} />
    <input type="date" aria-label="Modified to date" className="select-input text-[10px]" min={filters.from} value={filters.to ?? ''} onChange={e => onChange({ ...filters, to: e.target.value || undefined })} />
  </div>}{active && <div className="flex items-end">
    <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => onChange({ sort: filters.sort })}><X size={12} />Clear filters</Button>
  </div>}</div>;
}
