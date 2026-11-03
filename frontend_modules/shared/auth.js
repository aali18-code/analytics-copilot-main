const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const TOKEN_KEY = 'analytics-copilot-demo-token';

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

export async function signIn(password) {
  let response;
  try {
    response = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }),
    });
  } catch {
    throw new Error('The analytics service could not be reached. It may be waking up; try again shortly.');
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Could not sign in.');
  sessionStorage.setItem(TOKEN_KEY, body.token);
}

export async function checkExistingLogin() {
  const token = getToken();
  if (!token) return false;
  let response;
  try { response = await fetch(`${API_BASE}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } }); }
  catch { throw new Error('The analytics service could not be reached. It may be waking up; try again shortly.'); }
  if (response.status === 401) { clearToken(); return false; }
  if (!response.ok) throw new Error('Could not check your demo access. Try again shortly.');
  return true;
}

export function signOut() {
  const token = getToken();
  const askSessionId = sessionStorage.getItem('analytics-copilot-ask-ai-session');
  clearToken();
  sessionStorage.removeItem('analytics-copilot-ask-ai-session');
  if (token) {
    const headers = { Authorization: `Bearer ${token}` };
    (async () => {
      if (askSessionId) {
        try { await fetch(`${API_BASE}/api/ask-ai/sessions/${askSessionId}`, { method: 'DELETE', headers }); }
        catch { /* The backend may already have restarted. */ }
      }
      await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST', headers });
    })().catch(() => {});
  }
}
