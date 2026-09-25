import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export function enforceProductionApiUrl(apiUrl: string | undefined): void {
  if (!apiUrl || !apiUrl.trim()) {
    throw new Error(
      '\n[Vite Build Error] VITE_API_URL is required for production builds. Fallback to localhost is forbidden in production.'
    );
  }

  const trimmed = apiUrl.trim();
  const lower = trimmed.toLowerCase();

  if (lower.includes('localhost') || lower.includes('127.0.0.1')) {
    throw new Error(
      `\n[Vite Build Error] VITE_API_URL cannot point to localhost or 127.0.0.1 in production builds: ${trimmed}`
    );
  }

  if (!lower.startsWith('https://')) {
    throw new Error(
      `\n[Vite Build Error] VITE_API_URL must use https:// protocol in production builds: ${trimmed}`
    );
  }
}

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const isProduction = mode === 'production' || command === 'build';

  if (isProduction) {
    const env = loadEnv(mode, process.cwd(), '');
    const apiUrl = process.env.VITE_API_URL || env.VITE_API_URL;
    enforceProductionApiUrl(apiUrl);
  }

  return {
    plugins: [react()],
  };
});
