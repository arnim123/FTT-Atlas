import type { ReactNode } from 'react';
export function PageHeading({ title, description, eyebrow, children }: {
  title: string;
  description: string;
  eyebrow?: string;
  children?: ReactNode;
}) {
  return <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
    <div>
      {eyebrow && <p className="eyebrow mb-2.5">{eyebrow}</p>}
      <h1 className="page-title">{title}</h1>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground md:text-[13px]">{description}</p>
    </div>
    {children && <div className="flex items-center gap-2">{children}</div>}
  </div>;
}
