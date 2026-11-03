# LLM monitoring API

`GET /api/monitoring/calls?window=30d` returns Langfuse call metrics for the
selected window: `7d`, `30d` (default), or `all`.

The response has `configured`, `window`, `display_timezone`, `metrics`,
`shown_calls`, and `calls`. Metric totals use every call returned by Langfuse;
the table includes only the latest 200 calls. It reports call count, total
tokens, total cost in USD, average known latency in seconds, and the number of
calls with known cost. Each recent call has its activity name, timestamp,
model, token counts, cost, latency, and status. Trace and session IDs are not
returned to the browser.

When Langfuse keys are missing, the endpoint returns `configured: false` and
empty metrics. A Langfuse read failure returns HTTP 503 without exposing the
connection details. Results are cached for 15 seconds per window to avoid
repeated full-history reads from two browser users.

Run the API locally with the command in `backend_modules/dashboard/API.md`.
The endpoint requires the shared demo login described in
`backend_modules/AUTH.md`.
