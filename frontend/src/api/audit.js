import { api } from './client';

export const audit = {
  list: (page = 1, limit = 50, action = '') => {
    let qs = `?page=${page}&limit=${limit}`;
    if (action) qs += `&action=${encodeURIComponent(action)}`;
    return api.get(`/audit${qs}`);
  },
};
