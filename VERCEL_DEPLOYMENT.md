# Vercel Hobby frontend setup

The React frontend is a static Vite build. `frontend_modules/vercel.json`
specifies the Vite framework, `npm ci`, `npm run build`, and `dist` output.
`frontend_modules/package.json` requests Node 24, matching the local build.

The config assumes `analytics-copilot-main` is the Git repository root. In
Vercel, import that repository and set **Root Directory** to
`frontend_modules`. If `frontend_modules` is itself the repository root, leave
Root Directory at its default. Vercel should not build the Python backend.

Set this environment variable in the Vercel project before building:

| Variable | Value |
| --- | --- |
| `VITE_API_BASE_URL` | The Render backend's HTTPS origin, for example `https://your-api.onrender.com` (no trailing `/api`) |

This value is public in the browser build. Never put `POC_ACCESS_PASSWORD`,
AI provider keys, or Langfuse secrets in Vercel or any `VITE_` variable. The
user types the demo password into the React sign-in screen; the backend checks
it and returns a temporary token.

After Vercel provides the site's actual URL, set `FRONTEND_ORIGINS` in Render
to that exact origin, for example `https://your-site.vercel.app`. Add a preview
deployment origin only if you intend to test it. Render must restart after its
environment change, clearing in-memory data. Then test sign-in, a synthetic
upload, a dashboard report download, and Ask AI with a configured model.

The frontend has not been published yet. Local Vite builds check the source
and build output; they do not verify Vercel deployment, cross-site requests,
or live AI behavior.
