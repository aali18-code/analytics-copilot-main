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

Current UI flow: Dashboard opens on the prefilled Executive dashboard. Inspect
up to four exports, confirm dates, calculate fixed KPIs, read AI commentary,
and download the PowerPoint as before. After the Prefilled save and commentary
attempt finish, the AI Generated Dashboard starts in the background from the
same inspected uploads. Click **AI Generated Dashboard** to open the separate
view when it is ready; the view shows progress and offers a retry if needed.
AI chooses 2-3 metrics per source, calculates them from the complete local
tables, and shows grounded insights. AI generation has no date filter. Missing
AI text leaves calculated values visible.
