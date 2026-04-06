import { api } from './client';

export const users = {
  list: () => api.get('/users/'),
  invite: (payload) => api.post('/users/invite', payload),
  updateRole: (id, role) => api.patch(`/users/${id}/role`, { role }),
  deactivate: (id) => api.delete(`/users/${id}`),
};
