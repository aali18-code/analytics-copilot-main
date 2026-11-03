# Ask AI frontend

`AskAI.jsx` handles uploads, temporary sessions, data previews, chat, and
downloads. `api.js` calls the Python Ask AI endpoints. `PlotlyFigure.jsx`
renders interactive charts from the JSON produced by the existing Python
engine; it loads only when a chart is present. Matplotlib or Seaborn results
appear as PNG images. AI text is rendered as Markdown without raw HTML.

Start the backend from the repository root with the command in
`backend_modules/ask_ai/API.md`, then from `frontend_modules/` run:

```powershell
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173` and choose **Ask AI**. The API defaults to
`http://127.0.0.1:8000`; set `VITE_API_BASE_URL` for another host. A configured
AI model is required to ask questions. File previews work without one.

The browser stores only the random session ID in `sessionStorage`. Tables,
chat history, and result downloads live in backend memory and disappear when
the backend restarts or the session ends. After revisiting this screen, the
latest answer is restored in full; older answers show their text and can reload
their tables and charts on demand.
