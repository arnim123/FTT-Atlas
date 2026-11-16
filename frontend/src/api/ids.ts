let workspaceRootId: string | null = null;

export function rememberWorkspaceRoot(id: string) {
  workspaceRootId = id;
}

export function toApiFolderId(id: string | null | undefined): string | null {
  if (!id || id === 'root') return workspaceRootId;
  return id;
}

export function toUiFolderId(id: string | null | undefined): string | null {
  if (!id) return null;
  if (workspaceRootId && id === workspaceRootId) return 'root';
  return id;
}
