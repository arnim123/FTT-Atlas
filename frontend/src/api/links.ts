import type { Document } from '@/types';
import { USE_MOCKS } from './client';

export function getGoogleDocumentUrl(doc: Document, history = false) {
  if (!USE_MOCKS && doc.openUrl && !history) return doc.openUrl;
  if (USE_MOCKS && doc.googleFileId?.startsWith('atlas-demo-')) return `/google-preview/${doc.id}${history ? '?history=1' : ''}`;
  const kind = doc.type === 'google-sheet' ? 'spreadsheets' : doc.type === 'google-slide' ? 'presentation' : 'document';
  return `https://docs.google.com/${kind}/d/${encodeURIComponent(doc.googleFileId ?? '')}/edit${history ? '#revisionhistory' : ''}`;
}
