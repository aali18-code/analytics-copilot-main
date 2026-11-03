# Shared demo sign-in

`AccessGate.jsx` is the React password screen. `auth.js` posts the entered
password to the backend and keeps only the temporary token in the current
browser tab's `sessionStorage`. `apiClient.js` adds the token to Dashboard,
Ask AI, and monitoring requests and returns to sign-in when the backend says
the token has expired.

The password itself is never put in the frontend build or browser storage.
Sign-out clears the local token and Ask AI session ID, asks the backend to
remove the Ask AI session, and revokes the token. The backend keeps tokens
only in memory; see `backend_modules/AUTH.md`.
