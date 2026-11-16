import type { ReactNode } from 'react';
import { AlertCircle, ArrowLeft, FolderOpen, RotateCw, SearchX } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn, errorMessage } from '@/lib/utils';
export function Skeleton({ className }: {
  className?: string;
}) { return <div aria-hidden="true" className={cn('animate-pulse rounded-md bg-muted', className)} />; }
export function PageSkeleton({ rows = 6 }: {
  rows?: number;
}) {
  return <div className="space-y-6 p-6" role="status" aria-label="Loading content">
    <span className="sr-only">Loading content…</span>
    <Skeleton className="h-7 w-56" />
    <Skeleton className="h-4 w-72 max-w-full" />
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div>
    <div className="panel divide-y px-5">{Array.from({ length: rows }, (_, i) => <div className="flex gap-4 py-5" key={i}>
      <Skeleton className="h-9 w-9" />
      <div className="flex-1 space-y-2"><Skeleton className="h-3 w-2/3" /><Skeleton className="h-2 w-1/3" /></div>
    </div>)}</div>
  </div>;
}
export function EmptyState({ title = 'Nothing here just yet', description = 'Add a document to start building your team’s knowledge.', action, search }: {
  title?: string;
  description?: string;
  action?: ReactNode;
  search?: boolean;
}) {
  const Icon = search ? SearchX : FolderOpen; return <div className="flex min-h-64 flex-col items-center justify-center px-6 py-12 text-center">
    <div className="mb-4 grid h-14 w-14 place-items-center rounded-xl border bg-muted/50 text-primary"><Icon size={24} strokeWidth={1.4} /></div>
    <h3 className="text-sm font-semibold">{title}</h3>
    <p className="mt-2 max-w-sm text-xs leading-relaxed text-muted-foreground">{description}</p>
    {action && <div className="mt-5">{action}</div>}
  </div>;
}
export function ErrorState({ error, retry }: {
  error: unknown;
  retry?: () => void;
}) {
  return <div className="panel my-5 flex flex-col items-center gap-3 p-10 text-center" role="alert">
    <AlertCircle className="text-destructive" size={28} />
    <h2 className="font-semibold">We couldn’t load this content</h2>
    <p className="max-w-md text-xs leading-relaxed text-muted-foreground">{errorMessage(error)}</p>
    {retry && <Button onClick={retry} variant="outline"><RotateCw />Try again</Button>}
  </div>;
}
export function AccessDenied() {
  return <div className="page-container"><EmptyState title="This space is restricted" description="Your current role doesn’t have access to this page. Your workspace dashboard is a good place to start." action={<Button asChild>
    <Link to="/dashboard"><ArrowLeft />Back to dashboard</Link>
  </Button>} /></div>;
}
