import { FileText, FileSpreadsheet, Presentation, Image, File } from 'lucide-react';
import type { DocumentType } from '@/types';
import { cn } from '@/lib/utils';
import { TYPE_LABELS } from '@/lib/constants';
export function DocumentIcon({ type, small, className }: {
  type: DocumentType;
  small?: boolean;
  className?: string;
}) {
  const sheet = ['google-sheet', 'xlsx'].includes(type), slide = ['google-slide', 'ppt'].includes(type);
  const Icon = sheet ? FileSpreadsheet : slide ? Presentation : type === 'image' ? Image : type === 'txt' ? File : FileText;
  return <span title={TYPE_LABELS[type]} className={cn('relative inline-flex shrink-0 items-center justify-center rounded-md', small ? 'h-8 w-7' : 'h-10 w-9', type === 'pdf' ? 'bg-[#fcf0ed] text-[#be776c] dark:bg-[#3d2926] dark:text-[#dc9c91]' : sheet ? 'bg-[#ebf3eb] text-[#63906c] dark:bg-[#25372b] dark:text-[#91ba97]' : slide ? 'bg-[#faf3e0] text-[#b89a4f] dark:bg-[#39331d] dark:text-[#ccb477]' : type === 'image' ? 'bg-[#f0eaf7] text-[#9a7bad] dark:bg-[#32263e] dark:text-[#baa3cd]' : 'bg-[#eaf1fa] text-[#608abc] dark:bg-[#243040] dark:text-[#90aed1]', className)}><Icon size={small ? 18 : 21} strokeWidth={1.5} />{type === 'pdf' && <span className="absolute bottom-1 bg-inherit px-0.5 text-[5px] font-bold leading-none">PDF</span>}</span>;
}
