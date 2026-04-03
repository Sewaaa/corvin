import { api } from './client';

export const breach = {
  list: () => api.get('/breach/'),
  add: (email) => api.post('/breach/', { email }),
  check: (id) => api.post(`/breach/${id}/check`),
  remove: (id) => api.delete(`/breach/${id}`),
  results: (id) => api.get(`/breach/${id}/results`),
};
