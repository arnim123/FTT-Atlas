import { useQuery } from '@tanstack/react-query';
import { USE_MOCKS } from './client';
import { apiGet, type Schemas } from './http';

export interface PublicConfig {
  publicBaseUrl: string;
  publicAppUrl: string;
  googleClientId: string;
  maxUploadMb: number;
  serviceAccountEmail: string;
  googleMode: string;
  demoGoogleUrl: string | null;
}

let current: PublicConfig | null = null;

export function peekPublicConfig() {
  return current;
}

export function serviceEmail() {
  return current?.serviceAccountEmail || 'atlas-drive@company.iam.gserviceaccount.com';
}

export function maxUploadBytes() {
  const megabytes = current?.maxUploadMb ?? (USE_MOCKS ? 25 : 50);
  return megabytes * 1024 * 1024;
}

export async function loadPublicConfig(): Promise<PublicConfig> {
  const row = await apiGet<Schemas['PublicConfig']>('/api/v1/config', { redirectOn401: false });
  current = {
    publicBaseUrl: row.public_base_url.replace(/\/$/, ''),
    publicAppUrl: row.public_app_url.replace(/\/$/, ''),
    googleClientId: row.google_client_id,
    maxUploadMb: row.max_upload_mb,
    serviceAccountEmail: row.service_account_email,
    googleMode: row.google_mode,
    demoGoogleUrl: row.demo_google_url ?? null,
  };
  return current;
}

export function usePublicConfig() {
  return useQuery({ queryKey: ['public-config'], queryFn: loadPublicConfig, staleTime: Infinity, enabled: !USE_MOCKS });
}
