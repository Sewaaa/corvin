import { api } from './client';

export const webScan = {
  list: (params = '') => api.get(`/web-scan/${params}`),
  start: (domainId, frequency = 'manual') =>
    api.post('/web-scan/', { domain_id: domainId, frequency }),
  get: (id) => api.get(`/web-scan/${id}`),
  remove: (id) => api.delete(`/web-scan/${id}`),
};
