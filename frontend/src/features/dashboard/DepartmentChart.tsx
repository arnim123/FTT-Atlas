import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BarChart3 } from 'lucide-react';
import type { Dashboard } from '@/types';
import { EmptyState } from '@/components/shared/States';
export function DepartmentChart({ data }: {
  data: Dashboard;
}) {
  return <section className="panel min-w-0">
    <div className="flex items-center justify-between px-5 pb-0 pt-5">
      <div>
        <h2 className="text-[13px] font-semibold tracking-tight">Knowledge across teams</h2>
        <p className="mt-1.5 text-[10px] text-muted-foreground">Documents by department</p>
      </div>
      <span className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-[9px] text-muted-foreground"><BarChart3 size={11} />All documents</span>
    </div>
    {!data.totalDocuments ? <EmptyState title="Your chart starts here" description="Add a document to see how knowledge is shared across your teams." /> : <>
      <div className="h-[210px] px-3 pb-1 pt-6" role="img" aria-label={data.byDepartment.map(d => `${d.name}: ${d.count} documents`).join(', ')}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <BarChart data={data.byDepartment} margin={{ left: -22, right: 8, top: 8, bottom: 0 }} barSize={43}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 9 }} tickFormatter={name => name === 'People & Culture' ? 'People & Culture' : name} dy={8} interval={0} />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 9 }} allowDecimals={false} />
            <Tooltip cursor={{ fill: 'hsl(var(--muted))' }} contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, fontSize: 11, color: 'hsl(var(--foreground))' }} formatter={(value: number) => [`${value} documents`, 'Total']} />
            <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={false}>{data.byDepartment.map(dept => <Cell key={dept.name} fill={dept.color} />)}</Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mx-5 flex items-center gap-1.5 border-t py-3 text-[9px] text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-primary" />{data.byDepartment.filter(d => d.count > 0).length} departments contributing to your workspace</div>
    </>}
  </section>;
}
