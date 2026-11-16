import type { Document, DocumentType, AccessLevel } from '@/types';

type Seed = [string, DocumentType, string, string, string, string, string[]];
const entries: Seed[] = [
  ['ERP Lens Inventory Manual', 'google-doc', 'erp-manual', 'product', 'u3', 'manual', ['ERP Lens', 'Inventory', 'Getting started']],
  ['Employee Handbook 2026', 'pdf', 'policies', 'hr', 'u2', 'policy', ['Onboarding', 'Internal']],
  ['Q4 Sales Playbook', 'google-slide', 'pitch', 'sales', 'u8', 'guide', ['Sales enablement', 'Q4 2026']],
  ['AI Chatbot Integration Guide', 'google-doc', 'chatbot-integration', 'engineering', 'u7', 'guide', ['AI Chatbot', 'Getting started']],
  ['Product Roadmap · Q4 2026', 'google-sheet', 'erp-features', 'product', 'u1', 'report', ['ERP Lens', 'Q4 2026']],
  ['Inventory SOP', 'docx', 'processes', 'operations', 'u9', 'sop', ['Inventory', 'Process']],
  ['Warehouse Process Guide', 'pdf', 'processes', 'operations', 'u10', 'guide', ['Inventory', 'Process']],
  ['Remote Work Policy', 'google-doc', 'policies', 'hr', 'u2', 'policy', ['Internal', 'Benefits']],
  ['Leave & Holiday Guidelines', 'pdf', 'leave', 'hr', 'u6', 'policy', ['Benefits', 'Internal']],
  ['New Hire Onboarding Checklist', 'google-sheet', 'recruitment', 'hr', 'u2', 'template', ['Onboarding', 'Getting started']],
  ['ERP Lens Quick Start', 'pdf', 'erp-manual', 'product', 'u4', 'manual', ['ERP Lens', 'Getting started']],
  ['ERP Lens Feature Overview', 'google-slide', 'erp-features', 'product', 'u3', 'guide', ['ERP Lens', 'Customer-facing']],
  ['ERP Lens Frequently Asked Questions', 'google-doc', 'erp-faq', 'product', 'u4', 'guide', ['ERP Lens', 'Customer-facing']],
  ['AI Chatbot Setup Checklist', 'google-doc', 'chatbot-setup', 'engineering', 'u7', 'guide', ['AI Chatbot', 'Getting started']],
  ['API Authentication Reference', 'pdf', 'chatbot-integration', 'engineering', 'u7', 'manual', ['AI Chatbot', 'Security']],
  ['Chatbot Troubleshooting Runbook', 'google-doc', 'chatbot-troubleshooting', 'engineering', 'u7', 'sop', ['AI Chatbot', 'Process']],
  ['Company Overview Deck', 'ppt', 'pitch', 'sales', 'u8', 'template', ['Sales enablement', 'Customer-facing']],
  ['Enterprise Pricing Matrix', 'xlsx', 'pricing', 'sales', 'u8', 'report', ['Sales enablement', 'Internal']],
  ['Customer Proposal Template', 'docx', 'proposals', 'sales', 'u8', 'template', ['Customer-facing', 'Sales enablement']],
  ['Brand & Visual Guidelines', 'pdf', 'products', 'product', 'u4', 'guide', ['Internal', 'Getting started']],
  ['Design System Overview', 'image', 'erp-features', 'product', 'u4', 'guide', ['ERP Lens', 'Internal']],
  ['Incident Response Plan', 'google-doc', 'chatbot-troubleshooting', 'engineering', 'u7', 'sop', ['Security', 'Process']],
  ['Data Security Policy', 'pdf', 'policies', 'hr', 'u2', 'policy', ['Security', 'Internal']],
  ['Recruitment Interview Kit', 'docx', 'recruitment', 'hr', 'u6', 'template', ['Onboarding', 'Internal']],
  ['Benefits at a Glance', 'google-slide', 'leave', 'hr', 'u6', 'guide', ['Benefits', 'Onboarding']],
  ['Release Notes · November', 'txt', 'erp-features', 'product', 'u3', 'report', ['ERP Lens', 'Q4 2026']],
  ['Customer Success Handoff', 'google-doc', 'proposals', 'sales', 'u8', 'sop', ['Process', 'Customer-facing']],
  ['Monthly Operations Report', 'xlsx', 'reports', 'operations', 'u9', 'report', ['Q4 2026', 'Internal']],
  ['Vendor Management Guide', 'google-doc', 'processes', 'operations', 'u10', 'guide', ['Process', 'Internal']],
  ['Expense Reimbursement Policy', 'pdf', 'policies', 'hr', 'u2', 'policy', ['Internal', 'Benefits']],
  ['ERP Lens Reporting Manual', 'google-doc', 'erp-manual', 'product', 'u3', 'manual', ['ERP Lens', 'Getting started']],
  ['ERP Lens Permissions Guide', 'google-doc', 'erp-manual', 'product', 'u4', 'manual', ['ERP Lens', 'Security']],
  ['Webhook Integration Examples', 'txt', 'chatbot-integration', 'engineering', 'u7', 'guide', ['AI Chatbot', 'Getting started']],
  ['Chatbot Architecture Diagram', 'image', 'chatbot-setup', 'engineering', 'u7', 'guide', ['AI Chatbot', 'Internal']],
  ['Sales Discovery Questions', 'google-doc', 'pitch', 'sales', 'u8', 'template', ['Sales enablement', 'Process']],
  ['Partner Enablement Deck', 'google-slide', 'pitch', 'sales', 'u8', 'guide', ['Sales enablement', 'Customer-facing']],
  ['Product Launch Checklist', 'google-sheet', 'erp-features', 'product', 'u1', 'template', ['Process', 'Q4 2026']],
  ['Stock Reconciliation Template', 'xlsx', 'processes', 'operations', 'u9', 'template', ['Inventory', 'Process']],
  ['Office Safety Guidelines', 'pdf', 'policies', 'hr', 'u6', 'policy', ['Internal', 'Onboarding']],
  ['Performance Review Template', 'docx', 'recruitment', 'hr', 'u2', 'template', ['Internal', 'Process']],
  ['Customer Feedback Summary', 'google-sheet', 'erp-faq', 'product', 'u4', 'report', ['ERP Lens', 'Q4 2026']],
  ['Deployment & Rollback Guide', 'google-doc', 'chatbot-setup', 'engineering', 'u7', 'sop', ['AI Chatbot', 'Process']],
  ['Lead Qualification Framework', 'pdf', 'pitch', 'sales', 'u8', 'guide', ['Sales enablement', 'Process']],
  ['Quarterly Planning Notes', 'google-doc', 'reports', 'operations', 'u9', 'report', ['Q4 2026', 'Internal']],
  ['Product Research Notes', 'google-doc', 'products', 'product', 'u4', 'report', ['Internal', 'ERP Lens']],
  ['Pricing Archive · 2025', 'xlsx', 'pricing', 'sales', 'u8', 'report', ['Internal']],
  ['Employee Handbook 2025', 'pdf', 'policies', 'hr', 'u2', 'policy', ['Internal', 'Onboarding']],
  ['Legacy API Migration', 'docx', 'chatbot-integration', 'engineering', 'u7', 'guide', ['AI Chatbot']],
  ['Warehouse Floor Plan', 'image', 'processes', 'operations', 'u10', 'guide', ['Inventory', 'Process']],
  ['Service Level Agreement', 'pdf', 'proposals', 'sales', 'u8', 'template', ['Customer-facing', 'Security']],
  ['Team Working Agreements', 'google-doc', 'products', 'product', 'u3', 'policy', ['Internal', 'Onboarding']],
  ['AI Chatbot Model Configuration', 'google-sheet', 'chatbot-setup', 'engineering', 'u7', 'manual', ['AI Chatbot', 'Internal']],
];

