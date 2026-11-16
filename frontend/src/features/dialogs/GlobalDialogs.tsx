import { useUIStore } from '@/store/ui';
import { AddDocumentDrawer } from '@/features/documents/AddDocumentDrawer';
import { PermissionsDialog } from '@/features/permissions/PermissionsDialog';
import { FolderDialog } from './FolderDialog';
import { MoveDialog } from './MoveDialog';
import { ConfirmActionDialog } from './ConfirmActionDialog';
export function GlobalDialogs() {
  const ui = useUIStore(); return <>
    {ui.addDocument && <AddDocumentDrawer />}
    {ui.permissions && <PermissionsDialog key={ui.permissions.id} target={ui.permissions} />}
    {ui.folderDialog && <FolderDialog />}
    {ui.moveTargets.length > 0 && <MoveDialog />}
    {ui.itemAction && <ConfirmActionDialog />}
  </>;
}
