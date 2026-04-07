import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StatCard from '../components/StatCard';
import SeverityBadge from '../components/SeverityBadge';
import { useSettings } from '../context/SettingsContext';
import { breach } from '../api/breach';
import { domain } from '../api/domain';
import { notifications } from '../api/notifications';
import { sandbox } from '../api/sandbox';
import { api } from '../api/client';

const MODULE_CARDS = [
  { to: '/breach',        labelKey: 'dash.mod.breach',    descKey: 'dash.mod.breachDesc',   color: 'bg-red-50 border-red-100', iconColor: 'text-red-600', icon: ShieldAlertIcon },
  { to: '/domain',        labelKey: 'dash.mod.domain',    descKey: 'dash.mod.domainDesc',   color: 'bg-blue-50 border-blue-100', iconColor: 'text-blue-600', icon: GlobeIcon },
  { to: '/web-scan',      labelKey: 'dash.mod.webScan',   descKey: 'dash.mod.webScanDesc',  color: 'bg-indigo-50 border-indigo-100', iconColor: 'text-indigo-600', icon: ScanIcon },
  { to: '/email',         labelKey: 'dash.mod.email',     descKey: 'dash.mod.emailDesc',    color: 'bg-amber-50 border-amber-100', iconColor: 'text-amber-600', icon: MailIcon },
  { to: '/sandbox',       labelKey: 'dash.mod.sandbox',   descKey: 'dash.mod.sandboxDesc',  color: 'bg-orange-50 border-orange-100', iconColor: 'text-orange-600', icon: FileIcon },
  { to: '/notifications', labelKey: 'dash.mod.notif',     descKey: 'dash.mod.notifDesc',    color: 'bg-green-50 border-green-100', iconColor: 'text-green-600', icon: BellIcon },
];

function RiskGauge({ score, t }) {
  const isOk = score === 0;
  const isLow = score > 0 && score < 30;
  const isMed = score >= 30 && score < 60;
  const isHigh = score >= 60 && score < 80;

  const { color, bgBar, bgLight, labelKey, messageKey } = isOk
    ? { color: 'text-green-700', bgBar: 'bg-green-500', bgLight: 'bg-green-50 border-green-200', labelKey: 'dash.risk.safe', messageKey: 'dash.risk.safeSub' }
    : isLow
    ? { color: 'text-blue-700', bgBar: 'bg-blue-500', bgLight: 'bg-blue-50 border-blue-200', labelKey: 'dash.risk.low', messageKey: 'dash.risk.lowSub' }
    : isMed
    ? { color: 'text-amber-700', bgBar: 'bg-amber-500', bgLight: 'bg-amber-50 border-amber-200', labelKey: 'dash.risk.medium', messageKey: 'dash.risk.mediumSub' }
    : isHigh
    ? { color: 'text-orange-700', bgBar: 'bg-orange-500', bgLight: 'bg-orange-50 border-orange-200', labelKey: 'dash.risk.high', messageKey: 'dash.risk.highSub' }
    : { color: 'text-red-700', bgBar: 'bg-red-600', bgLight: 'bg-red-50 border-red-200', labelKey: 'dash.risk.critical', messageKey: 'dash.risk.criticalSub' };

  return (
    <div className={`bg-white rounded-xl shadow-card border p-5 ${bgLight.split(' ')[1]}`}>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">{t('dash.riskScore')}</p>
      <div className="flex items-end gap-4 mb-4">
        <span className={`text-5xl font-bold tabular-nums ${color}`}>{score}</span>
        <div className="flex-1 mb-1.5">
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm font-semibold ${color}`}>{t(labelKey)}</span>
            <span className="text-xs text-gray-400">{t('dash.outOf')}</span>
          </div>
          <div className="h-2.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full ${bgBar} rounded-full transition-all duration-700`}
              style={{ width: `${Math.min(score, 100)}%` }}
            />
          </div>
        </div>
      </div>
      <p className="text-sm text-gray-600">{t(messageKey)}</p>
    </div>
  );
}

