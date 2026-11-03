import React, { lazy, Suspense, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { askQuestion, clearChat, createSession, downloadExcel, downloadPng, endSession, getAnswer, getSession, getTable } from './api.js';
import './AskAI.css';

const PlotlyFigure = lazy(() => import('./PlotlyFigure.jsx'));
const SESSION_KEY = 'analytics-copilot-ask-ai-session';
const SUGGESTIONS = [
  'Give me a short overview of this data.',
  'Which columns have missing values?',
  'What are the main patterns or trends?',
];

function displayCell(value) {
  if (value === null || value === undefined) return '—';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

function DataGrid({ columns, rows, emptyText = 'No rows to show.' }) {
  if (!rows?.length) return <p className="ask-muted">{emptyText}</p>;
  return (
    <div className="ask-table-scroll"><table className="ask-table"><thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{displayCell(row[column])}</td>)}</tr>)}</tbody></table></div>
  );
}

function AnswerDisplay({ sessionId, message, onError }) {
  const [answer, setAnswer] = useState(message.answer || null);
  const [loading, setLoading] = useState(false);
  const answerId = answer?.id || message.answer_id;
  const text = answer?.text || message.text;

  async function restore() {
    setLoading(true);
    try { setAnswer(await getAnswer(sessionId, answerId)); }
    catch (error) { onError(error.message); }
    finally { setLoading(false); }
  }

  return (
    <article className="ask-message assistant">
      <div className="ask-avatar" aria-hidden="true">A</div>
      <div className="ask-message-body">
        <div className="ask-speaker">ANALYTICS COPILOT {answer?.model && <span>· {answer.model}</span>}</div>
        <div className={answer?.ok === false || message.ok === false ? 'ask-markdown error' : 'ask-markdown'}><ReactMarkdown remarkPlugins={[remarkGfm]}>{text || ''}</ReactMarkdown></div>
        {answer && <>
          {(answer.tables || []).map((table, index) => <section className="ask-result-block" key={`${answer.id}-table-${index}`}><div className="ask-result-heading"><strong>{table.title}</strong><span>{table.total_rows?.toLocaleString()} rows</span></div><DataGrid columns={table.columns || []} rows={table.rows || []} />{table.truncated && <p className="ask-muted">Showing the first {table.rows.length.toLocaleString()} of {table.total_rows.toLocaleString()} rows.</p>}</section>)}
          {(answer.plotly_figures || []).map((figure, index) => <section className="ask-chart-card" key={`${answer.id}-plotly-${index}`}><Suspense fallback={<div className="ask-chart-loading">Loading interactive chart…</div>}><PlotlyFigure figure={figure} /></Suspense></section>)}
          {(answer.png_figures || []).map((source, index) => <section className="ask-chart-card" key={`${answer.id}-png-${index}`}><img src={source} alt={`Analysis chart ${index + 1}`} /><button className="ask-link-button" type="button" onClick={() => downloadPng(sessionId, answer.id, index).catch((error) => onError(error.message))}>Download chart PNG</button></section>)}
          {answer.has_excel_download && <button className="ask-download-button" type="button" onClick={() => downloadExcel(sessionId, answer.id).catch((error) => onError(error.message))}>↓ Download result tables · Excel</button>}
        </>}
        {!answer && answerId && <button className="ask-link-button" type="button" disabled={loading} onClick={restore}>{loading ? 'Loading…' : 'Load result tables and charts'}</button>}
      </div>
    </article>
  );
}

function DataPanel({ session, table, tableLoading, tableError, selectedAlias, onSelect }) {
  const [view, setView] = useState('preview');
  const totalRows = (session.tables || []).reduce((sum, item) => sum + Number(item.Rows || 0), 0);
  return (
    <aside className="ask-data-panel" aria-label="Your uploaded data">
      <div className="ask-data-heading"><div className="ask-kicker">DATA WORKSPACE</div><h2>Your data</h2><p>{session.tables.length} table{session.tables.length === 1 ? '' : 's'} · {totalRows.toLocaleString()} rows</p></div>
      <div className="ask-data-list">{session.tables.map((item) => <button key={item.Variable} type="button" className={selectedAlias === item.Variable ? 'ask-data-source selected' : 'ask-data-source'} onClick={() => { onSelect(item.Variable); setView('preview'); }}><span className="ask-file-icon" aria-hidden="true">▦</span><span><strong>{item.File}</strong><small>{item.Sheet !== '-' ? `${item.Sheet} · ` : ''}{Number(item.Rows).toLocaleString()} rows</small></span></button>)}</div>
      <div className="ask-data-detail">
        <div className="ask-mini-tabs" role="tablist" aria-label="Table details"><button className={view === 'preview' ? 'active' : ''} type="button" onClick={() => setView('preview')}>Preview</button><button className={view === 'columns' ? 'active' : ''} type="button" onClick={() => setView('columns')}>Columns</button><button className={view === 'quality' ? 'active' : ''} type="button" onClick={() => setView('quality')}>Quality</button></div>
        {tableLoading && <p className="ask-muted">Loading table profile…</p>}
        {tableError && <p className="ask-inline-error">{tableError}</p>}
        {table && !tableLoading && <>
          {view === 'preview' && <><DataGrid columns={Object.keys(table.rows?.[0] || {})} rows={table.rows || []} />{table.total_rows > (table.rows?.length || 0) && <p className="ask-muted">First {table.rows.length} of {table.total_rows.toLocaleString()} rows.</p>}</>}
          {view === 'columns' && <DataGrid columns={['Column', 'Type', 'Missing %', 'Unique', 'Detail']} rows={table.columns || []} />}
          {view === 'quality' && <div className="ask-quality">{[...(table.cleaning_notes || []), ...(table.quality_issues || [])].length ? <ul>{[...(table.cleaning_notes || []), ...(table.quality_issues || [])].map((note, index) => <li key={index}>{note}</li>)}</ul> : <p className="ask-muted">No cleaning or quality issues found.</p>}</div>}
        </>}
      </div>
      {(session.shared_columns || []).length > 0 && <p className="ask-joins">{session.shared_columns.length} possible link{session.shared_columns.length === 1 ? '' : 's'} between tables detected.</p>}
    </aside>
  );
}

