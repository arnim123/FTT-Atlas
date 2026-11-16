import type { Folder } from '@/types';
import { DEFAULT_ACCESS } from '@/lib/constants';

const entries: [string, string, string | null, string][] = [
  ['root', 'Company Knowledge', null, 'product'],
  ['hr', 'HR', 'root', 'hr'], ['policies', 'Policies', 'hr', 'hr'], ['leave', 'Leave Rules', 'hr', 'hr'], ['recruitment', 'Recruitment', 'hr', 'hr'],
  ['products', 'Products', 'root', 'product'], ['erp', 'ERP Lens', 'products', 'product'],
  ['erp-manual', 'User Manual', 'erp', 'product'], ['erp-features', 'Features', 'erp', 'product'], ['erp-faq', 'FAQs', 'erp', 'product'],
  ['chatbot', 'AI Chatbot', 'products', 'engineering'], ['chatbot-setup', 'Setup Guide', 'chatbot', 'engineering'], ['chatbot-integration', 'Integration Docs', 'chatbot', 'engineering'], ['chatbot-troubleshooting', 'Troubleshooting', 'chatbot', 'engineering'],
  ['sales', 'Sales', 'root', 'sales'], ['pitch', 'Pitch Decks', 'sales', 'sales'], ['pricing', 'Pricing', 'sales', 'sales'], ['proposals', 'Proposals', 'sales', 'sales'],
  ['operations', 'Operations', 'root', 'operations'], ['processes', 'Processes', 'operations', 'operations'], ['reports', 'Reports', 'operations', 'operations'],
];
export const seedFolders: Folder[] = entries.map(([id, name, parentId, departmentId]) => ({
  id, name, parentId, departmentId, ownerId: departmentId === 'product' ? 'u3' : departmentId === 'hr' ? 'u2' : departmentId === 'engineering' ? 'u7' : departmentId === 'sales' ? 'u8' : 'u9',
  access: { ...DEFAULT_ACCESS, defaultPermission: 'edit', level: ['recruitment', 'pricing', 'reports'].includes(id) ? 'department' : 'organization', grants: [] }, archived: false,
}));
