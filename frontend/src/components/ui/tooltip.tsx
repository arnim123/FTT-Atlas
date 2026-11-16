import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import type { ReactNode } from 'react';
export const TooltipProvider = TooltipPrimitive.Provider;
export function Tooltip({ children, content }: {
  children: ReactNode;
  content: string;
}) {
  return <TooltipPrimitive.Root>
    <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content sideOffset={5} className="z-[90] max-w-64 rounded-md bg-foreground px-3 py-1.5 text-[11px] text-background shadow-popover">{content}<TooltipPrimitive.Arrow className="fill-foreground" /></TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  </TooltipPrimitive.Root>;
}
