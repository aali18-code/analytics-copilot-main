import { request } from '../shared/apiClient.js';

export async function getMonitoring(window) {
  return (await request(`/api/monitoring/calls?window=${encodeURIComponent(window)}`)).json();
}
