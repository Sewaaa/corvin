import { api } from './client';

export const notifications = {
  list: (params = '') => api.get(`/notifications/${params}`),
  get: (id) => api.get(`/notifications/${id}`),
  markRead: (id) => api.patch(`/notifications/${id}/read`),
  markAllRead: () => api.post('/notifications/read-all'),
  listWebhooks: () => api.get('/notifications/webhooks'),
  addWebhook: (payload) => api.post('/notifications/webhooks', payload),
  deleteWebhook: (id) => api.delete(`/notifications/webhooks/${id}`),
  testWebhook: (id) => api.post(`/notifications/webhooks/${id}/test`),
};
