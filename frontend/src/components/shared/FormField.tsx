import { useId, type ReactNode } from 'react';
export function FormField({ label, error, children, optional, htmlFor }: {
  label: string;
  error?: string;
  optional?: boolean;
  children: ReactNode;
  htmlFor?: string;
}) {
  const id = useId(); return <div>
    <label htmlFor={htmlFor ?? id} className="field-label">{label}{optional && <span className="ml-1 font-normal text-muted-foreground">(optional)</span>}</label>
    {children}
    {error && <p className="mt-1.5 text-[11px] text-destructive" role="alert">{error}</p>}
  </div>;
}
