import { db } from '@/mocks/db';
import type { CreateDocumentInput, Document, DocumentFilters, User } from '@/types';
import { canCreate, canEdit, canManage, canView, isAdmin } from '@/lib/access';
import { MAX_FILE_SIZE } from '@/lib/constants';
import { USE_MOCKS, activeUser, assert, newId, request } from './client';
import { maxUploadBytes } from './public-config';
import * as live from './live';

export function requireDocument(id: string, actor: User) {
  const doc = db.documents.find(d => d.id === id);
  assert(doc, 'This document could not be found. It may have been deleted.');
  assert(canView(activeUser(actor), doc), 'You don’t have access to this document.');
  return doc;
}
export function folderDescendants(id: string): string[] {
  return [id, ...db.folders.filter(f => f.parentId === id).flatMap(f => folderDescendants(f.id))];
}
export function filteredDocuments(actor: User, filters: DocumentFilters = {}): Document[] {
  const user = activeUser(actor);
  const folderIds = filters.folderId ? folderDescendants(filters.folderId) : undefined;
  const query = filters.query?.trim().toLowerCase();
  const result = db.documents.filter(d => canView(user, d)
    && (filters.includeArchived || d.archived === !!filters.archived)
    && (!folderIds || folderIds.includes(d.folderId))
    && (!filters.departmentId || d.departmentId === filters.departmentId)
    && (!filters.categoryId || d.categoryId === filters.categoryId)
    && (!filters.tag || d.tags.includes(filters.tag))
    && (!filters.type || d.type === filters.type)
    && (!filters.ownerId || d.ownerId === filters.ownerId)
    && (!filters.from || d.modifiedAt.slice(0, 10) >= filters.from)
    && (!filters.to || d.modifiedAt.slice(0, 10) <= filters.to)
    && (!query || `${d.name} ${d.description} ${d.tags.join(' ')} ${d.content}`.toLowerCase().includes(query)));
  return result.sort((a, b) => filters.sort === 'name' ? a.name.localeCompare(b.name) : filters.sort === 'views' ? b.views - a.views : filters.sort === 'oldest' ? a.modifiedAt.localeCompare(b.modifiedAt) : b.modifiedAt.localeCompare(a.modifiedAt));
}
export function listDocuments(actor: User, filters: DocumentFilters = {}) {
  if (!USE_MOCKS) return live.listDocuments(filters);
  return request(() => filteredDocuments(actor, filters));
}
export function getDocument(id: string, actor: User) {
  if (!USE_MOCKS) return live.getDocument(id);
  return request(() => requireDocument(id, actor));
}
export function getEmbed(id: string) {
  if (USE_MOCKS) return Promise.resolve(null);
  return live.getEmbed(id);
}
export function getRelatedDocuments(id: string, actor: User) {
  if (!USE_MOCKS) return live.getRelatedDocuments(id);
  return request(() => { const doc = requireDocument(id, actor); return filteredDocuments(actor).filter(d => d.id !== id && (d.folderId === doc.folderId || d.tags.some(t => doc.tags.includes(t)))).slice(0, 5); });
}
export function recordView(id: string, actor: User) {
  if (!USE_MOCKS) return live.recordView();
  return request(() => { requireDocument(id, actor).views++; });
}
export function validateGoogleUrl(url: string) {
  try { const parsed = new URL(url); return parsed.protocol === 'https:' && parsed.hostname === 'docs.google.com' && /^\/(document|spreadsheets|presentation)\/d\/[a-zA-Z0-9_-]+/.test(parsed.pathname); } catch { return false; }
}
export function checkGoogleSharing(url: string) {
  if (!USE_MOCKS) return live.checkGoogleSharing(url);
  return request(() => { assert(validateGoogleUrl(url), 'Enter a valid Google Docs, Sheets, or Slides URL.'); return { shared: !url.toLowerCase().includes('unshared'), fileId: url.split('/d/')[1].split('/')[0], email: undefined as string | undefined }; });
}
export function validateUpload(file: File) {
  const limit = USE_MOCKS ? MAX_FILE_SIZE : maxUploadBytes();
  assert(file.size > 0, 'This file is empty. Choose a file with content.');
  assert(file.size <= limit, `${file.name} exceeds the ${Math.round(limit / 1024 / 1024)} MB file size limit.`);
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  const types: Record<string, Document['type']> = { pdf: 'pdf', docx: 'docx', ppt: 'ppt', pptx: 'ppt', xls: 'xlsx', xlsx: 'xlsx', txt: 'txt', png: 'image', jpg: 'image', jpeg: 'image', gif: 'image', webp: 'image' };
  assert(types[ext], `${file.name} isn’t a supported file type.`);
  return types[ext];
}
export function createDocument(input: CreateDocumentInput, actor: User, onProgress?: (percent: number) => void) {
  if (!USE_MOCKS) return live.createDocument(input, onProgress);
  return request(async () => {
    const user = activeUser(actor);
    assert(canCreate(user));
    assert(input.name.trim(), 'Give your document a name.');
    const folder = db.folders.find(f => f.id === input.folderId && !f.archived);
    assert(folder && canEdit(user, folder), 'Choose a folder where you have edit access.');
    assert(db.departments.some(d => d.id === input.departmentId), 'Choose a valid department.');
    assert(isAdmin(user) || input.departmentId === user.departmentId, 'You can only create documents in your department.');
    if (input.googleUrl) assert(validateGoogleUrl(input.googleUrl) && !input.googleUrl.toLowerCase().includes('unshared'), 'Share this document with the service account before linking it.');
    const type = input.file ? validateUpload(input.file) : input.type;
    const now = new Date().toISOString();
    const fileUrl = input.file ? URL.createObjectURL(input.file) : undefined;
    const size = input.file?.size ?? 4096;
    const content = type === 'txt' && input.file ? await input.file.text() : `${input.name}\n\nOverview\n${input.description || 'A shared resource for your team.'}\n\n${input.template && input.template !== 'blank' ? `${input.template}\nAdd your objectives, key information, and next steps here.` : 'Start writing here. Share what you know and help your team move forward.'}`;
    const doc: Document = { id: newId('doc'), name: input.name.trim(), description: input.description, tags: input.tags, categoryId: input.categoryId, departmentId: input.departmentId, folderId: input.folderId, access: input.access, type, ownerId: user.id, createdAt: now, modifiedAt: now, version: 1, archived: false, starred: false, views: 0, size, content, fileUrl, fileName: input.file?.name, googleFileId: input.googleUrl?.split('/d/')[1].split('/')[0] ?? (type.startsWith('google') ? `atlas-demo-${crypto.randomUUID()}` : undefined), versions: input.file ? [{ number: 1, createdAt: now, uploadedBy: user.id, size, note: 'Initial upload', fileUrl, fileName: input.file.name, content }] : [] };
    input.tags.forEach(name => { if (!db.tags.some(t => t.name.toLowerCase() === name.toLowerCase())) db.tags.push({ id: newId('tag'), name, description: '' }); });
    db.documents.unshift(doc);
    return doc;
  });
}
export function updateDocument(id: string, changes: Partial<Pick<Document, 'name' | 'description' | 'tags' | 'content' | 'starred'>>, actor: User) {
  if (!USE_MOCKS) return live.updateDocument(id, changes);
  return request(() => { const doc = requireDocument(id, actor); assert(canEdit(activeUser(actor), doc)); assert(!doc.archived, 'Restore this document before editing.'); Object.assign(doc, changes, { modifiedAt: new Date().toISOString() }); return doc; });
}
export function bulkDocuments(ids: string[], action: 'archive' | 'restore' | 'delete' | 'move', actor: User, folderId?: string) {
  if (!USE_MOCKS) return live.bulkDocuments(ids, action, folderId);
  return request(() => {
    const user = activeUser(actor);
    const docs = ids.map(id => requireDocument(id, user));
    assert(docs.length, 'Select at least one document.');
    assert(docs.every(d => action === 'delete' ? isAdmin(user) : canManage(user, d)));
    if (action === 'move') { const folder = db.folders.find(f => f.id === folderId && !f.archived); assert(folder && canEdit(user, folder), 'You need edit access to the destination folder.'); }
    if (action === 'restore') assert(docs.every(d => !db.folders.find(f => f.id === d.folderId)?.archived), 'Restore the containing folder first.');
    if (action === 'delete') db.documents = db.documents.filter(d => !ids.includes(d.id));
    else docs.forEach(d => { if (action === 'move') d.folderId = folderId!; else d.archived = action === 'archive'; d.modifiedAt = new Date().toISOString(); });
    return ids.length;
  });
}
export function uploadVersion(id: string, file: File, actor: User) {
  if (!USE_MOCKS) return live.uploadVersion(id, file);
  return request(async () => {
    const doc = requireDocument(id, actor); assert(canEdit(activeUser(actor), doc)); assert(!doc.archived, 'Restore this document before editing.');
    assert(!doc.type.startsWith('google'), 'Google documents manage their own version history.');
    assert(validateUpload(file) === doc.type, 'The new version must have the same file type.');
    const fileUrl = URL.createObjectURL(file); if (doc.type === 'txt') doc.content = await file.text(); doc.version++; doc.size = file.size; doc.modifiedAt = new Date().toISOString(); doc.fileUrl = fileUrl; doc.fileName = file.name;
    doc.versions.unshift({ number: doc.version, createdAt: doc.modifiedAt, uploadedBy: actor.id, size: file.size, note: 'New version uploaded', fileUrl, fileName: file.name, content: doc.content });
    return doc;
  });
}
export function restoreVersion(id: string, version: number, actor: User) {
  if (!USE_MOCKS) return live.restoreVersion(id, version);
  return request(() => { const doc = requireDocument(id, actor); assert(canEdit(activeUser(actor), doc)); assert(!doc.archived, 'Restore this document before changing versions.'); const previous = doc.versions.find(v => v.number === version); assert(previous, 'Version not found.'); doc.version++; doc.modifiedAt = new Date().toISOString(); doc.fileUrl = previous.fileUrl; doc.fileName = previous.fileName; doc.size = previous.size; doc.content = previous.content ?? doc.content; doc.versions.unshift({ ...previous, number: doc.version, createdAt: doc.modifiedAt, uploadedBy: actor.id, note: `Restored from version ${version}` }); return doc; });
}
