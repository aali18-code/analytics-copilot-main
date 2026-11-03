# Shared demo access

Set `POC_ACCESS_PASSWORD` in the backend `.env` for local use and as a secret
environment variable on Render. It must have at least 12 characters. The
backend refuses protected requests when it is unset or shorter.

The React sign-in screen posts the entered password to `POST /api/auth/login`.
The backend returns a random token valid for four hours. The browser keeps the
token only in `sessionStorage` and sends it as a Bearer token on Dashboard,
Ask AI and monitoring requests. `GET /api/auth/me` checks an existing token;
`POST /api/auth/logout` revokes it. Tokens live only in backend memory, so a
Render restart signs users out. Eight failed login attempts from the same
client address cause a 15-minute lockout.

The demo password and AI provider keys must stay on Render and must never be
placed in `VITE_` variables or committed to the repository. Set
`FRONTEND_ORIGINS` on Render to the exact Vercel site origin (and any local
origin you deliberately allow). `GET /api/health` remains public for hosting
health checks.

This is a simple shared password for the small POC, not individual user
accounts or production identity management.
