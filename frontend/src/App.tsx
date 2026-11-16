import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes, Link } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { ApiError, USE_MOCKS, restoreSession } from '@/api';
import { queryClient } from '@/lib/query-client';
import { useAuthStore } from '@/store/auth';
import { useTheme } from '@/hooks/use-theme';
import { canManageUsers, canUseIntegrations, isAdmin } from '@/lib/access';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { AccessDenied, EmptyState, ErrorState, PageSkeleton } from '@/components/shared/States';
import { AppShell } from '@/components/layout/AppShell';
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then(module => ({ default: module.DashboardPage })));
const DocumentsPage = lazy(() => import('@/pages/DocumentsPage').then(module => ({ default: module.DocumentsPage })));
const DocumentViewerPage = lazy(() => import('@/pages/DocumentViewerPage').then(module => ({ default: module.DocumentViewerPage })));
const GooglePreviewPage = lazy(() => import('@/pages/GooglePreviewPage').then(module => ({ default: module.GooglePreviewPage })));
const SearchPage = lazy(() => import('@/pages/SearchPage').then(module => ({ default: module.SearchPage })));
const ArchivePage = lazy(() => import('@/pages/ArchivePage').then(module => ({ default: module.ArchivePage })));
const UsersPage = lazy(() => import('@/pages/UsersPage').then(module => ({ default: module.UsersPage })));
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then(module => ({ default: module.SettingsPage })));
const ProfilePage = lazy(() => import('@/pages/ProfilePage').then(module => ({ default: module.ProfilePage })));
const LoginPage = lazy(() => import('@/pages/LoginPage').then(module => ({ default: module.LoginPage })));
const IntegrationsPage = lazy(() => import('@/pages/IntegrationsPage').then(module => ({ default: module.IntegrationsPage })));
const OAuthConsentPage = lazy(() => import('@/pages/OAuthConsentPage').then(module => ({ default: module.OAuthConsentPage })));
function SessionGate({ children }: { children: ReactNode }) {
  const ready = useAuthStore(s => s.ready);
  const setUser = useAuthStore(s => s.setUser);
  const signOut = useAuthStore(s => s.signOut);
  const [started, setStarted] = useState(USE_MOCKS);
  const [connectionError, setConnectionError] = useState<unknown>(null);
  useEffect(() => {
    if (USE_MOCKS || started) return;
    setStarted(true);
    restoreSession().then(user => { setConnectionError(null); setUser(user); }).catch(error => {
      if (error instanceof ApiError && error.status === 401) { signOut(); return; }
      setConnectionError(error);
    });
  }, [setUser, signOut, started]);
  if (connectionError) return <div className="grid min-h-screen place-items-center px-6"><ErrorState error={connectionError} retry={() => { setConnectionError(null); setStarted(false); }} /></div>;
  if (!ready) return <PageSkeleton />;
  return children;
}
function RequireSession({ children }: {
  children: ReactNode;
}) { const authenticated = useAuthStore(s => s.authenticated); return authenticated ? children : <Navigate to="/login" replace />; }
function AdminRoute({ children, managers = false }: {
  children: ReactNode;
  managers?: boolean;
}) { const user = useAuthStore(s => s.user); return (managers ? canManageUsers(user) : isAdmin(user)) ? children : <AccessDenied />; }
function MemberRoute({ children }: { children: ReactNode }) { const user = useAuthStore(s => s.user); return canUseIntegrations(user) ? children : <AccessDenied />; }
export function App() {
  const { theme } = useTheme();
  useEffect(() => { document.documentElement.classList.toggle('dark', theme === 'dark'); }, [theme]);
  return <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={250}>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <SessionGate>
          <Suspense fallback={<PageSkeleton />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/google-preview/:id" element={<RequireSession><GooglePreviewPage /></RequireSession>} />
              <Route path="/oauth/consent" element={<RequireSession><OAuthConsentPage /></RequireSession>} />
              <Route element={<RequireSession><AppShell /></RequireSession>}><Route index element={<Navigate to="/dashboard" replace />} /><Route path="/dashboard" element={<DashboardPage />} /><Route path="/documents" element={<DocumentsPage />} /><Route path="/documents/:id" element={<DocumentViewerPage />} /><Route path="/search" element={<SearchPage />} /><Route path="/archive" element={<ArchivePage />} /><Route path="/integrations" element={<MemberRoute><IntegrationsPage /></MemberRoute>} /><Route path="/users" element={<AdminRoute managers><UsersPage /></AdminRoute>} /><Route path="/settings" element={<AdminRoute><SettingsPage /></AdminRoute>} /><Route path="/profile" element={<ProfilePage />} /><Route path="*" element={<div className="page-container"><EmptyState title="Looks like a wrong turn." description="This page doesn't exist. Your team’s knowledge is just a click away." action={<Button asChild>
                <Link to="/dashboard">Back to dashboard</Link>
              </Button>} /></div>} /></Route>
            </Routes>
          </Suspense>
          </SessionGate>
        </BrowserRouter>
        <Toaster position="bottom-left" theme={theme} richColors closeButton toastOptions={{ style: { fontFamily: 'Inter, sans-serif', fontSize: '12px' } }} />
      </TooltipProvider>
    </QueryClientProvider>
  </ErrorBoundary>;
}
