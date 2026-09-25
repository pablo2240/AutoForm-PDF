/**
 * Configuration and validation for backend API URL.
 *
 * Rules:
 * - In production builds, VITE_API_URL is strictly required.
 * - Production builds reject empty values, localhost, 127.0.0.1, and non-HTTPS protocols.
 * - Local development mode defaults to http://localhost:8000 when VITE_API_URL is omitted.
 */

export function validateProductionApiUrl(rawUrl: string | undefined): string {
  if (!rawUrl || !rawUrl.trim()) {
    throw new Error(
      'VITE_API_URL is required for production builds. Fallback to localhost is forbidden in production.'
    );
  }

  const trimmed = rawUrl.trim();
  const lower = trimmed.toLowerCase();

  if (lower.includes('localhost') || lower.includes('127.0.0.1')) {
    throw new Error(
      `VITE_API_URL cannot point to localhost or 127.0.0.1 in production: ${trimmed}`
    );
  }

  if (!lower.startsWith('https://')) {
    throw new Error(
      `VITE_API_URL must use https:// protocol in production: ${trimmed}`
    );
  }

  return trimmed.replace(/\/+$/, '');
}

export function validateDevApiUrl(rawUrl: string | undefined): string {
  if (rawUrl && rawUrl.trim()) {
    return rawUrl.trim().replace(/\/+$/, '');
  }
  return 'http://localhost:8000';
}

export function resolveApiBase(
  rawUrl: string | undefined = import.meta.env?.VITE_API_URL,
  isProd: boolean = Boolean(import.meta.env?.PROD)
): string {
  if (isProd) {
    return validateProductionApiUrl(rawUrl);
  }
  return validateDevApiUrl(rawUrl);
}
