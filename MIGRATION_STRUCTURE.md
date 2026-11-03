# Frontend and backend structure

The existing Streamlit app still starts with `streamlit run app.py`. Its UI
files remain at `app.py` and `pages/` while the React replacement is built.

| Area | New React UI | Canonical Python logic |
| --- | --- | --- |
| Dashboard | `frontend_modules/dashboard/` | `backend_modules/dashboard/` |
| Ask AI | `frontend_modules/ask_ai/` | `backend_modules/ask_ai/` |
| LLM monitoring | `frontend_modules/llm_monitoring/` | `backend_modules/llm_monitoring/` |

`frontend_modules/` is a JavaScript-only Vite project. The Dashboard screen is
connected to its API and uses Apache ECharts. Ask AI is connected to its API and
uses Plotly for interactive analysis charts. LLM monitoring is connected to
its Langfuse metrics API.

`backend_modules/dashboard/` owns source recognition, KPI definitions and
calculations, snapshot storage, dashboard AI, report planning, PowerPoint
writing, and the slide template. `backend_modules/ask_ai/` owns generic file
loading, the chat AI engine, and the disabled legacy report engine.
`backend_modules/llm_monitoring/` owns Langfuse telemetry.

All three backend API routers are mounted by `backend_modules/main.py`. Their
endpoints are documented in `backend_modules/dashboard/API.md`,
`backend_modules/ask_ai/API.md`, and `backend_modules/llm_monitoring/API.md`.
The shared password gate is in `backend_modules/auth.py`, with the React
sign-in UI and request client in `frontend_modules/shared/`; see
`backend_modules/AUTH.md`. All data API routes require this login.

Root-level Python modules with matching names contain only compatibility
imports. They preserve existing imports in `app.py`, `pages/`, and the legacy
report page. The actual implementations are under `backend_modules/`.

The selected deployment targets are Vercel Hobby for the React frontend and a
free Render web service for the in-memory Python API. The user describes this
as a personal showcase using synthetic or unrestricted data. If its purpose
changes to commercial work, revisit the Vercel plan. The Render backend
Blueprint and lean dependency file are prepared in `render.yaml` and
`requirements-backend.txt` (see `RENDER_DEPLOYMENT.md`). The Vercel static
frontend config is prepared in `frontend_modules/vercel.json` (see
`VERCEL_DEPLOYMENT.md`). Neither service has been published yet. Render's free
service may sleep and restart, clearing all in-memory sessions and snapshots.
