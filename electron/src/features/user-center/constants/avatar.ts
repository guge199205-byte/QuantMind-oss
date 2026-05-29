export const STORAGE_DOMAIN_KEY = 'user_center_storage_domain';
export const DEFAULT_STORAGE_DOMAIN = '';

function sanitizeDomain(value: string): string {
  const v = String(value || '').trim().replace(/\/+$/, '');
  if (!v) return '';
  if (!/^https?:\/\//i.test(v)) return '';
  try {
    const u = new URL(v);
    return `${u.protocol}//${u.host}`;
  } catch {
    return '';
  }
}

export function getConfiguredStorageDomain(): string {
  let fromStorage = '';
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      fromStorage = window.localStorage.getItem(STORAGE_DOMAIN_KEY) || '';
    }
  } catch {
    fromStorage = '';
  }

  const normalizedStorage = sanitizeDomain(fromStorage);
  if (normalizedStorage) return normalizedStorage;

  const fromEnv = String(
    ((import.meta as any)?.env?.VITE_API_BASE_URL || '')
  );
  const normalizedEnv = sanitizeDomain(fromEnv);
  if (normalizedEnv) return normalizedEnv;

  return DEFAULT_STORAGE_DOMAIN;
}

export function setConfiguredStorageDomain(domain: string): string {
  const normalized = sanitizeDomain(domain) || DEFAULT_STORAGE_DOMAIN;
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(STORAGE_DOMAIN_KEY, normalized);
    }
  } catch {
    // ignore storage errors
  }
  return normalized;
}

