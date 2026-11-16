import { db } from '@/mocks/db';
import type { Folder, User } from '@/types';
import { canCreate, canEdit, canManage, canView, isAdmin } from '@/lib/access';
import { DEFAULT_ACCESS } from '@/lib/constants';
import { USE_MOCKS, activeUser, assert, newId, request } from './client';
import * as live from './live';
import { folderDescendants } from './documents';

export function listFolderTree(actor: User) {
  if (!USE_MOCKS) return live.listFolderTree();
  return request(() => {
    const user = activeUser(actor);
    return db.folders.filter(f => !f.archived).map(f => ({ ...f, restricted: !canView(user, f), documentCount: db.documents.filter(d => !d.archived && folderDescendants(f.id).includes(d.folderId) && canView(user, d)).length }));
  });
}
export function getFolder(id: string, actor: User) { return request(() => { const folder = db.folders.find(f => f.id === id); assert(folder, 'Folder not found.'); assert(canView(activeUser(actor), folder)); return folder; }); }
export function createFolder(input: { name: string; parentId: string; departmentId: string }, actor: User) {
  if (!USE_MOCKS) return live.createFolder(input, []);
  return request(() => {
    const user = activeUser(actor); assert(canCreate(user)); assert(input.name.trim(), 'Enter a folder name.');
    assert(db.departments.some(d => d.id === input.departmentId), 'Choose a valid department.');
    assert(isAdmin(user) || input.departmentId === user.departmentId, 'You can only create folders for your own department.');
    const parent = db.folders.find(f => f.id === input.parentId && !f.archived); assert(parent && canEdit(user, parent), 'You need edit access to the parent folder.');
    assert(!db.folders.some(f => f.parentId === input.parentId && !f.archived && f.name.toLowerCase() === input.name.trim().toLowerCase()), 'A folder with this name already exists here.');
    const folder: Folder = { id: newId('folder'), name: input.name.trim(), parentId: input.parentId, departmentId: input.departmentId, ownerId: user.id, access: structuredClone({ ...DEFAULT_ACCESS, defaultPermission: 'edit' }), archived: false };
    db.folders.push(folder); return folder;
  });
}
export function updateFolder(id: string, changes: { name?: string; parentId?: string; archived?: boolean }, actor: User) {
  if (!USE_MOCKS) return live.updateFolder(id, changes);
  return request(() => {
    const user = activeUser(actor); const folder = db.folders.find(f => f.id === id); assert(folder, 'Folder not found.'); assert(id !== 'root', 'The workspace root cannot be changed.'); assert(canManage(user, folder));
    if (changes.name !== undefined) { assert(changes.name.trim(), 'Enter a folder name.'); assert(!db.folders.some(f => f.id !== id && !f.archived && f.parentId === folder.parentId && f.name.toLowerCase() === changes.name!.trim().toLowerCase()), 'A folder with this name already exists here.'); changes.name = changes.name.trim(); }
    if (changes.parentId) { assert(!folderDescendants(id).includes(changes.parentId), 'A folder cannot be moved into itself or one of its subfolders.'); const target = db.folders.find(f => f.id === changes.parentId && !f.archived); assert(target && canEdit(user, target), 'You need edit access to the destination folder.'); }
    if (changes.archived !== undefined) { const ids = folderDescendants(id); const nested = db.documents.filter(d => ids.includes(d.folderId)); assert(nested.every(d => canManage(user, d)), 'This folder contains documents managed by another owner. Ask an administrator to archive it.'); if (!changes.archived) assert(!db.folders.find(f => f.id === folder.parentId)?.archived, 'Restore the parent folder first.'); db.folders.filter(f => ids.includes(f.id)).forEach(f => f.archived = changes.archived!); nested.forEach(d => d.archived = changes.archived!); }
    Object.assign(folder, changes); return folder;
  });
}
export function deleteFolder(id: string, actor: User) {
  if (!USE_MOCKS) return live.deleteFolder(id);
  return request(() => { assert(isAdmin(activeUser(actor))); assert(id !== 'root', 'The workspace root cannot be deleted.'); assert(db.folders.some(f => f.id === id), 'Folder not found.'); const ids = folderDescendants(id); db.documents = db.documents.filter(d => !ids.includes(d.folderId)); db.folders = db.folders.filter(f => !ids.includes(f.id)); });
}
