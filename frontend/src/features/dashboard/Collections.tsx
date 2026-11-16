import { ArrowUpRight, FolderOpen } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useFolders } from '@/hooks/use-data';
export function Collections() {
  const { data } = useFolders();
  const collections = [{ id: 'hr', title: 'People & Culture', description: 'For a better workday', tone: 'bg-[#f4f1e8] text-[#9a8b62] dark:bg-[#322f25] dark:text-[#bdaf87]' }, { id: 'products', title: 'Product & Engineering', description: 'Built to move us forward', tone: 'bg-[#eaf0e9] text-[#698c6c] dark:bg-[#253429] dark:text-[#9ab79d]' }, { id: 'sales', title: 'Sales enablement', description: 'Turn conversations into growth', tone: 'bg-[#ebeff5] text-[#7a8daa] dark:bg-[#28303c] dark:text-[#a4b3cc]' }];
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">{collections.map(item => <Link to={`/documents?folder=${item.id}`} key={item.id} className="panel group flex items-center gap-3.5 p-4 transition-all hover:border-primary/30 hover:shadow-md">
    <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg ${item.tone}`}><FolderOpen size={20} strokeWidth={1.5} fill="currentColor" fillOpacity={0.1} /></span>
    <div className="min-w-0 flex-1">
      <p className="truncate text-[11px] font-semibold">{item.title}</p>
      <p className="mt-1 truncate text-[9px] text-muted-foreground">
        {data ? `${data.find(f => f.id === item.id)?.documentCount ?? 0} documents` : 'Loading collection…'}
        <span className="mx-1.5">·</span>
        {item.description}
      </p>
    </div>
    <ArrowUpRight size={14} className="shrink-0 text-muted-foreground/60 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
  </Link>)}</div>;
}
