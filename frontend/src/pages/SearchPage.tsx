import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, Clock3, Search, SlidersHorizontal, X } from 'lucide-react';
import type { DocumentFilters as Filters } from '@/types';
import { searchDocuments } from '@/api';
import { useAuthStore } from '@/store/auth';
import { useDebounce } from '@/hooks/use-debounce';
import { useReferenceData } from '@/hooks/use-data';
import { useRecentSearches } from '@/hooks/use-recent-searches';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { EmptyState, ErrorState, PageSkeleton, Skeleton } from '@/components/shared/States';
import { PageHeading } from '@/components/shared/PageHeading';
import { DocumentFilters } from '@/features/documents/DocumentFilters';
import { SearchResultCard } from '@/features/search/SearchResultCard';
export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const user = useAuthStore(s => s.user);
  const reference = useReferenceData();
  const recent = useRecentSearches();
  const [query, setQuery] = useState(params.get('q') ?? '');
  const debounced = useDebounce(query, 300);
  const [filters, setFilters] = useState<Filters>({ sort: 'relevance' });
  const [showFilters, setShowFilters] = useState(false);
  useEffect(() => { setQuery(params.get('q') ?? ''); }, [params]);
  const active = !!debounced.trim() || Object.keys(filters).some(key => key !== 'sort' && filters[key as keyof Filters]);
  const results = useQuery({ queryKey: ['search', user.id, debounced, filters], queryFn: () => searchDocuments(debounced, filters, user), enabled: active });
  const search = (term: string) => { setQuery(term); setParams(term ? { q: term } : {}); recent.remember(term); };
  if (reference.error)
    return <div className="page-container"><ErrorState error={reference.error} retry={() => void reference.refetch()} /></div>;
  if (!reference.data)
    return <PageSkeleton />;
  return <div className="page-container">
    <PageHeading title="The answer is closer than you think." description="Search across documents, tags, and everything your team has shared." eyebrow="Workspace search" />
    <form onSubmit={e => { e.preventDefault(); search(query); }} className="panel mb-6 flex items-center gap-3 px-4 py-3 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/10">
      <Search size={21} className="text-primary" />
      <input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="What would you like to know? Try “Inventory”" aria-label="Search all knowledge" className="h-7 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-0" autoComplete="off" />
      {query && <button type="button" aria-label="Clear search" className="icon-button" onClick={() => search('')}><X size={15} /></button>}
      <Button type="submit" size="sm">Search</Button>
    </form>
    <div className="flex flex-col gap-5 md:flex-row">
      <div className="md:hidden">
        <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters}><SlidersHorizontal />Filters</Button>
      </div>
      <aside className={cn('panel h-fit shrink-0 p-5 md:w-[210px]', showFilters ? 'block' : 'hidden md:block')} aria-label="Search filters">
        <div className="mb-5 flex items-center gap-2">
          <SlidersHorizontal size={14} className="text-muted-foreground" />
          <h2 className="text-xs font-semibold">Refine your search</h2>
        </div>
        <DocumentFilters filters={filters} onChange={setFilters} reference={reference.data} vertical dates />
        <label className="mt-6 flex cursor-pointer items-center gap-2 border-t pt-5 text-[10px]"><Checkbox checked={!!filters.includeArchived} onCheckedChange={checked => setFilters({ ...filters, includeArchived: checked === true })} />Include archived documents</label>
      </aside>
      <section className="min-w-0 flex-1" aria-live="polite">{!active ? <div>
        <div className="panel mb-5">
          <EmptyState search title="A good question is a great start." description="Find the how-to, the next step, or the detail you’re looking for. Search by name, tag, or a phrase from a document." />
          <div className="-mt-5 mb-8 flex flex-wrap justify-center gap-2">{['Inventory', 'Onboarding', 'ERP Lens', 'Security'].map(term => <Button key={term} size="sm" variant="outline" onClick={() => search(term)}>{term}<ArrowUpRight className="!size-3" /></Button>)}</div>
        </div>
        <div className="panel p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-xs font-medium"><Clock3 size={14} className="text-muted-foreground" />Recent searches</h2>
            {recent.recent.length > 0 && <button className="rounded text-[10px] text-muted-foreground hover:text-primary" onClick={recent.clear}>Clear history</button>}
          </div>
          {recent.recent.length ? recent.recent.map(term => <button key={term} onClick={() => search(term)} className="flex w-full items-center justify-between rounded-md px-2 py-2.5 text-left text-xs text-muted-foreground hover:bg-muted">
            <span>{term}</span>
            <ArrowUpRight size={12} />
          </button>) : <p className="py-3 text-[11px] text-muted-foreground">Your recent searches will appear here.</p>}
        </div>
      </div> : <>
        <div className="mb-4 flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">{results.isPending || query !== debounced ? 'Searching your workspace…' : <>
            <span className="font-semibold text-foreground">{results.data?.length ?? 0} results</span>
            {debounced && <> for “{debounced}”</>}
          </>}</p>
          <select className="select-input w-36 text-[10px]" aria-label="Sort search results" value={filters.sort} onChange={e => setFilters({ ...filters, sort: e.target.value as Filters['sort'] })}>
            <option value="relevance">Most relevant</option>
            <option value="modified">Recently modified</option>
            <option value="oldest">Oldest first</option>
          </select>
        </div>
        {results.error ? <ErrorState error={results.error} retry={() => void results.refetch()} /> : results.isPending || query !== debounced ? <div className="space-y-4" role="status" aria-label="Searching documents">{[1, 2, 3].map(i => <Skeleton key={i} className="h-40" />)}</div> : !results.data?.length ? <div className="panel"><EmptyState search title="No matches, yet." description="Try a broader phrase, check your spelling, or clear a filter. You’ll only see documents your role can access." action={<Button variant="outline" onClick={() => { setFilters({ sort: 'relevance' }); search('Inventory'); }}>Try “Inventory”</Button>} /></div> : <div className="space-y-3">{results.data.map(result => <SearchResultCard key={result.document.id} result={result} query={debounced} reference={reference.data} onOpen={() => recent.remember(query)} />)}</div>}
      </>}</section>
    </div>
  </div>;
}
