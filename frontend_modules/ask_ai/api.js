import { request } from '../shared/apiClient.js';

export async function createSession(files) {
  const body = new FormData();
  Array.from(files).forEach((file) => body.append('files', file));
  return (await request('/api/ask-ai/sessions', { method: 'POST', body })).json();
}

export async function getSession(sessionId) {
  return (await request(`/api/ask-ai/sessions/${sessionId}`)).json();
}

export async function getTable(sessionId, alias) {
  return (await request(`/api/ask-ai/sessions/${sessionId}/tables/${encodeURIComponent(alias)}`)).json();
}

export async function askQuestion(sessionId, question) {
  return (await request(`/api/ask-ai/sessions/${sessionId}/questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })).json();
}

export async function getAnswer(sessionId, answerId) {
  return (await request(`/api/ask-ai/sessions/${sessionId}/answers/${answerId}`)).json();
}

export async function clearChat(sessionId) {
  return (await request(`/api/ask-ai/sessions/${sessionId}/clear`, { method: 'POST' })).json();
}

export async function endSession(sessionId) {
  await request(`/api/ask-ai/sessions/${sessionId}`, { method: 'DELETE' });
}

async function download(path, filename) {
  const response = await request(path);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadExcel(sessionId, answerId) {
  return download(`/api/ask-ai/sessions/${sessionId}/answers/${answerId}/tables.xlsx`, `answer_${answerId.slice(0, 8)}.xlsx`);
}

export function downloadPng(sessionId, answerId, index) {
  return download(`/api/ask-ai/sessions/${sessionId}/answers/${answerId}/charts/${index}.png`, `chart_${answerId.slice(0, 8)}_${index + 1}.png`);
}
