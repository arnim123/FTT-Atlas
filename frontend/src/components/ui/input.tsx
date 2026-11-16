import * as React from 'react';
import { cn } from '@/lib/utils';
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, type, ...props }, ref) => <input type={type} className={cn('flex h-9 w-full rounded-md border border-input bg-card px-3 py-2 text-xs placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50', className)} ref={ref} {...props} />);
Input.displayName = 'Input';
export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => <textarea className={cn('flex min-h-24 w-full rounded-md border border-input bg-card px-3 py-2 text-xs leading-relaxed placeholder:text-muted-foreground disabled:opacity-50', className)} ref={ref} {...props} />);
Textarea.displayName = 'Textarea';
