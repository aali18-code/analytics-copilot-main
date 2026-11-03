# Ask AI API

The router is in `backend_modules/ask_ai/api.py` and is mounted by
`backend_modules/main.py`. Run it with the local command in
`backend_modules/dashboard/API.md`.

1. `POST /api/ask-ai/sessions`: multipart field `files` (1–4 CSV/XLSX/XLS
   files). Returns a random session ID, table summaries, cleaning errors, and
   model readiness. Each file is limited to 20 MB; combined upload to 25 MB.
2. `GET /api/ask-ai/sessions/{id}`: table summaries and lightweight chat history.
3. `GET /api/ask-ai/sessions/{id}/tables/{alias}`: first 100 rows, column
   profile, cleaning notes, and quality issues.
4. `POST /api/ask-ai/sessions/{id}/questions` with `{"question":"..."}`:
   returns the answer, result tables, interactive Plotly chart JSON, and
   fallback PNG images. Follow-up context is retained in that session.
5. `GET /api/ask-ai/sessions/{id}/answers/{answer_id}`: restore one answer.
   `.../tables.xlsx` and `.../charts/{index}.png` provide downloads.
6. `POST /api/ask-ai/sessions/{id}/clear`: clear chat on the same files.
7. `DELETE /api/ask-ai/sessions/{id}`: remove the uploaded tables and chat.

Sessions are held in one Python process: up to three sessions, idle expiry
after 90 minutes, and the last 12 answer results per session. A backend restart
clears everything. The model receives table profiles and masked sample rows;
the generated Python analysis still runs locally in the existing code runner.

All Ask AI routes require the shared demo login described in
`backend_modules/AUTH.md`.