function RecentActivity({ items, t }) {
  if (!items?.length) {
    return (
      <div className="bg-white rounded-xl shadow-card border border-corvin-200 p-5">
        <p className="text-sm font-semibold text-gray-700 mb-3">{t('dash.activity')}</p>
        <p className="text-sm text-gray-400 py-4 text-center">{t('dash.noActivity')}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-card border border-corvin-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold text-gray-700">{t('dash.activity')}</p>
        <Link to="/notifications" className="text-xs text-blue-600 hover:text-blue-700 font-medium">
          {t('dash.viewAll')}
        </Link>
      </div>
      <div className="space-y-1">
        {items.map((n) => (
          <div key={n.id} className="flex items-start gap-3 py-2.5 border-b border-corvin-100 last:border-0">
            <SeverityBadge value={n.severity} />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-900 font-medium truncate">{n.title}</p>
              <p className="text-xs text-gray-500 truncate">{n.message}</p>
            </div>
            <span className="text-xs text-gray-400 flex-shrink-0 whitespace-nowrap">
              {new Date(n.created_at).toLocaleDateString('it-IT')}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { t } = useSettings();
  const [stats, setStats] = useState({ emails: 0, domains: 0, unread: 0, threats: 0 });
  const [apiOk, setApiOk] = useState(null);
  const [riskScore, setRiskScore] = useState(null);
  const [recentNotifs, setRecentNotifs] = useState([]);

  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then((d) => setApiOk(d.status === 'ok' || d.status === 'healthy'))
      .catch(() => setApiOk(false));

    api.get('/organizations/summary')
      .then((s) => setRiskScore(s?.risk_score ?? 0))
      .catch(() => setRiskScore(0));

    api.get('/notifications/?limit=8')
      .then((data) => setRecentNotifs(data?.items ?? []))
      .catch(() => {});

    Promise.allSettled([
      breach.list(),
      domain.list(),
      notifications.list('?limit=1&is_read=false'),
      sandbox.list('?status=malicious&limit=1'),
    ]).then(([b, d, n, s]) => {
      setStats({
        emails: b.status === 'fulfilled' ? (b.value?.length ?? 0) : 0,
        domains: d.status === 'fulfilled' ? (d.value?.length ?? 0) : 0,
        unread: n.status === 'fulfilled' ? (n.value?.total ?? 0) : 0,
        threats: s.status === 'fulfilled' ? (s.value?.length ?? 0) : 0,
      });
    });
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('dash.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('dash.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-corvin-200 shadow-card text-sm">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
            apiOk === null ? 'bg-amber-400 animate-pulse' : apiOk ? 'bg-green-500' : 'bg-red-500'
          }`} />
          <span className="text-gray-600">
            {apiOk === null ? t('dash.api.checking') : apiOk ? t('dash.api.online') : t('dash.api.offline')}
          </span>
        </div>
      </div>

      {/* Risk score + Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <div className="lg:col-span-1">
          {riskScore !== null ? (
            <RiskGauge score={riskScore} t={t} />
          ) : (
            <div className="bg-white rounded-xl shadow-card border border-corvin-200 p-5 h-full flex items-center justify-center">
              <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full" />
            </div>
          )}
        </div>
        <div className="lg:col-span-2 grid grid-cols-2 gap-4">
          <StatCard label={t('dash.stat.emails')} value={stats.emails} to="/breach" />
          <StatCard label={t('dash.stat.domains')} value={stats.domains} to="/domain" />
          <StatCard label={t('dash.stat.unread')} value={stats.unread} accent={stats.unread > 0} to="/notifications" />
          <StatCard label={t('dash.stat.malicious')} value={stats.threats} accent={stats.threats > 0} to="/sandbox" />
        </div>
      </div>

      {/* Recent activity */}
      <div className="mb-10">
        <RecentActivity items={recentNotifs} t={t} />
      </div>

      {/* Module grid */}
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">{t('dash.modules')}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {MODULE_CARDS.map(({ to, labelKey, descKey, color, iconColor, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className={`bg-white border rounded-xl p-5 hover:shadow-card-md transition-all group ${color}`}
          >
            <div className="flex items-start gap-3">
              <div className={`mt-0.5 ${iconColor}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 group-hover:text-blue-700 transition-colors">
                  {t(labelKey)}
                </h3>
                <p className="text-sm text-gray-500 mt-0.5 leading-snug">{t(descKey)}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

// Icons
function ShieldAlertIcon({ className }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>;
}
function GlobeIcon({ className }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20" /></svg>;
}
function ScanIcon({ className }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>;
}
function MailIcon({ className }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="M2 7l10 7 10-7" /></svg>;
}
function FileIcon({ className }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h5" /></svg>;
}
function BellIcon({ className }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" /></svg>;
}
