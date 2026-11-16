import { Outlet, useLocation } from 'react-router-dom';
import { Suspense, useEffect } from 'react';
import { PageSkeleton } from '@/components/shared/States';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { RoleSwitcher } from './RoleSwitcher';
import { CommandPalette } from '@/features/search/CommandPalette';
import { GlobalDialogs } from '@/features/dialogs/GlobalDialogs';
import { useUIStore } from '@/store/ui';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
export function AppShell() {
  const open = useUIStore(s => s.sidebarOpen);
  const setOpen = useUIStore(s => s.setSidebarOpen);
  const location = useLocation();
  useEffect(() => { window.scrollTo({ top: 0 }); document.title = `Atlas · ${location.pathname.split('/')[1]?.replace(/^./, c => c.toUpperCase()) || 'Workspace'}`; }, [location.pathname]);
  return <>
    <a href="#main-content" className="fixed left-1/2 top-2 z-[100] -translate-x-1/2 -translate-y-20 rounded bg-primary px-4 py-2 text-primary-foreground focus:translate-y-0">Skip to content</a>
    <Sidebar />
    <div className="min-h-screen lg:ml-[224px]">
      <Topbar />
      <main id="main-content" className="pb-12" tabIndex={-1}>
        <Suspense fallback={<PageSkeleton />}><Outlet /></Suspense>
      </main>
    </div>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent drawer className="left-0 right-auto max-w-[250px] p-0 [&>button]:hidden">
        <DialogTitle className="sr-only">Workspace navigation</DialogTitle>
        <DialogDescription className="sr-only">Navigate your company knowledge workspace.</DialogDescription>
        <Sidebar mobile />
      </DialogContent>
    </Dialog>
    <CommandPalette />
    <GlobalDialogs />
    <RoleSwitcher />
  </>;
}
