import { ArrowUpRight, Bot, FileText, FolderPlus, LockKeyhole, Sparkles, Users } from 'lucide-react';
import type { Dashboard } from '@/types';
import { cn } from '@/lib/utils';
export function StatCards({ data, admin = false }: {
  data: Dashboard;
  admin?: boolean;
}) {
  const stats = [{ label: 'Total documents', value: data.totalDocuments, icon: FileText, foot: 'A growing source of truth', change: `${data.addedThisMonth} new` }, { label: 'Added this month', value: data.addedThisMonth, icon: FolderPlus, foot: 'Knowledge worth sharing', change: 'This month' }, { label: 'Active users', value: data.activeUsers, icon: Users, foot: 'Connected through knowledge', change: 'Workspace members' }];
  return <div className={cn('grid grid-cols-2 gap-3 xl:gap-4', admin ? 'xl:grid-cols-5' : 'xl:grid-cols-4')}>
    {stats.map(({ label, value, icon: Icon, foot, change }, index) => <div key={label} className="panel relative overflow-hidden p-4 lg:p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
        <span className="grid h-7 w-7 place-items-center rounded-md bg-muted text-primary"><Icon size={15} strokeWidth={1.6} /></span>
      </div>
      <div className="mt-3 flex items-baseline gap-2.5">
        <span className="text-[31px] font-semibold leading-none tracking-[-1px]">{value}</span>
        {index === 0 && <span className="flex items-center gap-0.5 text-[9px] font-medium text-primary"><ArrowUpRight size={11} />{change}</span>}
      </div>
      <p className="mt-3.5 text-[10px] text-muted-foreground">{foot}</p>
      <svg aria-hidden="true" viewBox="0 0 85 28" className="absolute bottom-9 right-4 h-7 w-[70px] text-primary/25"><path d={index === 0 ? 'M0 26 10 21 21 23 31 12 42 17 52 8 62 10 73 2 84 5' : index === 1 ? 'M0 25 12 25 23 18 33 22 45 12 58 14 70 6 84 3' : 'M0 22 12 18 24 20 36 13 48 15 60 6 72 8 84 3'} stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </div>)}
    {admin && <AgentCalls data={data} />}
    <div className="panel locked-pattern relative p-4 lg:p-5">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium text-muted-foreground">AI questions asked</p>
        <Sparkles size={16} className="text-muted-foreground/60" strokeWidth={1.5} />
      </div>
      <div className="mt-5 flex items-center gap-2.5">
        <span className="text-2xl leading-none text-muted-foreground/50">—</span>
        <span className="flex items-center gap-1 rounded-full border bg-card px-2 py-0.5 text-[8px] text-muted-foreground"><LockKeyhole size={9} />Coming in Phase 2</span>
      </div>
      <p className="mt-4 text-[10px] text-muted-foreground">A smarter way to find your answers</p>
    </div>
  </div>;
}
function AgentCalls({ data }: { data: Dashboard }) {
  const points = data.agentSparkline.length > 1 ? data.agentSparkline : [0, 0];
  const max = Math.max(...points, 1);
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'}${((index / (points.length - 1)) * 84).toFixed(1)} ${(24 - (point / max) * 20).toFixed(1)}`).join(' ');
  return <div className="panel relative overflow-hidden p-4 lg:p-5">
    <div className="flex items-center justify-between gap-2">
      <p className="text-[11px] font-medium text-muted-foreground">AI agent calls (30d)</p>
      <span className="grid h-7 w-7 place-items-center rounded-md bg-muted text-primary"><Bot size={15} strokeWidth={1.6} /></span>
    </div>
    <div className="mt-3"><span className="text-[31px] font-semibold leading-none tracking-[-1px]">{data.agentCalls30d}</span></div>
    <p className="mt-3.5 text-[10px] text-muted-foreground">External REST and MCP calls</p>
    <svg aria-label="AI agent calls over the last 14 days" role="img" viewBox="0 0 85 28" className="absolute bottom-9 right-4 h-7 w-[70px] text-primary/40"><path d={path} stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
  </div>;
}
