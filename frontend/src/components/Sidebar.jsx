import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';

const NAV_ITEMS = [
  { to: '/',               labelKey: 'nav.dashboard',       icon: HomeIcon },
  { to: '/breach',         labelKey: 'nav.breach',          icon: ShieldIcon },
  { to: '/domain',         labelKey: 'nav.domain',          icon: GlobeIcon },
  { to: '/web-scan',       labelKey: 'nav.webScan',         icon: SearchIcon },
  { to: '/email',          labelKey: 'nav.email',           icon: MailIcon },
  { to: '/sandbox',        labelKey: 'nav.sandbox',         icon: FileIcon },
  { to: '/notifications',  labelKey: 'nav.notifications',   icon: BellIcon },
  { to: '/reports',        labelKey: 'nav.reports',          icon: ChartIcon },
  { to: '/settings',       labelKey: 'nav.settings',        icon: GearIcon },
];

export default function Sidebar({ unreadCount = 0, onClose = () => {} }) {
  const { user, logout } = useAuth();
  const { t, lang, theme, toggleLang, toggleTheme } = useSettings();
  const initials = user?.full_name
    ? user.full_name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
    : '?';

  return (
    <aside className="w-60 h-full bg-corvin-nav flex flex-col flex-shrink-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-white/8">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-violet-700 flex items-center justify-center flex-shrink-0 shadow-lg shadow-violet-900/40">
            <RavenIcon className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-[15px] font-bold text-white tracking-tight">Corvin</span>
            <p className="text-[10px] text-white/35 leading-none mt-0.5 uppercase tracking-widest">{t('nav.platform')}</p>
          </div>
          {/* Close button — mobile only */}
          <button
            onClick={onClose}
            className="lg:hidden text-white/40 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors flex-shrink-0"
            aria-label="Chiudi menu"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2.5 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ to, labelKey, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                isActive
                  ? 'bg-violet-700 text-white font-semibold shadow-sm shadow-violet-900/50'
                  : 'text-white/55 hover:text-white hover:bg-white/8'
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1 truncate">{t(labelKey)}</span>
            {to === '/notifications' && unreadCount > 0 && (
              <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center leading-none font-semibold">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Lang / Theme toggles */}
      <div className="px-2.5 py-2 border-t border-white/8 flex gap-1.5">
        <button
          onClick={toggleLang}
          className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium text-white/45 hover:text-white hover:bg-white/8 rounded-lg transition-colors"
          title={lang === 'it' ? 'Switch to English' : 'Passa a Italiano'}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20" /></svg>
          {lang === 'it' ? 'IT' : 'EN'}
        </button>
        <button
          onClick={toggleTheme}
          className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium text-white/45 hover:text-white hover:bg-white/8 rounded-lg transition-colors"
          title={theme === 'dark' ? t('theme.dark') : t('theme.light')}
        >
          {theme === 'dark' ? (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" /></svg>
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></svg>
          )}
          {theme === 'dark' ? t('theme.dark') : t('theme.light')}
        </button>
      </div>

      {/* User */}
      <div className="px-2.5 py-3 border-t border-white/8">
        <div className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-white/5 transition-colors">
          <div className="w-7 h-7 rounded-full bg-violet-700/70 flex items-center justify-center text-xs text-white font-semibold flex-shrink-0">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs text-white font-medium truncate">{user?.full_name}</p>
            <p className="text-xs text-white/35 truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full mt-1 text-xs text-white/35 hover:text-white/70 transition-colors py-1.5 text-left px-2"
        >
          {t('nav.logout')}
        </button>
      </div>
    </aside>
  );
}

// ── Raven logo mark ───────────────────────────────────────────────────────────
// Stylized raven in profile: body curves up from tail (left) to crown,
// beak projects to the right, watchful eye below crown.

function RavenIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      {/*
        Raven head in profile, beak facing right.
        fill-rule="evenodd" makes the eye circle a transparent hole.
        Outer path: body/head silhouette (clockwise)
        Inner path: eye circle (creates hole via evenodd)
      */}
      <path
        fillRule="evenodd"
        d="
          M 5 20
          C 3.5 16 3.5 10 5.5 7
          C 7 5 9.5 3.5 12.5 3.5
          C 15.5 3.5 17.5 5 18.5 6.5
          L 22 9
          C 22.5 10 22 11.2 21 11
          L 18.5 10
          C 17.5 10.5 16.5 12 15.5 14
          C 14 17 12 19.5 9.5 21
          L 7.5 21.5
          L 6 20.5
          Z
          M 16.2 7
          a 1.25 1.25 0 1 0 -2.5 0
          a 1.25 1.25 0 1 0 2.5 0
        "
      />
    </svg>
  );
}

// ── SVG Icons ─────────────────────────────────────────────────────────────────

function HomeIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z" />
      <path d="M9 21V12h6v9" />
    </svg>
  );
}

function ShieldIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
    </svg>
  );
}

function GlobeIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20" />
    </svg>
  );
}

function SearchIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

function MailIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="M2 7l10 7 10-7" />
    </svg>
  );
}

function FileIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <path d="M14 2v6h6M8 13h8M8 17h5" />
    </svg>
  );
}

function BellIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" />
    </svg>
  );
}

function ChartIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 20V10M12 20V4M6 20v-6" />
    </svg>
  );
}

function GearIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  );
}
