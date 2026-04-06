import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { notifications } from '../api/notifications';

export default function Layout() {
  const [unread, setUnread] = useState(0);

  // Polling leggero: conta non lette ogni 60s
  useEffect(() => {
    const fetch = () =>
      notifications.list('?limit=1&is_read=false')
        .then((d) => setUnread(d?.total ?? 0))
        .catch(() => {});
    fetch();
    const id = setInterval(fetch, 60_000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex min-h-screen bg-corvin-50">
      <Sidebar unreadCount={unread} />
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
