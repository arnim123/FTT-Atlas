import { cn } from '@/lib/utils';
export function Brand({ light = false, compact = false }: {
  light?: boolean;
  compact?: boolean;
}) {
  return <div className={cn('flex items-center gap-2.5', light && 'text-white')}>
    <span className={cn('grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground', light && 'bg-white/15 text-white')}>
      <svg width="23" height="23" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M8 25 16 8l8 17M11.5 19h9" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </span>
    {!compact && <span className="text-[25px] font-semibold tracking-[-1.2px]">atlas<span className="text-primary">.</span></span>}
  </div>;
}
