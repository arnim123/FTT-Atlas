import type { components, paths } from './schema';

export type Schemas = components['schemas'];
export type ApiPaths = keyof paths;

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown> | null;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function apiBase() {
  return (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
}

export function absoluteApi(path: string) {
  if (!path) return path;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${apiBase()}${path.startsWith('/') ? path : `/${path}`}`;
}

type Options = Omit<RequestInit, 'body'> & { json?: unknown; form?: FormData; redirectOn401?: boolean };

export async function apiSend<T>(path: string, options: Options = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  if (method !== 'GET' && method !== 'HEAD') headers.set('X-Requested-With', 'fetch');
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(options.json);
  }
  let response: Response;
  try {
    response = await fetch(absoluteApi(path), { ...options, method, headers, body, credentials: 'include' });
  } catch {
    throw new ApiError(0, 'NETWORK', 'We couldn’t connect to the workspace. Please try again.');
  }
  if (response.status === 401 && options.redirectOn401 !== false && !path.includes('/auth/google') && !path.includes('/auth/test-login') && !window.location.pathname.startsWith('/login')) {
    window.location.assign('/login');
  }
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw errorFrom(response.status, payload);
  return payload as T;
}

export function apiGet<T>(path: string, options?: Options) {
  return apiSend<T>(path, { ...options, method: 'GET' });
}

export function apiUpload<T>(path: string, form: FormData, onProgress?: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', absoluteApi(path));
    xhr.withCredentials = true;
    xhr.setRequestHeader('X-Requested-With', 'fetch');
    xhr.upload.onprogress = event => {
      if (onProgress && event.lengthComputable) onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };
    xhr.onload = () => {
      const payload = xhr.responseText ? safeJson(xhr.responseText) : null;
      if (xhr.status === 401 && !window.location.pathname.startsWith('/login')) window.location.assign('/login');
      if (xhr.status === 204) { resolve(undefined as T); return; }
      if (xhr.status < 200 || xhr.status >= 300) { reject(errorFrom(xhr.status, payload)); return; }
      resolve(payload as T);
    };
    xhr.onerror = () => reject(new ApiError(0, 'NETWORK', 'We couldn’t connect to the workspace. Please try again.'));
    xhr.send(form);
  });
}

function safeJson(value: string) {
  try { return JSON.parse(value); } catch { return null; }
}

function errorFrom(status: number, payload: unknown) {
  const detail = payload && typeof payload === 'object' && 'detail' in payload ? (payload as { detail: unknown }).detail : null;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const body = detail as { code?: string; message?: string; details?: Record<string, unknown> };
    return new ApiError(status, body.code || 'ERROR', body.message || 'Request failed.', body.details ?? null);
  }
  if (Array.isArray(detail)) {
    const message = detail.map(item => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : '')).filter(Boolean).join(' ');
    return new ApiError(status, 'VALIDATION', message || 'Check the form and try again.');
  }
  return new ApiError(status, 'ERROR', 'Request failed.');
}
