import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
export function initials(name: string) { return name.split(' ').map(part => part[0]).slice(0, 2).join(''); }
export function formatDate(date: string, full = false) {
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', ...(full ? { year: 'numeric' as const } : {}) }).format(new Date(date));
}
export function formatDateTime(date: string) {
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(date));
}
export async function copyToClipboard(value: string) {
  if (!navigator.clipboard) throw new Error('Clipboard is not available in this browser.');
  await navigator.clipboard.writeText(value);
}
export function formatBytes(bytes: number) { return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`; }
export function errorMessage(error: unknown) { return error instanceof Error ? error.message : 'Something went wrong. Please try again.'; }
