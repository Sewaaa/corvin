import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';

/* ── Raven logo mark (shared) ────────────────────────────────────────── */
function RavenIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
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

/* ── Mock dashboard rendered in background ───────────────────────────── */
function MockDashboard() {
  const stats = [
    { label: 'Violazioni rilevate', value: '3', sub: '2 critiche', color: 'text-red-600', bg: 'bg-red-50 border-red-100' },
    { label: 'Domini monitorati', value: '7', sub: 'Score medio 84', color: 'text-violet-600', bg: 'bg-violet-50 border-violet-100' },
    { label: 'Email analizzate', value: '142', sub: '1 in quarantena', color: 'text-amber-600', bg: 'bg-amber-50 border-amber-100' },
    { label: 'File scansionati', value: '28', sub: 'Tutti puliti', color: 'text-green-600', bg: 'bg-green-50 border-green-100' },
  ];

  const navItems = [
    { label: 'Dashboard', active: true },
    { label: 'Monitoraggio Violazioni' },
    { label: 'Reputazione Domini' },
    { label: 'Scanner Web' },
    { label: 'Protezione Email' },
    { label: 'Sandbox File' },
    { label: 'Notifiche' },
    { label: 'Report' },
  ];

  const alerts = [
    { sev: 'Critico', title: 'Email aziendale in breach recente', mod: 'Breach Monitor', color: 'bg-red-100 text-red-700 border-red-200' },
    { sev: 'Medio', title: 'Certificato SSL in scadenza tra 12 giorni', mod: 'Reputazione Domini', color: 'bg-amber-100 text-amber-700 border-amber-200' },
    { sev: 'Basso', title: 'Header X-Frame-Options mancante', mod: 'Scanner Web', color: 'bg-blue-100 text-blue-700 border-blue-200' },
  ];

  return (
    <div className="flex h-screen w-full bg-corvin-50 overflow-hidden select-none" aria-hidden="true">
      {/* Sidebar */}
      <div className="w-56 flex-shrink-0 bg-corvin-nav flex flex-col py-4 gap-1 px-2">
        <div className="flex items-center gap-2.5 px-3 pb-5 pt-1">
          <div className="w-7 h-7 rounded-xl bg-violet-700 flex items-center justify-center shadow-md shadow-violet-900/40">
            <RavenIcon className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="text-white font-bold text-sm">Corvin</span>
            <p className="text-[9px] text-white/35 uppercase tracking-widest leading-none mt-0.5">Threat Intelligence</p>
          </div>
        </div>
        {navItems.map((item, i) => (
          <div key={i} className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs ${item.active ? 'bg-violet-700 text-white font-semibold' : 'text-white/55'}`}>
            <span>{item.label}</span>
          </div>
        ))}
      </div>

      {/* Main area */}
      <div className="flex-1 overflow-hidden p-6 flex flex-col gap-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">Dashboard</h1>
            <p className="text-xs text-gray-500">Panoramica sicurezza — Acme Corp</p>
          </div>
          <div className="flex gap-2">
            <div className="h-7 w-24 rounded-lg bg-gray-200 animate-pulse" />
            <div className="h-7 w-7 rounded-full bg-blue-100" />
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-4 gap-3">
          {stats.map((s, i) => (
            <div key={i} className={`rounded-xl border p-3.5 ${s.bg}`}>
              <p className="text-xs text-gray-500 mb-1">{s.label}</p>
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{s.sub}</p>
            </div>
          ))}
        </div>

        {/* Content row */}
        <div className="flex gap-4 flex-1 min-h-0">
          {/* Alert list */}
          <div className="flex-1 bg-white rounded-xl border border-corvin-200 p-4 flex flex-col gap-2 min-h-0 overflow-hidden">
            <p className="text-xs font-semibold text-gray-700 mb-1">Ultimi avvisi</p>
            {alerts.map((a, i) => (
              <div key={i} className={`flex items-start gap-2.5 rounded-lg border px-3 py-2 ${a.color}`}>
                <div className="mt-0.5">
                  <span className="text-xs font-semibold">{a.sev}</span>
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium truncate">{a.title}</p>
                  <p className="text-xs opacity-70">{a.mod}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Fake chart */}
          <div className="w-56 bg-white rounded-xl border border-corvin-200 p-4 flex flex-col gap-3">
            <p className="text-xs font-semibold text-gray-700">Moduli attivi</p>
            {[
              { label: 'Breach', pct: 75, color: 'bg-red-400' },
              { label: 'Domini', pct: 90, color: 'bg-violet-400' },
              { label: 'Email', pct: 60, color: 'bg-amber-400' },
              { label: 'Web', pct: 45, color: 'bg-indigo-400' },
              { label: 'File', pct: 30, color: 'bg-green-400' },
            ].map((bar, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-xs text-gray-500 w-12">{bar.label}</span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${bar.color}`} style={{ width: `${bar.pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Login page ──────────────────────────────────────────────────────── */
export default function Login() {
  const { login, register } = useAuth();
  const { t } = useSettings();
  const navigate = useNavigate();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({
    email: '', password: '', full_name: '', organization_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(form.email, form.password);
      } else {
        await register({
          email: form.email,
          password: form.password,
          full_name: form.full_name,
          organization_name: form.organization_name,
        });
      }
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* ── Blurred dashboard background ── */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <MockDashboard />
        {/* Dark overlay + blur */}
        <div className="absolute inset-0 backdrop-blur-sm bg-gray-900/40" />
      </div>

      {/* ── Login card ── */}
      <div className="relative z-10 min-h-screen flex flex-col items-center justify-center px-4">
        {/* Badge above card */}
        <div className="mb-4 flex items-center gap-2 bg-white/10 backdrop-blur-md border border-white/20 text-white text-xs px-3 py-1.5 rounded-full shadow">
          <RavenIcon className="w-3.5 h-3.5" />
          {t('login.badge') || 'Accedi per sbloccare la dashboard'}
        </div>

        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-violet-700 mb-4 shadow-lg shadow-violet-900/40 ring-4 ring-white/20">
              <RavenIcon className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white">{t('login.title')}</h1>
            <p className="text-white/70 text-sm mt-1">{t('login.subtitle')}</p>
          </div>

          <div className="bg-white/95 backdrop-blur-md rounded-2xl shadow-2xl border border-white/30 p-6">
            {/* Toggle */}
            <div className="flex mb-6 bg-corvin-100 rounded-xl p-1 gap-1">
              {['login', 'register'].map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); setError(''); }}
                  className={`flex-1 py-2 text-sm rounded-lg font-medium transition-all ${
                    mode === m
                      ? 'bg-white text-gray-900 shadow-card'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {t(`login.tab.${m}`)}
                </button>
              ))}
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'register' && (
                <>
                  <Field label={t('login.fullName')} value={form.full_name} onChange={set('full_name')} required />
                  <Field label={t('login.orgName')} value={form.organization_name} onChange={set('organization_name')} required />
                </>
              )}
              <Field label={t('login.email')} type="email" value={form.email} onChange={set('email')} required />
              <Field label={t('login.password')} type="password" value={form.password} onChange={set('password')} required />

              {error && (
                <div className="flex gap-2.5 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                  <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 8v4M12 16h.01" />
                  </svg>
                  <span>{error}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full py-2.5 text-base justify-center flex items-center gap-2"
              >
                {loading && (
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                )}
                {loading ? t('common.loading') : t(`login.submit.${mode}`)}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, type = 'text', value, onChange, required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        className="form-input"
      />
    </div>
  );
}
