import { renderToString } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import * as api from '@/api';
import { AppShell } from '@/components/layout/AppShell';
import { DashboardPage } from '@/pages/DashboardPage';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { DocumentViewerPage } from '@/pages/DocumentViewerPage';
import { SearchPage } from '@/pages/SearchPage';
import { ArchivePage } from '@/pages/ArchivePage';
import { UsersPage } from '@/pages/UsersPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { LoginPage } from '@/pages/LoginPage';
import { GooglePreviewPage } from '@/pages/GooglePreviewPage';
import { IntegrationsPage } from '@/pages/IntegrationsPage';
import { OAuthConsentPage } from '@/pages/OAuthConsentPage';
import { AccessDenied } from '@/components/shared/States';
import { canManageUsers, canUseIntegrations, isAdmin } from '@/lib/access';
import { integrationQuery } from '@/features/integrations/query';
import { AccessPicker } from '@/features/permissions/AccessPicker';
import { Highlight } from '@/features/search/Highlight';
import type { Role } from '@/types';

export async function renderScreen(path: string, role: Role = 'super_admin') {
  const actor = await api.getRoleIdentity(role);
  useAuthStore.setState({ user: actor, authenticated: true });
  // Zustand's bound hook closes over the original API. Set that server snapshot for this request.
  Object.assign(useAuthStore.getInitialState(), { user: actor, authenticated: true });
  useUIStore.setState({ sidebarOpen: false, commandOpen: false, addDocument: null, permissions: null, folderDialog: null, moveTargets: [], itemAction: null });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  const url = new URL(path, 'http://localhost');
  const folder = url.searchParams.get('folder') ?? 'root';
  const query = url.searchParams.get('q') ?? '';
  const set = (key: unknown[], value: unknown) => client.setQueryData(key, value);
  set(['reference', actor.id], await api.getReferenceData(actor));
  set(['folders', actor.id], await api.listFolderTree(actor));
  set(['dashboard', actor.id], await api.getDashboard(actor));
  set(['documents', actor.id, folder, { sort: 'modified' }, ''], await api.listDocuments(actor, { folderId: folder, sort: 'modified' }));
  set(['archive', actor.id], await api.listArchived(actor));
  set(['profile', actor.id], await api.getProfile(actor));
  if (query) set(['search', actor.id, query, { sort: 'relevance' }], await api.searchDocuments(query, { sort: 'relevance' }, actor));
  if (canManageUsers(actor)) set(['users', actor.id, '', { role: '', departmentId: '', status: '' }], await api.listUsers(actor));
  if (isAdmin(actor)) {
    set(['taxonomy', 'departments', actor.id], await api.listTaxonomy('departments', actor));
    set(integrationQuery.tokens(actor.id, true), await api.listTokens(actor, { everyone: true }));
  }
  if (url.pathname === '/integrations' && canUseIntegrations(actor)) set(integrationQuery.settings(actor.id), await api.getOrgSettings(actor));
  if (url.pathname === '/oauth/consent' && canUseIntegrations(actor)) {
    const consentQuery = { app: url.searchParams.get('app') ?? '', redirectUri: url.searchParams.get('redirect_uri') ?? '', verified: url.searchParams.get('verified') ?? '', scope: url.searchParams.get('scope') ?? '' };
    set(integrationQuery.consent(actor.id, consentQuery.app, consentQuery.redirectUri, consentQuery.verified, consentQuery.scope), await api.getConsentRequest(consentQuery, actor));
  }
  const documentId = /^\/(documents|google-preview)\/(.+)/.exec(url.pathname)?.[2];
  if (documentId) {
    set(['document', documentId, actor.id], await api.getDocument(documentId, actor));
    set(['related', documentId, actor.id], await api.getRelatedDocuments(documentId, actor));
    set(integrationQuery.access(documentId, actor.id), await api.listDocumentAccess(documentId, actor));
  }
  const html = renderToString(<QueryClientProvider client={client}><TooltipProvider><StaticRouter location={path}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/google-preview/:id" element={<GooglePreviewPage />} />
    <Route path="/oauth/consent" element={<OAuthConsentPage />} />
    <Route element={<AppShell />}>
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/documents" element={<DocumentsPage />} />
      <Route path="/documents/:id" element={<DocumentViewerPage />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="/archive" element={<ArchivePage />} />
      <Route path="/integrations" element={canUseIntegrations(actor) ? <IntegrationsPage /> : <AccessDenied />} />
      <Route path="/users" element={canManageUsers(actor) ? <UsersPage /> : <AccessDenied />} />
      <Route path="/settings" element={isAdmin(actor) ? <SettingsPage /> : <AccessDenied />} />
      <Route path="/profile" element={<ProfilePage />} />
    </Route>
  </Routes></StaticRouter></TooltipProvider></QueryClientProvider>);
  client.clear();
  return html;
}

export async function renderAccessPicker() {
  const actor = api.getInitialUser();
  const reference = await api.getReferenceData(actor);
  return renderToString(<AccessPicker value={{ level: 'custom', defaultPermission: 'view', syncStatus: 'failed', grants: [{ principalType: 'user', principalId: 'u5', permission: 'view' }] }} onChange={() => undefined} reference={reference} ownerId={actor.id} departmentId={actor.departmentId} />);
}

export function renderHighlight(text: string, query: string) {
  return renderToString(<Highlight text={text} query={query} />);
}
