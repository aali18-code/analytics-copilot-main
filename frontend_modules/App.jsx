import React, { useEffect, useState } from 'react';

import { Dashboard } from './dashboard/Dashboard.jsx';
import { AskAI } from './ask_ai/AskAI.jsx';
import { LLMMonitoring } from './llm_monitoring/LLMMonitoring.jsx';
import { AccessGate } from './shared/AccessGate.jsx';
import { checkExistingLogin, signIn, signOut } from './shared/auth.js';
import './App.css';

const sections = {
  dashboard: { label: 'Dashboard', number: '01', component: Dashboard },
  ask_ai: { label: 'Ask AI', number: '02', component: AskAI },
  llm_monitoring: { label: 'LLM monitoring', number: '03', component: LLMMonitoring },
};

export function App() {
  const [section, setSection] = useState('dashboard');
  const [access, setAccess] = useState('checking');
  const [accessIssue, setAccessIssue] = useState('');
  const Current = sections[section].component;

  useEffect(() => {
    let active = true;
    checkExistingLogin().then((valid) => { if (active) setAccess(valid ? 'ready' : 'locked'); })
      .catch((error) => { if (active) { setAccessIssue(error.message); setAccess('locked'); } });
    const locked = () => { setAccessIssue('Your demo session expired. Sign in again.'); setAccess('locked'); };
    window.addEventListener('auth-required', locked);
    return () => { active = false; window.removeEventListener('auth-required', locked); };
  }, []);

  async function retryAccess() {
    setAccessIssue(''); setAccess('checking');
    try { setAccess(await checkExistingLogin() ? 'ready' : 'locked'); }
    catch (error) { setAccessIssue(error.message); setAccess('locked'); }
  }

  if (access !== 'ready') return <AccessGate checking={access === 'checking'} issue={accessIssue} onRetry={retryAccess} onLogin={async (password) => { await signIn(password); setAccessIssue(''); setAccess('ready'); }} />;

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand">
          <div className="app-brand-mark" aria-hidden="true">A<span>·</span></div>
          <div><strong>Analytics Copilot</strong><span>Intelligence workspace</span></div>
        </div>
        <div className="app-sidebar-label">WORKSPACE</div>
        <nav className="app-nav" aria-label="Main navigation">
          {Object.entries(sections).map(([key, item]) => (
            <button
              key={key}
              className={section === key ? 'app-nav-item active' : 'app-nav-item'}
              type="button"
              aria-current={section === key ? 'page' : undefined}
              onClick={() => setSection(key)}
            >
              <span className="app-nav-number">{item.number}</span>
              <span>{item.label}</span>
              <span className="app-nav-arrow" aria-hidden="true">›</span>
            </button>
          ))}
        </nav>
        <div className="app-sidebar-footer"><span><span className="app-status-dot" /> Proof of concept</span><button type="button" onClick={() => { signOut(); setAccess('locked'); }}>Sign out</button></div>
      </aside>
      <main className="app-content"><Current /></main>
    </div>
  );
}