export function AskAI() {
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [selectedAlias, setSelectedAlias] = useState('');
  const [table, setTable] = useState(null);
  const [tableLoading, setTableLoading] = useState(false);
  const [tableError, setTableError] = useState('');
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState('');
  const [restoring, setRestoring] = useState(true);
  const [notice, setNotice] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    const savedId = sessionStorage.getItem(SESSION_KEY);
    if (!savedId) { setRestoring(false); return; }
    let active = true;
    getSession(savedId).then(async (restored) => {
      if (!active) return;
      const history = restored.messages || [];
      const lastAnswer = [...history].reverse().find((item) => item.role === 'assistant' && item.answer_id);
      if (lastAnswer) {
        try {
          const full = await getAnswer(savedId, lastAnswer.answer_id);
          if (!active) return;
          setMessages(history.map((item) => item === lastAnswer ? { ...item, answer: full } : item));
        } catch { setMessages(history); }
      } else setMessages(history);
      setSession(restored);
      setSelectedAlias(restored.tables?.[0]?.Variable || '');
    }).catch((error) => {
      if (!active) return;
      sessionStorage.removeItem(SESSION_KEY);
      setNotice({ type: 'info', text: error.message });
    }).finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!session?.session_id || !selectedAlias) { setTable(null); return undefined; }
    let active = true;
    setTable(null); setTableError(''); setTableLoading(true);
    getTable(session.session_id, selectedAlias).then((result) => { if (active) setTable(result); }).catch((error) => { if (active) setTableError(error.message); }).finally(() => { if (active) setTableLoading(false); });
    return () => { active = false; };
  }, [session?.session_id, selectedAlias]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages.length, busy]);

  async function upload(files) {
    if (!files?.length) return;
    if (files.length > 4) { setNotice({ type: 'error', text: 'Choose up to four files for one session.' }); return; }
    setBusy('upload'); setNotice(null);
    try {
      const created = await createSession(files);
      if (session?.session_id) endSession(session.session_id).catch(() => {});
      sessionStorage.setItem(SESSION_KEY, created.session_id);
      setSession(created); setMessages([]); setSelectedAlias(created.tables?.[0]?.Variable || ''); setQuestion('');
      if (created.load_errors?.length) setNotice({ type: 'info', text: `${created.load_errors.length} file or sheet issue(s) were skipped; the usable tables are loaded.` });
    } catch (error) { setNotice({ type: 'error', text: error.message }); }
    finally { setBusy(''); }
  }

  async function submit(value = question) {
    const prompt = value.trim();
    if (!prompt || !session?.session_id || busy) return;
    setQuestion(''); setBusy('ask'); setNotice(null);
    setMessages((current) => [...current, { role: 'user', text: prompt }]);
    try {
      const answer = await askQuestion(session.session_id, prompt);
      setMessages((current) => [...current, { role: 'assistant', answer }]);
    } catch (error) {
      setMessages((current) => [...current, { role: 'assistant', text: error.message, ok: false }]);
    } finally { setBusy(''); }
  }

  async function handleClear() {
    if (!session) return;
    setBusy('clear');
    try { await clearChat(session.session_id); setMessages([]); setNotice({ type: 'success', text: 'Chat cleared. Your uploaded tables are still available.' }); }
    catch (error) { setNotice({ type: 'error', text: error.message }); }
    finally { setBusy(''); }
  }

  async function handleEnd() {
    if (!session) return;
    setBusy('end');
    try { await endSession(session.session_id); setNotice({ type: 'success', text: 'Session ended and uploaded data cleared.' }); }
    catch (error) { setNotice({ type: 'info', text: `Local session cleared. Server confirmation was unavailable: ${error.message}` }); }
    sessionStorage.removeItem(SESSION_KEY);
    setSession(null); setMessages([]); setTable(null); setSelectedAlias(''); setQuestion(''); setBusy('');
  }

  const totalRows = (session?.tables || []).reduce((sum, item) => sum + Number(item.Rows || 0), 0);

  return (
    <div className="ask-page">
      <header className="ask-header"><div><div className="ask-kicker">CONVERSATIONAL ANALYTICS</div><h1>Ask your data</h1><p>Explore spreadsheets in plain English. See the numbers, tables and charts behind each answer.</p></div>{session && <div className="ask-header-actions"><label className={`ask-button secondary ask-replace-button${busy ? ' disabled' : ''}`}>Replace files<input type="file" accept=".csv,.xlsx,.xls" multiple disabled={Boolean(busy)} onChange={(event) => { upload(event.target.files); event.target.value = ''; }} /></label><button className="ask-button secondary" type="button" disabled={Boolean(busy) || !messages.length} onClick={handleClear}>Clear chat</button><button className="ask-button secondary" type="button" disabled={Boolean(busy)} onClick={handleEnd}>End session</button></div>}</header>
      {notice && <div className={`ask-notice ${notice.type}`} role="status"><span>{notice.text}</span><button type="button" aria-label="Dismiss message" onClick={() => setNotice(null)}>×</button></div>}
      {restoring ? <div className="ask-restoring">Restoring your session…</div> : !session ? (
        <section className="ask-empty"><div className="ask-empty-top"><div className="ask-empty-icon" aria-hidden="true">▦</div><div className="ask-kicker">START AN ANALYSIS SESSION</div><h2>Bring your data into focus.</h2><p>Upload CSV or Excel files. We’ll clean and profile each table, then you can ask questions across all of them.</p><label className="ask-upload-button">{busy === 'upload' ? 'Preparing files…' : 'Choose files to analyse'}<input type="file" accept=".csv,.xlsx,.xls" multiple disabled={Boolean(busy)} onChange={(event) => { upload(event.target.files); event.target.value = ''; }} /></label><small>Up to four files · 20 MB per file · 25 MB combined</small></div><div className="ask-empty-foot"><div><strong>01</strong><span>Upload files</span></div><div><strong>02</strong><span>Review profiles</span></div><div><strong>03</strong><span>Ask questions</span></div></div></section>
      ) : <>
        <div className="ask-session-strip"><div><span className="ask-session-mark">●</span><strong>Session active</strong><span>{session.tables.length} tables</span><span>{totalRows.toLocaleString()} rows</span></div><span className={session.ai_ready ? 'ask-ai-state ready' : 'ask-ai-state'}>{session.ai_ready ? 'Model configured' : 'AI setup needed'}</span></div>
        {!session.ai_ready && <div className="ask-setup-note">Your files are ready to preview. Add an AI provider key and model in the backend settings to ask questions.</div>}
        <div className="ask-workspace">
          <DataPanel session={session} table={table} tableLoading={tableLoading} tableError={tableError} selectedAlias={selectedAlias} onSelect={setSelectedAlias} />
          <section className="ask-chat" aria-label="Ask AI conversation">
            <div className="ask-chat-heading"><div><div className="ask-kicker">ANALYSIS CONVERSATION</div><h2>Explore your data</h2></div><span>{messages.length ? `${Math.ceil(messages.length / 2)} question${messages.length > 2 ? 's' : ''}` : 'Ready when you are'}</span></div>
            <div className="ask-chat-scroll">
              {!messages.length && <div className="ask-starters"><div className="ask-starters-icon" aria-hidden="true">✦</div><h3>What would you like to know?</h3><p>Try a starting question or ask about a specific file, column or time period.</p><div>{SUGGESTIONS.map((suggestion) => <button type="button" key={suggestion} disabled={!session.ai_ready || Boolean(busy)} onClick={() => submit(suggestion)}>{suggestion}<span aria-hidden="true">↗</span></button>)}</div></div>}
              {messages.map((message, index) => message.role === 'user' ? <article className="ask-message user" key={index}><div className="ask-message-body"><div className="ask-speaker">YOU</div><p>{message.text}</p></div></article> : <AnswerDisplay key={message.answer?.id || message.answer_id || index} sessionId={session.session_id} message={message} onError={(text) => setNotice({ type: 'error', text })} />)}
              {busy === 'ask' && <div className="ask-thinking"><span className="ask-thinking-dot" /> Analysing your data…</div>}
              <div ref={bottomRef} />
            </div>
            <form className="ask-composer" onSubmit={(event) => { event.preventDefault(); submit(); }}><label htmlFor="ask-question">ASK A QUESTION</label><textarea id="ask-question" value={question} maxLength={3000} rows={2} disabled={!session.ai_ready || Boolean(busy)} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder={session.ai_ready ? 'Ask about trends, totals, outliers or relationships across files…' : 'Configure an AI model to enable questions'} /><div className="ask-composer-foot"><span>Enter to send · Shift + Enter for a new line</span><button className="ask-button primary" type="submit" disabled={!session.ai_ready || !question.trim() || Boolean(busy)}>Send question <span aria-hidden="true">↗</span></button></div></form>
          </section>
        </div>
      </>}
    </div>
  );
}
