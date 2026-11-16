import { db } from '@/mocks/db';
import type { ReferenceData, Taxonomy, TaxonomyKind, User } from '@/types';
import { isAdmin } from '@/lib/access';
import { USE_MOCKS, activeUser, assert, newId, request } from './client';
import * as live from './live';

export function getReferenceData(actor: User): Promise<ReferenceData> {
  if (!USE_MOCKS) return live.getReferenceData();
  return request(() => { activeUser(actor); return { departments: db.departments, categories: db.categories, tags: db.tags, users: db.users }; });
}
export function listTaxonomy(kind: TaxonomyKind, actor: User) {
  if (!USE_MOCKS) return live.listTaxonomy(kind);
  return request(() => { assert(isAdmin(activeUser(actor))); return db[kind]; });
}
export function saveTaxonomy(kind: TaxonomyKind, input: { id?: string; name: string; description: string }, actor: User) {
  if (!USE_MOCKS) return live.saveTaxonomy(kind, input);
  return request(() => {
    assert(isAdmin(activeUser(actor))); assert(input.name.trim(), 'Enter a name.');
    assert(!db[kind].some(t => t.id !== input.id && t.name.toLowerCase() === input.name.trim().toLowerCase()), 'This name already exists.');
    if (input.id) { const entry = db[kind].find(t => t.id === input.id); assert(entry, 'Entry not found.'); if (kind === 'tags') db.documents.forEach(d => d.tags = d.tags.map(t => t === entry.name ? input.name.trim() : t)); Object.assign(entry, { name: input.name.trim(), description: input.description }); return entry; }
    const entry: Taxonomy = { id: newId(kind), name: input.name.trim(), description: input.description }; db[kind].push(entry); return entry;
  });
}
export function deleteTaxonomy(kind: TaxonomyKind, id: string, actor: User) {
  if (!USE_MOCKS) return live.deleteTaxonomy(kind, id);
  return request(() => { assert(isAdmin(activeUser(actor))); const entry = db[kind].find(t => t.id === id); assert(entry, 'Entry not found.');
    if (kind === 'departments') assert(!db.documents.some(d => d.departmentId === id) && !db.users.some(u => u.departmentId === id) && !db.folders.some(f => f.departmentId === id), 'Reassign this department’s documents, folders, and users before deleting it.');
    if (kind === 'categories') assert(!db.documents.some(d => d.categoryId === id), 'Reassign documents in this category before deleting it.');
    if (kind === 'tags') db.documents.forEach(d => d.tags = d.tags.filter(t => t !== entry.name));
    db[kind] = db[kind].filter(t => t.id !== id);
  });
}
