import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { to: '/',           label: 'Dashboard',         icon: '⬡' },
  { to: '/breach',     label: 'Breach Monitor',    icon: '⚠' },
  { to: '/domain',     label: 'Domain Reputation', icon: '◈' },
  { to: '/web-scan',   label: 'Web Scanner',       icon: '⊕' },
  { to: '/email',      label: 'Email Protection',  icon: '✉' },
  { to: '/sandbox',    label: 'File Sandbox',      icon: '⧫' },
  { to: '/notifications', label: 'Notifications',  icon: '◉' },
  { to: '/reports',       label: 'Reports',         icon: '▤' },
];

export default function Sidebar({ unreadCount = 0 }) {
  const { user, logout } = useAuth();

  return (
    <aside className="w-56 min-h-screen bg-corvin-900 border-r border-corvin-700 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-corvin-700">
        <span className="text-xl font-bold text-corvin-accent tracking-tight">Corvin</span>
        <p className="text-xs text-gray-500 mt-0.5">Security Platform</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-2 space-y-0.5">
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-corvin-700 text-white font-medium'
                  : 'text-gray-400 hover:text-white hover:bg-corvin-800'
              }`
            }
          >
            <span className="text-base w-4 text-center">{icon}</span>
            <span className="flex-1">{label}</span>
            {to === '/notifications' && unreadCount > 0 && (
              <span className="bg-corvin-accent text-white text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-4 py-4 border-t border-corvin-700">
        <p className="text-xs text-gray-400 truncate">{user?.full_name}</p>
        <p className="text-xs text-gray-600 truncate mb-2">{user?.email}</p>
        <button
          onClick={logout}
          className="text-xs text-gray-500 hover:text-red-400 transition-colors"
        >
          Disconnetti →
        </button>
      </div>
    </aside>
  );
}
