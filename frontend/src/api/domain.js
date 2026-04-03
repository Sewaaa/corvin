import { api } from './client';

export const domain = {
  list: () => api.get('/domain/'),
  add: (domainName) => api.post('/domain/', { domain: domainName }),
  get: (id) => api.get(`/domain/${id}`),
  verify: (id) => api.post(`/domain/${id}/verify`),
  scan: (id) => api.post(`/domain/${id}/scan`),
  remove: (id) => api.delete(`/domain/${id}`),
};
