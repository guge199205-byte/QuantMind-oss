function stableStringify(value: unknown): string {
  if (value === null || value === undefined) {
    return String(value);
  }

  const valueType = typeof value;
  if (valueType === 'number' || valueType === 'boolean' || valueType === 'bigint') {
    return String(value);
  }

  if (valueType === 'string') {
    return JSON.stringify(value);
  }

  if (valueType === 'function') {
    return '"[Function]"';
  }

  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`;
  }

  if (value instanceof Date) {
    return `"${value.toISOString()}"`;
  }

  if (valueType === 'object') {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const serialized = keys.map((key) => `${JSON.stringify(key)}:${stableStringify(obj[key])}`);
    return `{${serialized.join(',')}}`;
  }

  return JSON.stringify(value);
}

function hashString(input: string): string {
  let hash = 5381;
  for (let i = 0; i < input.length; i += 1) {
    hash = ((hash << 5) + hash) ^ input.charCodeAt(i);
  }
  return `${hash >>> 0}:${input.length}`;
}

export function calcFingerprint(value: unknown): string {
  return hashString(stableStringify(value));
}

export function shouldUpdateByFingerprint(prevFingerprint: string | null, nextValue: unknown): {
  changed: boolean;
  fingerprint: string;
} {
  const nextFingerprint = calcFingerprint(nextValue);
  return {
    changed: prevFingerprint !== nextFingerprint,
    fingerprint: nextFingerprint,
  };
}
