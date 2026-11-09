import React, { useEffect, useState } from 'react';

import { KpiChart } from './KpiChart.jsx';
import { downloadReport, generateInsights, getPeriod, inspectFile, listPeriods, saveSnapshot } from './api.js';
import { SharedFilePicker } from '../shared/SharedFilePicker.jsx';
import './Dashboard.css';
import './DashboardLoading.css';

const SOURCE_ORDER = ['ServiceNow', 'Traackr', 'Sprinklr'];
const SOURCE_DESCRIPTIONS = {
  ServiceNow: 'Service requests and operational delivery',
  Traackr: 'Influencer campaigns and brand performance',
  Sprinklr: 'Paid and organic social performance',
};

const periodKey = (item) => `${item.period_start}|${item.period_end}`;
const splitPeriod = (key) => key?.split('|') || [];
const dateLabel = (value) => value ? new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
const formatValue = (value, unit) => {
  if (value === null || value === undefined) return 'n/a';
  if (typeof value !== 'number') return String(value);
  const digits = unit === 'count' ? 0 : 2;
  const formatted = new Intl.NumberFormat(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
  return unit === '%' ? `${formatted}%` : unit === 'hours' ? `${formatted} hrs` : formatted;
};

function Insight({ id, ai }) {
  const entry = ai?.entries?.[id];
  if (!entry) return null;
  return (
    <div className="dashboard-insight">
      <div className="dashboard-insight-label">AI INSIGHT</div>
      <p>{entry.insight}</p>
      <div className="dashboard-insight-label">RECOMMENDED ACTION</div>
      <p>{entry.recommendation}</p>
    </div>
  );
}

function MetricCard({ kpi, ai }) {
  return (
    <article className="dashboard-metric">
      <div className="dashboard-metric-top"><span className="dashboard-id">{kpi.dashboard_id}</span><span className="dashboard-metric-line" /></div>
      <div className="dashboard-metric-value">{formatValue(kpi.value, kpi.unit)}</div>
      <h3>{kpi.name}</h3>
      <Insight id={kpi.dashboard_id} ai={ai} />
    </article>
  );
}

function BreakdownCard({ kpi, chart, ai }) {
  if (!chart) return null;
  return (
    <article className="dashboard-panel dashboard-breakdown">
      <div className="dashboard-panel-heading"><div><span className="dashboard-id">{kpi.dashboard_id}</span><h3>{kpi.name}</h3></div><span className="dashboard-panel-unit">{kpi.unit === 'count' ? 'TASKS' : kpi.unit.toUpperCase()}</span></div>
      <KpiChart chart={chart} unit={kpi.unit} title={kpi.name} />
      <Insight id={kpi.dashboard_id} ai={ai} />
    </article>
  );
}

function RankedTable({ kpi, ai }) {
  const columns = kpi.columns || [];
  const rows = Array.isArray(kpi.value) ? kpi.value : [];
  return (
    <article className="dashboard-panel dashboard-table-panel">
      <div className="dashboard-panel-heading"><div><span className="dashboard-id">{kpi.dashboard_id}</span><h3>{kpi.name}</h3></div>{kpi.rank_by && <span className="dashboard-panel-unit">RANKED BY {kpi.rank_by.toUpperCase()}</span>}</div>
      <div className="dashboard-table-scroll">
        <table className="dashboard-table">
          <thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
          <tbody>{rows.map((row, index) => <tr key={`${kpi.dashboard_id}-${index}`}>{columns.map((column) => <td key={column}>{row[column] ?? '—'}</td>)}</tr>)}</tbody>
        </table>
      </div>
      <Insight id={kpi.dashboard_id} ai={ai} />
    </article>
  );
}

function SourceView({ source, snapshot, ai }) {
  if (!snapshot) return <div className="dashboard-empty-source"><h2>{source} is not available for this period</h2><p>Upload a matching export and save it with the same reporting dates.</p></div>;
  const items = Object.values(snapshot.kpis || {});
  const metrics = items.filter((kpi) => kpi.kind !== 'breakdown' && kpi.kind !== 'table');
  const breakdowns = items.filter((kpi) => kpi.kind === 'breakdown');
  const tables = items.filter((kpi) => kpi.kind === 'table');
  const chartByKey = Object.fromEntries((snapshot.charts || []).map((chart) => [chart.kpi_key, chart]));
  const entries = Object.entries(snapshot.kpis || {});
  return (
    <section aria-label={`${source} results`}>
      <div className="dashboard-source-heading"><div><div className="dashboard-kicker">SOURCE ANALYSIS</div><h2>{source}</h2><p>{SOURCE_DESCRIPTIONS[source]}</p></div><div className="dashboard-source-file">Source: {(snapshot.source_files || []).join(', ') || 'Uploaded export'}</div></div>
      {metrics.length > 0 && <><div className="dashboard-section-label">KEY MEASURES</div><div className="dashboard-metrics">{metrics.map((kpi) => <MetricCard key={kpi.dashboard_id || kpi.name} kpi={kpi} ai={ai} />)}</div></>}
      {breakdowns.length > 0 && <><div className="dashboard-section-label">PERFORMANCE BREAKDOWN</div><div className="dashboard-charts">{entries.filter(([, kpi]) => kpi.kind === 'breakdown').map(([key, kpi]) => <BreakdownCard key={key} kpi={kpi} chart={chartByKey[key]} ai={ai} />)}</div></>}
      {tables.length > 0 && <><div className="dashboard-section-label">RANKED RESULTS</div><div className="dashboard-tables">{tables.map((kpi) => <RankedTable key={kpi.dashboard_id || kpi.name} kpi={kpi} ai={ai} />)}</div></>}
      {(snapshot.skipped_kpis || []).length > 0 && <details className="dashboard-skipped"><summary>{snapshot.skipped_kpis.length} measure(s) unavailable from this export</summary><ul>{snapshot.skipped_kpis.map((item) => <li key={item.key}>{item.name}: {item.reason}</li>)}</ul></details>}
      <div className="dashboard-source-foot">Saved {new Date(snapshot.saved_at).toLocaleString()} · KPI version {snapshot.kpi_version} · {(snapshot.period_days || 0)} days</div>
    </section>
  );
}

function UploadPanel({ uploads, sharedFiles, busy, onFiles, onUseShared, onSharedFileRemove, onDate, onSave, onRemove }) {
  return (
    <section className="dashboard-upload-panel" aria-label="Upload exports">
      <div className="dashboard-upload-heading"><div><div className="dashboard-kicker">DATA INPUT</div><h2>Import source exports</h2><p>Excel files are checked before any KPI is saved. Confirm the reporting period for each file.</p></div><span className="dashboard-upload-limit">XLSX, XLSM, XLS · UP TO 20 MB EACH</span></div>
      <label className="dashboard-dropzone"><input type="file" accept=".xlsx,.xlsm,.xls" multiple disabled={busy} onChange={(event) => { onFiles(event.target.files); event.target.value = ''; }} /><span className="dashboard-upload-glyph" aria-hidden="true">↑</span><strong>Choose Excel exports</strong><span>ServiceNow, Traackr and Sprinklr are recognised automatically</span></label>
      {sharedFiles.length > 0 && uploads.length === 0 && <SharedFilePicker title="Use uploaded files" description="Select Excel exports already uploaded during this app session." accept=".xlsx,.xlsm,.xls" files={sharedFiles} maxFiles={4} disabled={busy} onUse={onUseShared} onRemove={onSharedFileRemove} />}
      {uploads.length > 0 && <div className="dashboard-upload-list">{uploads.map((item) => (
        <div className="dashboard-upload-item" key={item.local_id}>
          <div className="dashboard-upload-item-head"><div><strong>{item.file_name}</strong><span>{item.upload_id ? `${item.source} · ${item.row_count?.toLocaleString() || 0} rows` : item.error ? 'Could not inspect file' : 'Reading file...'}</span></div><button className="dashboard-text-button" type="button" onClick={() => onRemove(item.local_id)} disabled={busy}>Remove</button></div>
          {item.error && <p className="dashboard-inline-error">{item.error}</p>}
          {item.upload_id && <><div className="dashboard-date-grid"><label>Period start<input type="date" value={item.period_start || ''} onChange={(event) => onDate(item.local_id, 'period_start', event.target.value)} /></label><label>Period end<input type="date" value={item.period_end || ''} onChange={(event) => onDate(item.local_id, 'period_end', event.target.value)} /></label></div><p className="dashboard-file-note">{item.period_filters_rows ? 'Rows will be filtered to these dates.' : 'These dates label the results; values cover the whole file.'}</p>{(item.warnings || []).map((warning, index) => <p className="dashboard-file-note" key={index}>{warning}</p>)}</>}
        </div>
      ))}</div>}
      {uploads.some((item) => item.upload_id) && <div className="dashboard-upload-actions"><button className="dashboard-button primary" type="button" onClick={onSave} disabled={busy}>{busy ? 'Working…' : 'Calculate and save KPIs'}</button><span>AI commentary is attempted after the selected files are saved.</span></div>}
    </section>
  );
}

export function Dashboard({ sharedFiles = [], onFilesAdded = () => {}, onSharedFileRemove }) {
  const [periods, setPeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [periodData, setPeriodData] = useState(null);
  const [activeSource, setActiveSource] = useState('ServiceNow');
  const [uploads, setUploads] = useState([]);
  const [showUpload, setShowUpload] = useState(false);
  const [busy, setBusy] = useState('');
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState(null);

  async function refreshPeriods(preferred) {
    const response = await listPeriods();
    const next = response.periods || [];
    setPeriods(next);
    setSelectedPeriod((current) => {
      const available = next.map(periodKey);
      return available.includes(preferred) ? preferred : available.includes(current) ? current : available[0] || '';
    });
    return next;
  }

  useEffect(() => {
    let mounted = true;
    listPeriods().then((result) => {
      if (!mounted) return;
      const next = result.periods || [];
      setPeriods(next);
      setSelectedPeriod(next[0] ? periodKey(next[0]) : '');
      setShowUpload(next.length === 0);
    }).catch((error) => { if (mounted) setNotice({ type: 'error', text: error.message }); }).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!selectedPeriod) { setPeriodData(null); return undefined; }
    const [start, end] = splitPeriod(selectedPeriod);
    const controller = new AbortController();
    setPeriodData(null);
    setLoading(true);
    getPeriod(start, end, controller.signal).then(setPeriodData).catch((error) => { if (error.name !== 'AbortError') setNotice({ type: 'error', text: error.message }); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [selectedPeriod]);

  useEffect(() => {
    if (!periodData) return;
    if (!periodData.sources?.[activeSource]) setActiveSource(SOURCE_ORDER.find((source) => periodData.sources?.[source]) || 'ServiceNow');
  }, [periodData, activeSource]);

  async function inspectFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    if (uploads.filter((item) => item.upload_id).length + files.length > 4) {
      setNotice({ type: 'error', text: 'Inspect up to four source exports at a time.' });
      return;
    }
    onFilesAdded(files);
    setBusy('upload');
    setNotice(null);
    const results = await Promise.all(files.map(async (file) => {
      const local_id = `${Date.now()}-${Math.random()}`;
      try { return { local_id, ...(await inspectFile(file)) }; }
      catch (error) { return { local_id, file_name: file.name, error: error.message }; }
    }));
    setUploads((current) => [...current, ...results]);
    setBusy('');
  }

  async function inspectSharedFiles(items) {
    const files = items.map((item) => item.file);
    if (uploads.filter((item) => item.upload_id).length + files.length > 4) {
      throw new Error('Inspect up to four source exports at a time. Remove an inspected export first.');
    }
    onFilesAdded(files);
    setBusy('upload');
    setNotice(null);
    const results = await Promise.all(files.map(async (file) => {
      const local_id = `${Date.now()}-${Math.random()}`;
      try { return { local_id, ...(await inspectFile(file)) }; }
      catch (error) { return { local_id, file_name: file.name, error: error.message }; }
    }));
    setUploads((current) => [...current, ...results]);
    setBusy('');
  }

  async function saveFiles() {
    const ready = uploads.filter((item) => item.upload_id);
    if (!ready.length) return;
    const badDates = ready.find((item) => !item.period_start || !item.period_end || item.period_end < item.period_start);
    if (badDates) { setNotice({ type: 'error', text: 'Check the start and end dates for each file.' }); return; }
    setShowUpload(false);
    setBusy('save');
    setNotice(null);
    const saved = [];
    const failed = {};
    for (const item of ready) {
      try { await saveSnapshot(item); saved.push(item); }
      catch (error) { failed[item.local_id] = error.message; }
    }
    setUploads((current) => current.filter((item) => !saved.some((done) => done.local_id === item.local_id)).map((item) => failed[item.local_id] ? { ...item, error: failed[item.local_id] } : item));
    const keys = [...new Set(saved.map(periodKey))];
    let aiNote = '';
    for (const key of keys) {
      try {
        const [start, end] = splitPeriod(key);
        const ai = await generateInsights(start, end);
        if (!ai.available) aiNote = 'KPIs were saved. AI commentary is not available yet.';
      } catch { aiNote = 'KPIs were saved. AI commentary can be retried later.'; }
    }
    if (saved.length) {
      try {
        const preferred = keys[keys.length - 1];
        await refreshPeriods(preferred);
        setPeriodData(await getPeriod(...splitPeriod(preferred)));
        setShowUpload(false);
      }
      catch (error) { setNotice({ type: 'error', text: error.message }); }
    }
    if (Object.keys(failed).length) {
      setShowUpload(true);
      setNotice({ type: 'error', text: `${Object.keys(failed).length} file(s) could not be saved. Check their messages below.` });
    }
    else if (saved.length) setNotice({ type: 'success', text: `${saved.length} source export(s) saved. ${aiNote}`.trim() });
    else setShowUpload(true);
    setBusy('');
  }

  async function handleInsights() {
    if (!selectedPeriod) return;
    setBusy('ai'); setNotice(null);
    try {
      const [start, end] = splitPeriod(selectedPeriod);
      const result = await generateInsights(start, end);
      setPeriodData(await getPeriod(start, end));
      setNotice({ type: result.available ? 'success' : 'info', text: result.available ? 'AI insights updated.' : result.notes?.[0] || 'AI commentary is not available.' });
    } catch (error) { setNotice({ type: 'error', text: error.message }); }
    finally { setBusy(''); }
  }

  async function handleReport() {
    if (!selectedPeriod) return;
    setBusy('report'); setNotice(null);
    try {
      const result = await downloadReport(...splitPeriod(selectedPeriod), periodData);
      if (result.fallbackCount) setNotice({ type: 'info', text: `Report downloaded. ${result.fallbackCount} chart(s) used the PowerPoint fallback style.` });
    }
    catch (error) { setNotice({ type: 'error', text: error.message }); }
    finally { setBusy(''); }
  }

  const selected = periods.find((item) => periodKey(item) === selectedPeriod);
  const sources = periodData?.sources || {};
  const available = SOURCE_ORDER.filter((source) => sources[source]);
  const kpiCount = available.reduce((sum, source) => sum + Object.keys(sources[source].kpis || {}).length, 0);
  const aiCount = Object.keys(periodData?.ai?.entries || {}).length;

  return (
    <div className="dashboard-page">
      <header className="dashboard-header"><div><div className="dashboard-kicker">PERFORMANCE INTELLIGENCE</div><h1>Executive dashboard</h1><p>A focused view of service delivery, influencer activity and social performance.</p></div><div className="dashboard-header-actions"><button className="dashboard-button secondary" type="button" disabled={Boolean(busy)} onClick={() => setShowUpload((value) => !value)}>{showUpload ? 'Close import' : 'Import data'}</button><button className="dashboard-button primary" type="button" disabled={!selectedPeriod || Boolean(busy)} onClick={handleReport}>{busy === 'report' ? 'Preparing…' : 'Download report'}</button></div></header>
      {notice && <div role="status" className={`dashboard-notice ${notice.type}`}><span>{notice.text}</span><button type="button" aria-label="Dismiss message" onClick={() => setNotice(null)}>×</button></div>}
      {busy === 'save' && <div className="dashboard-ai-loading" role="status"><span className="dashboard-ai-spinner" aria-hidden="true" /><span><strong>Generating AI insights...</strong><small>Saving KPIs and preparing recommendations for this period.</small></span></div>}
      {showUpload && <UploadPanel uploads={uploads} sharedFiles={sharedFiles} busy={Boolean(busy)} onFiles={inspectFiles} onUseShared={inspectSharedFiles} onSharedFileRemove={onSharedFileRemove} onDate={(id, field, value) => setUploads((current) => current.map((item) => item.local_id === id ? { ...item, [field]: value } : item))} onSave={saveFiles} onRemove={(id) => setUploads((current) => current.filter((item) => item.local_id !== id))} />}
      {!periods.length && !loading ? <section className="dashboard-empty"><div className="dashboard-empty-symbol" aria-hidden="true">↗</div><div className="dashboard-kicker">READY FOR YOUR DATA</div><h2>Turn source exports into a clear performance story.</h2><p>Import a ServiceNow, Traackr or Sprinklr workbook to calculate the fixed KPIs. Results appear here as cards, charts and ranked tables.</p><button className="dashboard-button primary" type="button" onClick={() => setShowUpload(true)}>Import your first export</button></section> : null}
      {periods.length > 0 && <>
        <div className="dashboard-toolbar"><div><label htmlFor="dashboard-period">REPORTING PERIOD</label><select id="dashboard-period" value={selectedPeriod} onChange={(event) => setSelectedPeriod(event.target.value)}>{periods.map((item) => <option key={periodKey(item)} value={periodKey(item)}>{dateLabel(item.period_start)} – {dateLabel(item.period_end)}</option>)}</select></div><span className="dashboard-updated">{selected?.last_updated ? `Updated ${new Date(selected.last_updated).toLocaleString()}` : ''}</span><button className="dashboard-text-button" type="button" disabled={Boolean(busy)} onClick={handleInsights}>{busy === 'ai' ? 'Writing insights…' : 'Regenerate AI insights'}</button></div>
        <div className="dashboard-overview"><div className="dashboard-overview-main"><span className="dashboard-kicker">PERIOD AT A GLANCE</span><strong>{dateLabel(selected?.period_start)} <span>—</span> {dateLabel(selected?.period_end)}</strong><small>Calculated from the uploaded source exports</small></div><div className="dashboard-overview-stat"><strong>{available.length}</strong><span>Sources loaded</span></div><div className="dashboard-overview-stat"><strong>{kpiCount}</strong><span>KPI views</span></div><div className="dashboard-overview-stat"><strong>{aiCount}</strong><span>AI insights</span></div></div>
        <div className="dashboard-source-tabs" role="tablist" aria-label="Data source">{SOURCE_ORDER.map((source) => <button key={source} type="button" role="tab" aria-selected={activeSource === source} className={activeSource === source ? 'active' : ''} onClick={() => setActiveSource(source)}><span>{source}</span><span className={sources[source] ? 'dashboard-tab-status available' : 'dashboard-tab-status'}>{sources[source] ? 'Ready' : 'No data'}</span></button>)}</div>
        {loading && !periodData ? <div className="dashboard-loading">Loading saved results…</div> : <SourceView source={activeSource} snapshot={sources[activeSource]} ai={periodData?.ai} />}
      </>}
    </div>
  );
}
