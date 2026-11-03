import { clearToken, getToken } from './auth.js';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

function errorText(detail) {
  if (Array.isArray(detail)) return detail.map((part) => typeof part === 'string' ? part : part.msg || JSON.stringify(part)).join(' ');
  return typeof detail === 'string' ? detail : 'The request could not be completed.';
}

export async function request(path, options = {}) {
  const token = getToken();
  if (!token) {
    window.dispatchEvent(new Event('auth-required'));
    throw new Error('Sign in to continue.');
  }
  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${token}`);
  let response;
  try { response = await fetch(`${API_BASE}${path}`, { ...options, headers }); }
  catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('The analytics service could not be reached. Check that the backend is running.');
  }
  if (response.status === 401) {
    clearToken();
    window.dispatchEvent(new Event('auth-required'));
    throw new Error('Your demo session expired. Sign in again.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(errorText(body.detail));
  }
  return response;
}
