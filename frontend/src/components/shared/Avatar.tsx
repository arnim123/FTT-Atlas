import { cn, initials } from '@/lib/utils';
const colors: Record<string, string> = { sage: 'bg-[#e1eae0] text-[#496847]', rose: 'bg-[#f3e4df] text-[#8b655e]', sand: 'bg-[#f3ebd9] text-[#8b764d]', lavender: 'bg-[#e9e5f1] text-[#736687]', blue: 'bg-[#e1eaf0] text-[#5d7589]' };
export function Avatar({ name, color = 'sage', size = 'md', className }: {
  name: string;
  color?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  className?: string;
}) { return <span title={name} className={cn('inline-flex shrink-0 select-none items-center justify-center rounded-full font-medium', colors[color], { 'h-5 w-5 text-[8px]': size === 'xs', 'h-7 w-7 text-[9px]': size === 'sm', 'h-9 w-9 text-[11px]': size === 'md', 'h-20 w-20 text-2xl': size === 'lg' }, className)}>{initials(name)}</span>; }
