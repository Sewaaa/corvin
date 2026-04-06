import { api } from './client';

export const breach = {
  list: () => api.get('/breach/emails'),
  add: (email) => api.post('/breach/check', { emails: [email] }),
  checkAll: (emails) => api.post('/breach/check', { emails }),
  history: (page = 1, limit = 50) => api.get(`/breach/history?page=${page}&limit=${limit}`),
  remove: (id) => api.delete(`/breach/emails/${id}`),
};
