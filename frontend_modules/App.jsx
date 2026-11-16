import React, { useEffect, useRef, useState } from 'react';

import { Dashboard } from './dashboard/Dashboard.jsx';
import { generateDashboard } from './dashboard/api.js';
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
  const [sharedFiles, setSharedFiles] = useState([]);
  const [dashboardUploads, setDashboardUploads] = useState([]);
  const [generatedDashboard, setGeneratedDashboard] = useState(null);
  const [dashboardSavedIds, setDashboardSavedIds] = useState([]);
  const [dashboardGeneration, setDashboardGeneration] = useState({ status: 'idle', error: '' });
  const generationRef = useRef({ sequence: 0, key: '', status: 'idle', result: null, promise: null });
  const Current = sections[section].component;

  function clearGeneratedDashboard() {
    generationRef.current.sequence += 1;
    generationRef.current.key = '';
    generationRef.current.status = 'idle';
    generationRef.current.result = null;
    generationRef.current.promise = null;
    setGeneratedDashboard(null);
    setDashboardGeneration({ status: 'idle', error: '' });
  }

  function startDashboardGeneration(uploadIds, { force = false } = {}) {
    const ids = [...new Set(uploadIds)].filter(Boolean);
    if (!ids.length) return Promise.resolve(null);
    const key = ids.join('|');
    const current = generationRef.current;
    if (!force && current.key === key && current.status === 'running') return current.promise;
    if (!force && current.key === key && current.status === 'ready') return Promise.resolve(current.result);

    const sequence = ++current.sequence;
    current.key = key;
    current.status = 'running';
    current.result = null;
    setGeneratedDashboard(null);
    setDashboardGeneration({ status: 'running', error: '' });
    const job = generateDashboard(ids).then((result) => {
      if (generationRef.current.sequence === sequence) {
        generationRef.current.status = 'ready';
        generationRef.current.result = result;
        setGeneratedDashboard(result);
        setDashboardGeneration({ status: 'ready', error: '' });
      }
      return result;
    }).catch((error) => {
      if (generationRef.current.sequence === sequence) {
        generationRef.current.status = 'error';
        setDashboardGeneration({ status: 'error', error: error.message });
      }
      return null;
    });
    current.promise = job;
    return job;
  }

  function rememberFiles(fileList) {
    const incoming = Array.from(fileList || []).map((file) => ({
      id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
      key: `${file.name}|${file.size}|${file.lastModified}`,
      file,
    }));
    setSharedFiles((current) => {
      const known = new Set(current.map((item) => item.key));
      const fresh = [];
      incoming.forEach((item) => {
        if (!known.has(item.key)) { known.add(item.key); fresh.push(item); }
      });
      return [...current, ...fresh];
    });
  }

  function forgetFile(fileId) {
    setSharedFiles((current) => current.filter((item) => item.id !== fileId));
  }

  function resetLocalSession() {
    setSharedFiles([]);
    setDashboardUploads([]);
    clearGeneratedDashboard();
    setDashboardSavedIds([]);
    setSection('dashboard');
    sessionStorage.removeItem('analytics-copilot-ask-ai-session');
  }

  useEffect(() => {
    let active = true;
    checkExistingLogin().then((valid) => { if (active) { if (!valid) resetLocalSession(); setAccess(valid ? 'ready' : 'locked'); } })
      .catch((error) => { if (active) { setAccessIssue(error.message); setAccess('locked'); } });
    const locked = () => { setAccessIssue('Your demo session expired. Sign in again.'); setAccess('locked'); resetLocalSession(); };
    window.addEventListener('auth-required', locked);
    return () => { active = false; window.removeEventListener('auth-required', locked); };
  }, []);

  async function retryAccess() {
    setAccessIssue(''); setAccess('checking');
    try {
      const valid = await checkExistingLogin();
      if (!valid) resetLocalSession();
      setAccess(valid ? 'ready' : 'locked');
    }
    catch (error) { setAccessIssue(error.message); setAccess('locked'); }
  }

  function handleSignOut() {
    signOut();
    resetLocalSession();
    setAccessIssue('');
    setAccess('locked');
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
        <div className="app-sidebar-footer"><span><span className="app-status-dot" /> Proof of concept</span><button type="button" onClick={handleSignOut}>Sign out</button></div>
      </aside>
      <main className="app-content"><Current sharedFiles={sharedFiles} onFilesAdded={rememberFiles} onSharedFileRemove={forgetFile} dashboardUploads={dashboardUploads} setDashboardUploads={setDashboardUploads} generatedDashboard={generatedDashboard} dashboardGeneration={dashboardGeneration} startDashboardGeneration={startDashboardGeneration} clearGeneratedDashboard={clearGeneratedDashboard} dashboardSavedIds={dashboardSavedIds} setDashboardSavedIds={setDashboardSavedIds} /></main>
    </div>
  );
}
