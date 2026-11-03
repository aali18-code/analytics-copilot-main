# Render Free backend setup

The `render.yaml` Blueprint configures one free Python web service in Render's
Singapore region. It installs `requirements-backend.txt` (which omits
Streamlit), starts one Uvicorn worker, and checks `/api/health`. The one-worker
setting matters: chat sessions, login tokens, and KPI snapshots are kept in
that process's memory. `.python-version` selects Python 3.14, matching the
local test environment's minor version.

The Blueprint assumes `analytics-copilot-main` is the root of the Git
repository connected to Render. If you publish a parent directory instead,
move `render.yaml` to that repository root and set the service's `rootDir` to
`analytics-copilot-main`.

When creating the Blueprint, provide these environment variables in Render:

| Variable | Purpose |
| --- | --- |
| `POC_ACCESS_PASSWORD` | Shared demo password, at least 12 characters |
| `FRONTEND_ORIGINS` | Exact Vercel frontend origin, such as `https://your-site.vercel.app`; use commas for more than one |
| `LLM_MODELS` | Ordered `provider:model` list for the AI engine |
| `GEMINI_API_KEY` | Gemini key if using Gemini; add another provider's `*_API_KEY` in Render if needed |

Optional Langfuse monitoring requires `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST` in Render's environment.
Do not put passwords or API keys in Git or in Vercel's `VITE_` variables.

After Render reports the service live, open its actual `/api/health` URL to
confirm it returns `{"status":"ok"}`. Add that service origin as
`VITE_API_BASE_URL` on Vercel when configuring the frontend. The backend is not
deployed yet; the local API and its synthetic tests do not establish that the
free service has enough memory for real exports or the AI code runner.

Render Free has 512 MB RAM and sleeps after 15 minutes without requests. It
can take about a minute to wake. A sleep, restart, or redeploy clears all
uploaded data, login tokens, chat sessions, and KPI snapshots, as agreed for
this POC. Load demo files shortly before a presentation.
