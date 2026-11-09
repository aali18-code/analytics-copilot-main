# Dashboard API

Set `POC_ACCESS_PASSWORD` in `.env` first (see `backend_modules/AUTH.md`).
Run locally from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend_modules.main:app --host 127.0.0.1 --port 8000
```

The API is in `backend_modules/dashboard/api.py`. Its workflow matches the
existing Streamlit dashboard:

1. `POST /api/dashboard/uploads/inspect` with one Excel file as multipart field
   `file`. The response contains an `upload_id`, detected source, sheets,
   warnings, and suggested period. One file is limited to 20 MB. Up to four
   inspected uploads remain in memory for 30 minutes.
2. `POST /api/dashboard/snapshots` with JSON containing `upload_id`,
   `period_start`, `period_end`, and optional `generate_ai` (default `true`).
   A successful save consumes the upload ID and returns the calculated snapshot.
3. `GET /api/dashboard/periods` lists saved periods.
4. `GET /api/dashboard/periods/{start}/{end}` returns saved source snapshots,
   including chart data and ranked rows, plus any saved AI text.
5. `POST /api/dashboard/periods/{start}/{end}/insights` retries AI commentary.
6. `POST /api/dashboard/periods/{start}/{end}/report` downloads the dashboard-style
   PowerPoint. Its optional JSON body is `{ "chart_images": { "kpi_key": "data:image/png;base64,..." } }`.
   The React frontend sends PNGs captured from ECharts; the backend validates
   each image and uses native charts for any missing image. Cards and tables are
   editable. The existing `GET` route also downloads the new layout with native
   chart fallback for older clients.

`GET /api/health` is the service health check. The selected dates filter
ServiceNow rows; for Traackr and Sprinklr they only label the full-file values.
AI is optional: KPI save succeeds without a configured or available model.

All Dashboard routes require the shared demo login. Set `FRONTEND_ORIGINS` to a
comma-separated list of allowed browser origins when deploying; the local
Vite origins are defaults.
