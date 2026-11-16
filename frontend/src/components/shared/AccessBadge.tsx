import { Building2, LockKeyhole, Users, Globe2 } from 'lucide-react';
import type { AccessLevel } from '@/types';
import { ACCESS_LABELS } from '@/lib/constants';
import { cn } from '@/lib/utils';
export function AccessBadge({ level, compact }: {
  level: AccessLevel;
  compact?: boolean;
}) { const Icon = { private: LockKeyhole, department: Building2, organization: Globe2, custom: Users }[level]; return <span title={`${ACCESS_LABELS[level]} access`} className={cn('inline-flex items-center gap-1.5 whitespace-nowrap rounded px-1.5 py-1 text-[10px]', level === 'private' ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400' : level === 'organization' ? 'bg-primary/[0.06] text-primary' : 'bg-muted text-muted-foreground')}><Icon size={11} />{!compact && ACCESS_LABELS[level]}</span>; }
