import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { CopyBlock, copyValue } from './shared';
import type { ConnectorGuide } from './connectors';

export function ConnectorDrawer({ guide, mcpUrl }: { guide: ConnectorGuide; mcpUrl: string }) {
  return <DialogContent drawer className="overflow-y-auto p-6">
    <DialogHeader>
      <DialogTitle>{guide.name}</DialogTitle>
      <DialogDescription>{guide.summary}</DialogDescription>
    </DialogHeader>
    <div className="space-y-6">
      <div>
        <p className="field-label">MCP server URL</p>
        <div className="flex gap-2">
          <Input readOnly value={mcpUrl} aria-label="MCP server URL" className="font-mono" />
          <Button type="button" variant="outline" onClick={() => void copyValue(mcpUrl, 'MCP server URL copied')}>Copy</Button>
        </div>
      </div>
      <div>
        <p className="field-label">Setup</p>
        <ol className="space-y-2.5">
          {guide.steps.map((step, index) => <li key={step} className="flex items-start gap-3 text-[11px] leading-relaxed">
            <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent text-[10px] font-semibold text-primary">{index + 1}</span>
            <span>{step}</span>
          </li>)}
        </ol>
      </div>
      {guide.consentPreview && <Button asChild variant="outline" size="sm">
        <Link to={guide.consentPreview}>Preview consent screen</Link>
      </Button>}
      {guide.openApiUrl && <div>
        <p className="field-label">OpenAPI description</p>
        <div className="flex gap-2">
          <Input readOnly value={guide.openApiUrl} aria-label="OpenAPI URL" className="font-mono" />
          <Button type="button" variant="outline" onClick={() => void copyValue(guide.openApiUrl!, 'OpenAPI link copied')}>Copy</Button>
        </div>
      </div>}
      {guide.snippets.map(snippet => <div key={snippet.label}>
        <p className="field-label">{snippet.label}</p>
        <CopyBlock value={snippet.value} label={`${snippet.label} copied`} />
      </div>)}
      {guide.auth !== 'oauth' && <p className="text-[10px] leading-relaxed text-muted-foreground">Replace TOKEN with a personal access token. The full token is shown only once, when you create it.</p>}
    </div>
  </DialogContent>;
}
