# Dashboard frontend

`Dashboard.jsx` renders the management dashboard. `KpiChart.jsx` renders the
saved breakdown values with Apache ECharts. `api.js` calls the Dashboard API.
The browser displays only calculated snapshots; the Python backend remains the
source of KPI values and PowerPoint content. On report download, the browser
captures each ECharts chart as a PNG and sends those images to the backend so
the deck uses the dashboard's chart appearance. If capture fails, that chart
uses a native PowerPoint fallback and the UI reports the count.

To run locally, start the API from the repository root using the command in
`backend_modules/dashboard/API.md`, then run from `frontend_modules/`:

```powershell
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The default API address is
`http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` to the Render API origin when
deploying the frontend to Vercel. The Render backend must also allow the
frontend origin through `FRONTEND_ORIGINS`.

Current UI flow: inspect up to four exports, confirm each period, calculate and
save, select a saved period and source, read KPI cards/charts/tables and AI
commentary, retry AI, or download a PowerPoint. Missing AI text leaves the KPI
visible. No sample numbers are displayed when a source has not been loaded.
