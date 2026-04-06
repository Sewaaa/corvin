import { api } from './client';

export const email = {
  listAccounts: () => api.get('/email/accounts'),
  addAccount: (payload) => api.post('/email/accounts', payload),
  deleteAccount: (id) => api.delete(`/email/accounts/${id}`),
  triggerScan: (id) => api.post(`/email/accounts/${id}/scan`),
  listThreats: (params = '') => api.get(`/email/threats${params}`),
  listThreatsByAccount: (emailAddress) => api.get(`/email/threats?recipient=${encodeURIComponent(emailAddress)}&limit=100`),
  getThreat: (id) => api.get(`/email/threats/${id}`),
  updateThreat: (id, action) => api.patch(`/email/threats/${id}`, { action }),
};
