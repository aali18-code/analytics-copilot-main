import { request } from '../shared/apiClient.js';
import { renderChartPng } from './KpiChart.jsx';

export async function inspectFile(file) {
  const body = new FormData();
  body.append('file', file);
  return (await request('/api/dashboard/uploads/inspect', { method: 'POST', body })).json();
}

export async function saveSnapshot(item) {
  return (await request('/api/dashboard/snapshots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ upload_id: item.upload_id, period_start: item.period_start, period_end: item.period_end, generate_ai: false }),
  })).json();
}

export async function listPeriods() {
  return (await request('/api/dashboard/periods')).json();
}

export async function getPeriod(start, end, signal) {
  return (await request(`/api/dashboard/periods/${start}/${end}`, { signal })).json();
}

export async function generateInsights(start, end) {
  return (await request(`/api/dashboard/periods/${start}/${end}/insights`, { method: 'POST' })).json();
}

export async function downloadReport(start, end, loadedPeriod) {
  const period = loadedPeriod?.period_start === start && loadedPeriod?.period_end === end
    ? loadedPeriod : await getPeriod(start, end);
  const chart_images = {};
  let fallbackCount = 0;
  for (const snapshot of Object.values(period.sources || {})) {
    if (!snapshot) continue;
    for (const chart of snapshot.charts || []) {
      const kpi = snapshot.kpis?.[chart.kpi_key];
      if (kpi?.kind !== 'breakdown') continue;
      try { chart_images[chart.kpi_key] = renderChartPng(chart, kpi.unit); }
      catch { fallbackCount += 1; }
    }
  }
  const response = await request(`/api/dashboard/periods/${start}/${end}/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chart_images }),
  });
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = `kpi_report_${start}_${end}.pptx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return { fallbackCount };
}
