import React, { useState } from 'react';

import './AccessGate.css';

export function AccessGate({ checking, issue, onLogin, onRetry }) {
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    if (!password || busy) return;
    setBusy(true);
    setError('');
    try { await onLogin(password); setPassword(''); }
    catch (caught) { setError(caught.message); }
    finally { setBusy(false); }
  }

  return (
    <main className="access-page">
      <div className="access-frame">
        <div className="access-intro"><div className="access-brand"><div className="access-mark" aria-hidden="true">A<span>·</span></div><span>Analytics Copilot</span></div><div className="access-intro-content"><div className="access-kicker">INTELLIGENCE WORKSPACE</div><h1>Make sense of the numbers.</h1><p>A focused place to explore data, track performance and turn findings into clear decisions.</p></div><div className="access-intro-foot">Private proof of concept</div></div>
        <section className="access-form-panel" aria-label="Sign in"><div className="access-form-inner"><div className="access-kicker">DEMO ACCESS</div><h2>Welcome back.</h2><p>Enter the shared demo password to open the workspace.</p>{checking ? <div className="access-checking">Checking your session…</div> : <><form onSubmit={submit}><label htmlFor="demo-password">Demo password</label><input id="demo-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter password" /><button type="submit" disabled={busy || !password}>{busy ? 'Signing in…' : 'Open workspace'} <span aria-hidden="true">→</span></button></form>{(error || issue) && <p className="access-error" role="alert">{error || issue}</p>}{issue && <button className="access-retry" type="button" onClick={onRetry}>Retry connection</button>}</>}</div><div className="access-form-foot">Your uploaded data is cleared when the backend restarts.</div></section>
      </div>
    </main>
  );
}
