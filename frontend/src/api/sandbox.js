import { api } from './client';

export const sandbox = {
  list: (params = '') => api.get(`/sandbox/${params}`),
  upload: (formData) => api.upload('/sandbox/upload', formData),
  get: (id) => api.get(`/sandbox/${id}`),
  remove: (id) => api.delete(`/sandbox/${id}`),
};
