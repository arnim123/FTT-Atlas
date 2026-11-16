import { create } from 'zustand';
import type { ResourceTarget } from '@/types';

export type DocumentTab = 'create' | 'link' | 'upload';
type FolderDialog = { mode: 'create' | 'rename'; id?: string; parentId?: string; name?: string };
type ItemAction = { action: 'archive' | 'delete' | 'restore'; targets: ResourceTarget[] };
interface UIState {
  sidebarOpen: boolean; setSidebarOpen: (open: boolean) => void;
  commandOpen: boolean; setCommandOpen: (open: boolean) => void;
  addDocument: DocumentTab | null; addFolderId: string; openAdd: (tab?: DocumentTab, folderId?: string) => void; closeAdd: () => void;
  permissions: ResourceTarget | null; setPermissions: (target: ResourceTarget | null) => void;
  folderDialog: FolderDialog | null; setFolderDialog: (dialog: FolderDialog | null) => void;
  moveTargets: ResourceTarget[]; setMoveTargets: (targets: ResourceTarget[]) => void;
  itemAction: ItemAction | null; setItemAction: (action: ItemAction | null) => void;
}
export const useUIStore = create<UIState>(set => ({
  sidebarOpen: false, setSidebarOpen: sidebarOpen => set({ sidebarOpen }),
  commandOpen: false, setCommandOpen: commandOpen => set({ commandOpen }),
  addDocument: null, addFolderId: 'root', openAdd: (tab = 'create', folderId = 'root') => set({ addDocument: tab, addFolderId: folderId }), closeAdd: () => set({ addDocument: null }),
  permissions: null, setPermissions: permissions => set({ permissions }),
  folderDialog: null, setFolderDialog: folderDialog => set({ folderDialog }),
  moveTargets: [], setMoveTargets: moveTargets => set({ moveTargets }),
  itemAction: null, setItemAction: itemAction => set({ itemAction }),
}));
