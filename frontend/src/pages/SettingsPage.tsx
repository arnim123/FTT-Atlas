import { Building2, Hash, Shapes, ShieldCheck } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeading } from '@/components/shared/PageHeading';
import { TaxonomyTable } from '@/features/settings/TaxonomyTable';
export function SettingsPage() {
  return <div className="page-container">
    <PageHeading title="A workspace that works for you." description="Give your knowledge a little structure. Keep your teams, categories, and tags in order." eyebrow="Workspace settings" />
    <Tabs defaultValue="departments">
      <TabsList className="mb-4">
        <TabsTrigger value="departments"><Building2 size={14} />Departments</TabsTrigger>
        <TabsTrigger value="categories"><Shapes size={14} />Categories</TabsTrigger>
        <TabsTrigger value="tags"><Hash size={14} />Tags</TabsTrigger>
      </TabsList>
      <TabsContent value="departments">
        <div className="mb-5">
          <h2 className="text-sm font-semibold">Organized around your people</h2>
          <p className="mt-1.5 text-[11px] text-muted-foreground">Departments connect your teammates to the resources that matter to them.</p>
        </div>
        <TaxonomyTable kind="departments" />
      </TabsContent>
      <TabsContent value="categories">
        <div className="mb-5">
          <h2 className="text-sm font-semibold">The right place for every resource</h2>
          <p className="mt-1.5 text-[11px] text-muted-foreground">Categories give your library a consistent, recognizable structure.</p>
        </div>
        <TaxonomyTable kind="categories" />
      </TabsContent>
      <TabsContent value="tags">
        <div className="mb-5">
          <h2 className="text-sm font-semibold">Little connections. Better discovery.</h2>
          <p className="mt-1.5 text-[11px] text-muted-foreground">Tags connect related documents and help your team find the next answer.</p>
        </div>
        <TaxonomyTable kind="tags" />
      </TabsContent>
    </Tabs>
    <div className="mt-5 flex items-center gap-2 text-[10px] text-muted-foreground"><ShieldCheck size={13} />Workspace settings are available to administrators only.</div>
  </div>;
}
