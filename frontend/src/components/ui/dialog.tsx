import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;
export const DialogTitle = React.forwardRef<React.ElementRef<typeof DialogPrimitive.Title>, React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>>(({ className, ...props }, ref) => <DialogPrimitive.Title ref={ref} className={cn('text-lg font-semibold tracking-tight', className)} {...props} />);
DialogTitle.displayName = 'DialogTitle';
export const DialogDescription = React.forwardRef<React.ElementRef<typeof DialogPrimitive.Description>, React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>>(({ className, ...props }, ref) => <DialogPrimitive.Description ref={ref} className={cn('mt-1.5 text-xs leading-relaxed text-muted-foreground', className)} {...props} />);
DialogDescription.displayName = 'DialogDescription';
export function DialogContent({ children, className, drawer, ...props }: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  drawer?: boolean;
}) {
  return <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/30 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
    <DialogPrimitive.Content className={cn('fixed z-50 flex flex-col border bg-card shadow-popover duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out', drawer ? 'inset-y-0 right-0 w-full max-w-[580px] data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right' : 'left-1/2 top-1/2 max-h-[90dvh] w-[calc(100%-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg p-6 data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95', className)} {...props}>
      {children}
      <DialogPrimitive.Close className="icon-button absolute right-4 top-4" aria-label="Close dialog"><X size={16} /></DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>;
}
export function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn('mb-6 pr-7', className)} {...props} />; }
export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn('mt-6 flex justify-end gap-2', className)} {...props} />; }