export const seedDocuments: Document[] = entries.map(([name, type, folderId, departmentId, ownerId, categoryId, tags], i) => {
  const modifiedAt = new Date(Date.UTC(2026, 10, 15 - Math.floor(i / 3), 10 - (i % 3), 30)).toISOString();
  const createdAt = new Date(Date.UTC(2026, i < 16 ? 10 : 9, i < 16 ? 1 + i % 14 : 5 + i % 20, 9)).toISOString();
  const accessLevel: AccessLevel = [16, 18, 35, 49].includes(i) ? 'custom' : [23, 39, 44].includes(i) ? 'private' : i % 7 === 3 || [17, 27].includes(i) ? 'department' : 'organization';
  const description = i === 0 ? 'Your complete guide to inventory management in ERP Lens.' : i === 5 ? 'Standard operating procedures for managing inventory across locations.' : i === 6 ? 'A practical guide to warehouse operations, stock handling, and inventory.' : `${name.replace(/ · .*/, '')} — a shared resource for the ${departmentId === 'hr' ? 'people' : departmentId} team.`;
  const content = `${name}\n\nOverview\n${description}\n\nThis document brings together the information, workflows, and best practices you need to work with confidence. It is maintained by our ${departmentId === 'hr' ? 'People & Culture' : departmentId} team and reviewed regularly.\n\nGetting started\n1. Review the prerequisites and make sure you have the right access.\n2. Follow the setup steps with your team lead.\n3. Use the checklist to verify your work before sharing it.\n\n${tags.includes('Inventory') ? 'Inventory management\nKeep stock levels accurate with regular cycle counts. Use the ERP Lens dashboard to track receipts, transfers, and warehouse stock. Reconcile inventory weekly and report discrepancies to Operations.\n\n' : ''}Best practices\nKeep your information up to date. Document decisions where your team can find them. When something changes, update the source document and let the relevant owners know.\n\nNeed a hand?\nReach out to the document owner or your department manager for help.`;
  const extension = ({ pdf: 'pdf', docx: 'docx', xlsx: 'xlsx', ppt: 'pptx', txt: 'txt', image: 'svg' } as Record<string, string>)[type];
  const size = 128000 + i * 58000;
  const version = 1 + i % 4;
  return {
    id: `doc-${i + 1}`, name, description, type, folderId, departmentId, ownerId, categoryId, tags,
    createdAt, modifiedAt, version, access: { level: accessLevel, defaultPermission: 'view', grants: accessLevel === 'custom' ? [{ principalType: 'user', principalId: 'u5', permission: 'view' }, { principalType: 'department', principalId: 'sales', permission: 'edit' }] : [], syncStatus: i === 18 ? 'failed' : i === 35 ? 'pending' : 'synced' },
    archived: [45, 46, 47].includes(i), views: [428, 386, 294, 257, 186][i] ?? Math.max(12, 180 - i * 3), size, content, starred: [0, 1, 3, 10].includes(i),
    googleFileId: type.startsWith('google') ? `atlas-demo-${i + 1}` : undefined,
    fileUrl: extension ? `/samples/document.${extension}` : undefined, fileName: extension ? `${name}.${extension}` : undefined,
    versions: type.startsWith('google') ? [] : Array.from({ length: version }, (_, j) => ({ number: version - j, createdAt: new Date(new Date(modifiedAt).getTime() - j * 86400000 * 7).toISOString(), uploadedBy: ownerId, size: size - j * 10000, note: j === version - 1 ? 'Initial upload' : 'Updated document', content, fileUrl: `/samples/document.${extension}`, fileName: `${name}.${extension}` })),
  };
});
