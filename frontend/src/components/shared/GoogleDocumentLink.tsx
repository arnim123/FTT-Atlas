import { forwardRef, type AnchorHTMLAttributes } from 'react';
import { Link } from 'react-router-dom';
import type { Document } from '@/types';
import { getGoogleDocumentUrl } from '@/api';
export const GoogleDocumentLink = forwardRef<HTMLAnchorElement, AnchorHTMLAttributes<HTMLAnchorElement> & {
  document: Document;
  history?: boolean;
}>(({ document, history, ...props }, ref) => {
  const url = getGoogleDocumentUrl(document, history);
  return url.startsWith('/') ? <Link ref={ref} to={url} {...props} /> : <a ref={ref} href={url} target="_blank" rel="noreferrer" {...props} />;
});
GoogleDocumentLink.displayName = 'GoogleDocumentLink';
