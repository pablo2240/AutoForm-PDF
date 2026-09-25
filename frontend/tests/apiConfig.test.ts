import test from 'node:test';
import assert from 'node:assert/strict';
import {
  validateProductionApiUrl,
  validateDevApiUrl,
  resolveApiBase
} from '../src/apiConfig.ts';

test('Production build rejects missing or empty VITE_API_URL', () => {
  assert.throws(
    () => validateProductionApiUrl(undefined),
    /VITE_API_URL is required for production builds/
  );
  assert.throws(
    () => validateProductionApiUrl(''),
    /VITE_API_URL is required for production builds/
  );
  assert.throws(
    () => validateProductionApiUrl('   '),
    /VITE_API_URL is required for production builds/
  );
});

test('Production build rejects localhost and 127.0.0.1', () => {
  assert.throws(
    () => validateProductionApiUrl('http://localhost:8000'),
    /cannot point to localhost or 127\.0\.0\.1/
  );
  assert.throws(
    () => validateProductionApiUrl('https://localhost:8000'),
    /cannot point to localhost or 127\.0\.0\.1/
  );
  assert.throws(
    () => validateProductionApiUrl('http://127.0.0.1:8000'),
    /cannot point to localhost or 127\.0\.0\.1/
  );
  assert.throws(
    () => validateProductionApiUrl('https://127.0.0.1:8000'),
    /cannot point to localhost or 127\.0\.0\.1/
  );
});

test('Production build rejects non-HTTPS URLs', () => {
  assert.throws(
    () => validateProductionApiUrl('http://api.autoform.iaclatam.com'),
    /must use https:\/\/ protocol in production/
  );
});

test('Production build accepts valid HTTPS URL and strips trailing slash', () => {
  const result = validateProductionApiUrl('https://api.autoform.iaclatam.com///');
  assert.strictEqual(result, 'https://api.autoform.iaclatam.com');
});

test('Development mode permits localhost and defaults cleanly', () => {
  assert.strictEqual(validateDevApiUrl(undefined), 'http://localhost:8000');
  assert.strictEqual(validateDevApiUrl(''), 'http://localhost:8000');
  assert.strictEqual(validateDevApiUrl('http://localhost:8000/'), 'http://localhost:8000');
  assert.strictEqual(validateDevApiUrl('http://127.0.0.1:8000'), 'http://127.0.0.1:8000');
});

test('resolveApiBase respects isProd flag', () => {
  // In dev
  assert.strictEqual(resolveApiBase(undefined, false), 'http://localhost:8000');
  // In prod
  assert.strictEqual(resolveApiBase('https://api.autoform.iaclatam.com', true), 'https://api.autoform.iaclatam.com');
  assert.throws(
    () => resolveApiBase('http://localhost:8000', true),
    /cannot point to localhost or 127\.0\.0\.1/
  );
});
