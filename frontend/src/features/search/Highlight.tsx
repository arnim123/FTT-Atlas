export function Highlight({ text, query }: {
  text: string;
  query: string;
}) {
  if (!query.trim())
    return <>{text}</>; const escaped = query.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); const parts = text.split(new RegExp(`(${escaped})`, 'gi')); return <>{parts.map((part, i) => part.toLowerCase() === query.trim().toLowerCase() ? <mark key={i}>{part}</mark> : part)}</>;
}
