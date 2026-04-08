import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { notifications } from '../api/notifications';

export default function Layout() {
  const [unread, setUnread] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
    <div className="flex h-screen overflow-hidden bg-corvin-50">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — off-screen on mobile, slide in when open */}
      <div
        className={`fixed inset-y-0 left-0 z-30 transition-transform duration-200 ease-in-out
          lg:relative lg:translate-x-0 lg:flex ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <Sidebar unreadCount={unread} onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main area */}
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">
        {/* Mobile top bar */}
        <header className="lg:hidden flex items-center gap-3 px-4 h-14 bg-corvin-nav border-b border-white/8 flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-white/70 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors -ml-1"
            aria-label="Apri menu"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-violet-700 flex items-center justify-center shadow-sm flex-shrink-0">
              <svg className="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M5 20C3.5 16 3.5 10 5.5 7C7 5 9.5 3.5 12.5 3.5C15.5 3.5 17.5 5 18.5 6.5L22 9C22.5 10 22 11.2 21 11L18.5 10C17.5 10.5 16.5 12 15.5 14C14 17 12 19.5 9.5 21L7.5 21.5L6 20.5ZM16.2 7a1.25 1.25 0 1 0-2.5 0a1.25 1.25 0 1 0 2.5 0" />
              </svg>
            </div>
            <span className="text-white font-bold text-sm">Corvin</span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto px-4 py-5 md:px-6 md:py-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
