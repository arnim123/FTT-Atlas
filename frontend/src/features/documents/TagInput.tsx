import { useId, useState } from 'react';
import { Plus, X } from 'lucide-react';
export function TagInput({ value, onChange, suggestions }: {
  value: string[];
  onChange: (tags: string[]) => void;
  suggestions: string[];
}) {
  const [input, setInput] = useState('');
  const id = useId();
  const add = () => {
    const next = input.trim().slice(0, 40); if (next && !value.some(t => t.toLowerCase() === next.toLowerCase()))
      onChange([...value, next]); setInput('');
  };
  return <div>
    <div className="flex min-h-10 flex-wrap items-center gap-1.5 rounded-md border border-input bg-card p-2">
      {value.map(tag => <span key={tag} className="inline-flex items-center gap-1 rounded bg-accent px-2 py-1 text-[10px] text-primary">
        {tag}
        <button type="button" className="rounded hover:bg-primary/10" onClick={() => onChange(value.filter(t => t !== tag))} aria-label={`Remove tag ${tag}`}><X size={10} /></button>
      </span>)}
      <input list={id} aria-label="Add or create a tag" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ',') {
          e.preventDefault();
          add();
        }
      }} placeholder={value.length ? 'Add a tag…' : 'Choose or create tags…'} className="min-w-24 flex-1 bg-transparent px-1 py-1 text-[11px] outline-none placeholder:text-muted-foreground" />
      <datalist id={id}>{suggestions.filter(s => !value.includes(s)).map(s => <option key={s} value={s} />)}</datalist>
      {input.trim() && <button className="rounded p-1 text-primary" aria-label="Add tag" type="button" onClick={add}><Plus size={13} /></button>}
    </div>
    <p className="mt-1.5 text-[9px] text-muted-foreground">Press Enter to add a tag. New tags are created automatically.</p>
  </div>;
}
