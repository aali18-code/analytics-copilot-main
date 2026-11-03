import React, { useEffect, useState } from 'react';

import { getMonitoring } from './api.js';
import './LLMMonitoring.css';

const WINDOWS = [
  { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' },
  { id: 'all', label: 'All time' },
];

const number = (value) => new Intl.NumberFormat().format(Number(value || 0));
const cost = (value, places = 4) => value === null || value === undefined ? '—' : `$${Number(value).toFixed(places)}`;
const latency = (value, places = 2) => value === null || value === undefined ? '—' : `${Number(value).toFixed(places)}s`;

function when(value, timezone) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const format = { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true };
  try { return new Intl.DateTimeFormat(undefined, { ...format, timeZone: timezone }).format(date); }
  catch { return new Intl.DateTimeFormat(undefined, format).format(date); }
}

function Metric({ label, value, note, tone }) {
  return <article className="monitor-metric"><div className="monitor-metric-label">{label}</div><strong className={tone || ''}>{value}</strong><p>{note}</p></article>;
}

export function LLMMonitoring() {
  const [window, setWindow] = useState('30d');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    let pending = false;
    setData(null);
    setLoading(true);
    setError('');

    async function load() {
      if (pending) return;
      pending = true;
      try {
        const result = await getMonitoring(window);
        if (active) { setData(result); setError(''); }
      } catch (caught) {
        if (active) setError(caught.message);
      } finally {
        pending = false;
        if (active) setLoading(false);
      }
    }

    load();
    const timer = setInterval(load, 15_000);
    return () => { active = false; clearInterval(timer); };
  }, [window]);

  const metrics = data?.metrics;
  const calls = data?.calls || [];

  return (
    <div className="monitor-page">
      <header className="monitor-header"><div><div className="monitor-kicker">MODEL OPERATIONS</div><h1>LLM monitoring</h1><p>Usage, cost and response time across the platform’s AI calls.</p></div><div className={data?.configured ? 'monitor-connection connected' : 'monitor-connection'}><span />{data?.configured ? 'Langfuse connected' : loading ? 'Checking connection' : 'Langfuse not connected'}</div></header>
      <div className="monitor-toolbar"><div className="monitor-window-label">TIME WINDOW</div><div className="monitor-window-picker" role="group" aria-label="Time window">{WINDOWS.map((item) => <button type="button" key={item.id} className={window === item.id ? 'active' : ''} aria-pressed={window === item.id} onClick={() => setWindow(item.id)}>{item.label}</button>)}</div><span className="monitor-refresh">Refreshes every 15 seconds</span></div>
      {error && <div className="monitor-error" role="alert">{error}</div>}
      {loading && !data && <div className="monitor-loading">Loading model activity…</div>}
      {data && !data.configured && <section className="monitor-setup"><div className="monitor-setup-icon" aria-hidden="true">◇</div><div className="monitor-kicker">MONITORING SETUP</div><h2>Connect Langfuse to see AI activity.</h2><p>Once Langfuse credentials are added to the backend settings, call counts, tokens, cost and latency will appear here. The rest of the platform works without monitoring.</p></section>}
      {data?.configured && <>
        <div className="monitor-summary"><div><span className="monitor-kicker">USAGE OVERVIEW</span><strong>{WINDOWS.find((item) => item.id === window)?.label}</strong><small>Counts include all calls in this window</small></div><div className="monitor-summary-mark" aria-hidden="true">↗</div></div>
        <div className="monitor-metrics"><Metric label="AI CALLS" value={number(metrics.calls)} note="Recorded model requests" /><Metric label="TOTAL TOKENS" value={number(metrics.total_tokens)} note="Input and output combined" /><Metric label="TOTAL COST" value={cost(metrics.total_cost_usd)} note={metrics.costed_calls < metrics.calls ? `Cost known for ${number(metrics.costed_calls)} of ${number(metrics.calls)} calls` : 'Reported provider cost'} /><Metric label="AVG LATENCY" value={latency(metrics.average_latency_seconds)} note="Calls with measured latency" /></div>
        <section className="monitor-activity"><div className="monitor-activity-heading"><div><div className="monitor-kicker">RECENT ACTIVITY</div><h2>Model calls</h2></div><span>Showing {number(data.shown_calls)} of {number(metrics.calls)} calls</span></div>
          {calls.length ? <div className="monitor-table-scroll"><table className="monitor-table"><thead><tr><th scope="col">Activity</th><th scope="col">Date & time</th><th scope="col">Model</th><th scope="col">Tokens</th><th scope="col">Cost</th><th scope="col">Latency</th><th scope="col">Status</th></tr></thead><tbody>{calls.map((call, index) => <tr key={`${call.start_time}-${call.step}-${index}`}><td><strong>{call.name}</strong><small>{call.step}</small></td><td>{when(call.start_time, data.display_timezone)}</td><td className="monitor-model">{call.model}</td><td>{number(call.total_tokens)}</td><td>{cost(call.cost_usd, 6)}</td><td>{latency(call.latency_seconds, 3)}</td><td><span className={call.status === 'error' ? 'monitor-status error' : 'monitor-status'}>{call.status === 'error' ? 'Error' : 'OK'}</span></td></tr>)}</tbody></table></div> : <div className="monitor-empty-calls"><div aria-hidden="true">◎</div><strong>No AI calls recorded in this window.</strong><p>Ask a question or generate dashboard insights, then check here again.</p></div>}
        </section>
        <p className="monitor-footnote">Times shown in {data.display_timezone || 'your local timezone'}. Monitoring records call metadata, not uploaded spreadsheets or answer text.</p>
      </>}
    </div>
  );
}
