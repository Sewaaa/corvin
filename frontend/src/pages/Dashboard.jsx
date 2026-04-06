import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StatCard from '../components/StatCard';
import SeverityBadge from '../components/SeverityBadge';
import { breach } from '../api/breach';
import { domain } from '../api/domain';
import { notifications } from '../api/notifications';
import { sandbox } from '../api/sandbox';
import { api } from '../api/client';

const MODULE_CARDS = [
  { to: '/breach',        label: 'Breach Monitor',    desc: 'Monitoraggio HIBP con k-anonymity',    icon: '⚠' },
  { to: '/domain',        label: 'Domain Reputation', desc: 'DNS, DNSBL, SSL, WHOIS analysis',      icon: '◈' },
  { to: '/web-scan',      label: 'Web Scanner',       desc: 'Scansione passiva di vulnerabilità',   icon: '⊕' },
  { to: '/email',         label: 'Email Protection',  desc: 'Phishing, DMARC, spoofing detection',  icon: '✉' },
  { to: '/sandbox',       label: 'File Sandbox',      desc: 'YARA rules, VirusTotal, analisi PE',   icon: '⧫' },
  { to: '/notifications', label: 'Notifications',     desc: 'Alert severity-based, webhook',        icon: '◉' },
];

function RiskGauge({ score }) {
  const color = score >= 70 ? 'text-red-400' : score >= 40 ? 'text-yellow-400' : score > 0 ? 'text-orange-400' : 'text-green-400';
  const bgColor = score >= 70 ? 'bg-red-400' : score >= 40 ? 'bg-yellow-400' : score > 0 ? 'bg-orange-400' : 'bg-green-400';
  const label = score >= 70 ? 'Critico' : score >= 40 ? 'Alto' : score > 0 ? 'Medio' : 'Sicuro';

  return (
    <div className="bg-corvin-800 border border-corvin-700 rounded-xl p-5">
      <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">Risk Score</p>
      <div className="flex items-end gap-4">
        <span className={`text-4xl font-bold ${color}`}>{score}</span>
        <div className="flex-1 mb-1.5">
          <div className="flex items-center justify-between mb-1">
            <span className={`text-xs font-medium ${color}`}>{label}</span>
            <span className="text-xs text-gray-500">/ 100</span>
          </div>
          <div className="h-2 bg-corvin-700 rounded-full overflow-hidden">
            <div
              className={`h-full ${bgColor} rounded-full transition-all duration-500`}
              style={{ width: `${Math.min(score, 100)}%` }}
            />
          </div>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-2">
        Basato sulle notifiche non lette per severity (critical=40, high=20, medium=10, low=5)
      </p>
    </div>
  );
}

function RecentActivity({ items }) {
  if (!items?.length) {
    return (
      <div className="bg-corvin-800 border border-corvin-700 rounded-xl p-5">
        <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">Attività recente</p>
        <p className="text-xs text-gray-500 py-4 text-center">Nessuna notifica recente.</p>
      </div>
    );
  }

  return (
    <div className="bg-corvin-800 border border-corvin-700 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-400 uppercase tracking-wider">Attività recente</p>
        <Link to="/notifications" className="text-xs text-corvin-accent hover:underline">
          Vedi tutte
        </Link>
      </div>
      <div className="space-y-2">
        {items.map((n) => (
          <div key={n.id} className="flex items-start gap-3 py-2 border-b border-corvin-700/40 last:border-0">
            <SeverityBadge value={n.severity} />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-white font-medium truncate">{n.title}</p>
              <p className="text-xs text-gray-500 truncate">{n.message}</p>
            </div>
            <span className="text-xs text-gray-600 flex-shrink-0">
              {new Date(n.created_at).toLocaleDateString('it-IT')}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState({ emails: 0, domains: 0, unread: 0, threats: 0 });
  const [apiOk, setApiOk] = useState(null);
  const [riskScore, setRiskScore] = useState(null);
  const [recentNotifs, setRecentNotifs] = useState([]);

  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

  useEffect(() => {
    // Health check
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then((d) => setApiOk(d.status === 'ok' || d.status === 'healthy'))
      .catch(() => setApiOk(false));

    // Org summary (risk score)
    api.get('/organizations/summary')
      .then((s) => setRiskScore(s?.risk_score ?? 0))
      .catch(() => setRiskScore(0));

    // Recent notifications for activity feed
    api.get('/notifications/?limit=8')
      .then((data) => setRecentNotifs(data?.items ?? []))
      .catch(() => {});

    // Module stats
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
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">Panoramica della tua postura di sicurezza</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className={`w-2 h-2 rounded-full ${apiOk === null ? 'bg-yellow-400 animate-pulse' : apiOk ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-gray-400">
            API {apiOk === null ? 'checking...' : apiOk ? 'online' : 'offline'}
          </span>
        </div>
      </div>

      {/* Risk score + Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <div className="lg:col-span-1">
          {riskScore !== null ? (
            <RiskGauge score={riskScore} />
          ) : (
            <div className="bg-corvin-800 border border-corvin-700 rounded-xl p-5 h-full flex items-center justify-center">
              <div className="animate-spin h-5 w-5 border-2 border-corvin-accent border-t-transparent rounded-full" />
            </div>
          )}
        </div>
        <div className="lg:col-span-2 grid grid-cols-2 gap-4">
          <StatCard label="Email monitorate" value={stats.emails} to="/breach" />
          <StatCard label="Domini tracciati" value={stats.domains} to="/domain" />
          <StatCard label="Notifiche non lette" value={stats.unread} accent={stats.unread > 0} to="/notifications" />
          <StatCard label="File malevoli" value={stats.threats} accent={stats.threats > 0} to="/sandbox" />
        </div>
      </div>

      {/* Recent activity */}
      <div className="mb-10">
        <RecentActivity items={recentNotifs} />
      </div>

      {/* Module grid */}
      <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">Moduli</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {MODULE_CARDS.map(({ to, label, desc, icon }) => (
          <Link
            key={to}
            to={to}
            className="bg-corvin-800 border border-corvin-700 rounded-xl p-5 hover:border-corvin-accent transition-colors group"
          >
            <div className="flex items-start gap-3">
              <span className="text-2xl text-corvin-accent">{icon}</span>
              <div>
                <h3 className="font-semibold text-white group-hover:text-corvin-accent transition-colors">
                  {label}
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
