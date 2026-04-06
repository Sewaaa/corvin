import { api } from './client';

export const reports = {
  summary: () => api.get('/reports/summary'),

  downloadPdf: async () => {
    const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
    const token = localStorage.getItem('access_token');
    const res = await fetch(`${API_BASE}/reports/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Errore generazione PDF');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    a.download = `corvin-report-${date}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },
};
