import { api } from './client';

export const breach = {
  list: () => api.get('/breach/emails'),
  add: (email) => api.post('/breach/check', { emails: [email] }),
  checkAll: (emails) => api.post('/breach/check', { emails }),
  remove: (id) => api.delete(`/breach/emails/${id}`),
};
