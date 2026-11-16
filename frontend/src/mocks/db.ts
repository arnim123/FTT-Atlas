import { seedDocuments } from './documents';
import { seedFolders } from './folders';
import { seedAudit, seedDocumentAccess, seedGrants, seedOrgSettings, seedTokens } from './integrations';
import { seedUsers, departments, categories, tags } from './users';

export const db = {
  documents: structuredClone(seedDocuments), folders: structuredClone(seedFolders),
  users: structuredClone(seedUsers), departments: structuredClone(departments),
  categories: structuredClone(categories), tags: structuredClone(tags),
  tokens: structuredClone(seedTokens), grants: structuredClone(seedGrants),
  audit: structuredClone(seedAudit), documentAccess: structuredClone(seedDocumentAccess),
  orgSettings: structuredClone(seedOrgSettings),
};
