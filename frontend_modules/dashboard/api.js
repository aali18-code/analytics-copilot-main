import { request } from '../shared/apiClient.js';

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

export async function downloadReport(start, end) {
  const response = await request(`/api/dashboard/periods/${start}/${end}/report`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = `kpi_report_${start}_${end}.pptx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
