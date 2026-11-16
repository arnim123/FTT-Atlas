import type { Taxonomy, User } from '@/types';

export const seedUsers: User[] = [
  { id: 'u1', name: 'Alex Morgan', email: 'alex.morgan@company.com', role: 'super_admin', departmentId: 'product', status: 'active', color: 'sage', lastActive: '2026-11-15T09:00:00Z' },
  { id: 'u2', name: 'Sarah Chen', email: 'sarah.chen@company.com', role: 'admin', departmentId: 'hr', status: 'active', color: 'rose', lastActive: '2026-11-15T08:45:00Z' },
  { id: 'u3', name: 'James Wilson', email: 'james.wilson@company.com', role: 'manager', departmentId: 'product', status: 'active', color: 'sand', lastActive: '2026-11-15T08:30:00Z' },
  { id: 'u4', name: 'Emma Davis', email: 'emma.davis@company.com', role: 'employee', departmentId: 'product', status: 'active', color: 'lavender', lastActive: '2026-11-15T08:15:00Z' },
  { id: 'u5', name: 'Noah Williams', email: 'noah@partner.co', role: 'guest', departmentId: 'sales', status: 'active', color: 'blue', lastActive: '2026-11-14T13:10:00Z' },
  { id: 'u6', name: 'Olivia Martinez', email: 'olivia.m@company.com', role: 'employee', departmentId: 'hr', status: 'active', color: 'sand', lastActive: '2026-11-15T07:45:00Z' },
  { id: 'u7', name: 'Liam Patel', email: 'liam.patel@company.com', role: 'manager', departmentId: 'engineering', status: 'active', color: 'sage', lastActive: '2026-11-14T16:45:00Z' },
  { id: 'u8', name: 'Sophie Turner', email: 'sophie.turner@company.com', role: 'employee', departmentId: 'sales', status: 'active', color: 'rose', lastActive: '2026-11-14T15:00:00Z' },
  { id: 'u9', name: 'Daniel Kim', email: 'daniel.kim@company.com', role: 'manager', departmentId: 'operations', status: 'active', color: 'blue', lastActive: '2026-11-15T08:50:00Z' },
  { id: 'u10', name: 'Isabella Brown', email: 'isabella.b@company.com', role: 'employee', departmentId: 'operations', status: 'active', color: 'lavender', lastActive: '2026-11-13T12:00:00Z' },
  { id: 'u11', name: 'Ethan Taylor', email: 'ethan.taylor@company.com', role: 'employee', departmentId: 'engineering', status: 'invited', color: 'sand', lastActive: '2026-11-10T11:00:00Z' },
  { id: 'u12', name: 'Mia Robinson', email: 'mia.robinson@company.com', role: 'employee', departmentId: 'hr', status: 'deactivated', color: 'rose', lastActive: '2026-10-08T10:30:00Z' },
  { id: 'u13', name: 'Atlas Indexer', email: 'atlas.indexer@company.com', role: 'employee', departmentId: 'engineering', status: 'active', color: 'blue', lastActive: '2026-11-15T11:20:00Z', accountType: 'bot' },
];
export const departments: Taxonomy[] = [
  { id: 'product', name: 'Product', description: 'Product strategy, design, and documentation', color: '#246b5a' },
  { id: 'engineering', name: 'Engineering', description: 'Technical guides, architecture, and integrations', color: '#4a8b78' },
  { id: 'hr', name: 'People & Culture', description: 'People, policies, and everything in between', color: '#81b09c' },
  { id: 'sales', name: 'Sales', description: 'Resources to build better customer relationships', color: '#adcebb' },
  { id: 'operations', name: 'Operations', description: 'Processes that keep the company moving', color: '#d4e4d6' },
];
export const categories: Taxonomy[] = [
  { id: 'manual', name: 'User manuals', description: 'Step-by-step product documentation' },
  { id: 'policy', name: 'Policies', description: 'Company guidelines and policies' },
  { id: 'guide', name: 'Guides & tutorials', description: 'Practical instructions and learning resources' },
  { id: 'sop', name: 'Standard procedures', description: 'Repeatable operational processes' },
  { id: 'template', name: 'Templates', description: 'Ready-to-use starting points' },
  { id: 'report', name: 'Reports', description: 'Insights, metrics, and analysis' },
];
export const tags: Taxonomy[] = ['Getting started', 'ERP Lens', 'Inventory', 'Internal', 'Onboarding', 'AI Chatbot', 'Process', 'Q4 2026', 'Customer-facing', 'Security', 'Sales enablement', 'Benefits'].map((name, i) => ({ id: `tag-${i + 1}`, name, description: `Documents related to ${name.toLowerCase()}` }));
