import * as React from 'react';
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { cn } from '@/lib/utils';
export const DropdownMenu = DropdownMenuPrimitive.Root;
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;
export function DropdownMenuContent({ className, sideOffset = 6, ...props }: React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>) { return <DropdownMenuPrimitive.Portal><DropdownMenuPrimitive.Content sideOffset={sideOffset} className={cn('z-[80] min-w-48 rounded-lg border bg-popover p-1.5 text-popover-foreground shadow-popover data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95', className)} {...props} /></DropdownMenuPrimitive.Portal>; }
export function DropdownMenuItem({ className, ...props }: React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item>) { return <DropdownMenuPrimitive.Item className={cn('relative flex cursor-pointer select-none items-center gap-2.5 rounded-md px-2.5 py-2 text-xs outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-40 [&_svg]:size-3.5', className)} {...props} />; }
export function DropdownMenuSeparator() { return <DropdownMenuPrimitive.Separator className="-mx-1 my-1 h-px bg-border" />; }
export function DropdownMenuLabel({ children }: {
  children: React.ReactNode;
}) { return <DropdownMenuPrimitive.Label className="px-2.5 py-2 text-[10px] font-medium text-muted-foreground">{children}</DropdownMenuPrimitive.Label>; }
