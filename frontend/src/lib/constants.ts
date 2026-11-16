import type { Access, DocumentType, Role } from '@/types';

export const ROLE_LABELS: Record<Role, string> = { super_admin: 'Super Admin', admin: 'Admin', manager: 'Department Manager', employee: 'Employee', guest: 'Guest' };
export const TYPE_LABELS: Record<DocumentType, string> = { 'google-doc': 'Google Doc', 'google-sheet': 'Google Sheet', 'google-slide': 'Google Slide', pdf: 'PDF', docx: 'Word document', xlsx: 'Excel spreadsheet', ppt: 'PowerPoint', txt: 'Text document', image: 'Image' };
export const ACCESS_LABELS = { private: 'Private', department: 'Department', organization: 'Organization', custom: 'Custom access' };
export const DEFAULT_ACCESS: Access = { level: 'organization', defaultPermission: 'view', grants: [], syncStatus: 'synced' };
export const SERVICE_EMAIL = 'docs-service@company.iam.gserviceaccount.com';
export const MCP_SERVER_URL = 'https://mcp.knowledge.acme.example/mcp';
export const OPENAPI_URL = 'https://mcp.knowledge.acme.example/openapi.json';
export const API_BASE_URL = 'https://mcp.knowledge.acme.example';
export const MAX_FILE_SIZE = 25 * 1024 * 1024;
export const ACCEPTED_FILES = '.pdf,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.png,.jpg,.jpeg,.gif,.webp';
