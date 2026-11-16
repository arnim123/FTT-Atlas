import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, CalendarDays, Plus, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getDashboard } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useUIStore } from '@/store/ui';
import { useReferenceData } from '@/hooks/use-data';
import { canCreate, isAdmin } from '@/lib/access';
import { Button } from '@/components/ui/button';
import { ErrorState, PageSkeleton } from '@/components/shared/States';
import { PageHeading } from '@/components/shared/PageHeading';
import { StatCards } from '@/features/dashboard/StatCards';
import { DepartmentChart } from '@/features/dashboard/DepartmentChart';
import { RecentDocuments } from '@/features/dashboard/RecentDocuments';
import { PopularDocuments } from '@/features/dashboard/PopularDocuments';
import { Collections } from '@/features/dashboard/Collections';
export function DashboardPage() {
  const user = useAuthStore(s => s.user);
  const openAdd = useUIStore(s => s.openAdd);
  const reference = useReferenceData();
  const { data, isPending, error, refetch } = useQuery({ queryKey: ['dashboard', user.id], queryFn: () => getDashboard(user) });
  if (error || reference.error)
    return <div className="page-container"><ErrorState error={error ?? reference.error} retry={() => { void refetch(); void reference.refetch(); }} /></div>;
  if (isPending || !data || !reference.data)
    return <PageSkeleton />;
  return <div className="page-container">
    <div className="mb-5 flex items-center justify-between">
      <p className="flex items-center gap-1.5 text-[10px] text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-primary" />A little more connected, every day.</p>
      <span className="hidden items-center gap-1.5 text-[10px] text-muted-foreground sm:flex"><CalendarDays size={12} />{new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }).format(new Date())}</span>
    </div>
    <PageHeading title={`Welcome back, ${user.name.split(' ')[0]}.`} description="Your team's knowledge, all in one place. Pick up where you left off.">{canCreate(user) && <Button onClick={() => openAdd('upload')}><Plus size={15} />Add document</Button>}</PageHeading>


    <StatCards data={data} admin={isAdmin(user)} />


    <div className="mb-3 mt-7 flex items-center justify-between">
      <h2 className="text-[12px] font-semibold">A place for every team</h2>
      <Link to="/documents" className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-primary">Browse all folders<ArrowUpRight size={12} /></Link>
    </div>
    <Collections />


    <div className="mt-6 grid grid-cols-1 gap-5 xl:grid-cols-[1.65fr_1fr]">
      <DepartmentChart data={data} />
      <div className="relative flex min-h-[290px] flex-col justify-between overflow-hidden rounded-lg border border-primary/10 bg-[#eaf0e8] p-6 dark:bg-[#1b2c25]">
        <div className="relative z-10 max-w-[235px]">
          <span className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-primary/15 bg-white/40 px-2 py-1 text-[8px] font-medium text-primary dark:bg-primary/10"><Sparkles size={10} />A LITTLE LESS SEARCHING</span>
          <h2 className="text-[24px] font-semibold leading-[1.3] tracking-[-0.6px] text-[#254c3f] dark:text-[#c2d9ca]">Great work starts<br />with shared knowledge.</h2>
          <p className="mt-3 max-w-[215px] text-[11px] leading-relaxed text-[#6b8075] dark:text-[#95b19f]">From the first-day essentials to the details that make a difference. It's all here.</p>
        </div>
        <Link to="/search" className="relative z-10 mt-5 flex w-fit items-center gap-2 text-[11px] font-semibold text-primary">Find your next answer<ArrowUpRight size={14} /></Link>
        <KnowledgeIllustration />
      </div>
    </div>


    <div className="mt-6 grid grid-cols-1 items-start gap-5 xl:grid-cols-[1.65fr_1fr]"><RecentDocuments documents={data.recent} reference={reference.data} /><PopularDocuments documents={data.popular} /></div>


    <footer className="mt-6 flex items-center justify-between text-[9px] text-muted-foreground/80">
      <span>A shared space for everything that moves us forward.</span>
      <span className="hidden sm:inline">Made for your team. Built on trust.</span>
    </footer>


  </div>;
}
function KnowledgeIllustration() { return <svg aria-hidden="true" viewBox="0 0 210 240" className="pointer-events-none absolute -bottom-5 -right-7 w-[190px] opacity-80 2xl:right-0 2xl:w-[210px]" fill="none"><circle cx="139" cy="129" r="77" stroke="#97b39b" strokeOpacity=".4" /><circle cx="139" cy="129" r="57" stroke="#97b39b" strokeOpacity=".3" /><path d="m68 95 90-18 20 122-90 18z" fill="#93ae93" /><path d="m83 76 91 8-11 123-91-8z" fill="#f8faf4" stroke="#aebfac" /><path d="m100 67 87 30-40 116-87-30z" fill="#f8faf4" stroke="#aebfac" /><path d="m114 90 49 17M108 103l49 17M103 116l33 12" stroke="#adc0a7" strokeWidth="3" strokeLinecap="round" /><rect x="99" y="138" width="41" height="33" rx="4" transform="rotate(19 99 138)" fill="#e2eadc" /><path d="m174 49 3 8 9 3-9 3-3 9-3-9-9-3 9-3z" fill="#5b8567" /><path d="m59 151 2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="#5b8567" /><circle cx="57" cy="84" r="3" fill="#aabd9d" /><circle cx="186" cy="179" r="4" fill="#aabd9d" /></svg>; }
