# LLM monitoring frontend

`LLMMonitoring.jsx` displays the read-only Langfuse metrics returned by
`api.js`. It offers last 7 days, last 30 days and all time, refreshing every
15 seconds. Totals use every call in the window; the table shows the latest
200. It handles missing Langfuse configuration, no calls and read errors.

Start the backend using the command in `backend_modules/dashboard/API.md`, then
run `npm.cmd run dev` from `frontend_modules/` and choose **LLM monitoring**.
No monitoring credentials are sent to the browser; they stay in backend
environment variables. The monitoring API uses the shared demo sign-in screen.
