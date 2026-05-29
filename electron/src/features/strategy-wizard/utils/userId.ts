/**
 * 将数字型 user_id 统一补零到 8 位（如 '1' → '00000001'）。
 * 非数字类型原样返回。
 */
export function normalizeUserId(id: string | number | null | undefined): string {
  const raw = String(id ?? '').trim();
  return /^\d+$/.test(raw) ? raw.padStart(8, '0') : raw;
}

export function getWizardUserId(): string {
  const userFromStorage = (() => {
    try {
      const raw = localStorage.getItem('user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  })();

  const candidateFromUser = [
    userFromStorage?.user_id,
    userFromStorage?.id,
  ]
    .map((v: unknown) => String(v ?? '').trim())
    .find((v) => v.length > 0);

  const candidateFromToken = (() => {
    const token = localStorage.getItem('access_token') || localStorage.getItem('auth_token');
    if (!token || token.split('.').length < 2) return '';
    try {
      const payloadBase64Url = token.split('.')[1];
      const payloadBase64 = payloadBase64Url.replace(/-/g, '+').replace(/_/g, '/');
      const padded = payloadBase64 + '='.repeat((4 - (payloadBase64.length % 4)) % 4);
      const payload = JSON.parse(atob(padded));
      return String(payload?.user_id || payload?.sub || '').trim();
    } catch {
      return '';
    }
  })();

  const raw = candidateFromToken || candidateFromUser || 'dev_user_001';
  return normalizeUserId(raw);
}

