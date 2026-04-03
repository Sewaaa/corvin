import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StatCard from '../components/StatCard';
import { breach } from '../api/breach';
import { domain } from '../api/domain';
import { notifications } from '../api/notifications';
import { sandbox } from '../api/sandbox';

const MODULE_CARDS = [
  { to: '/breach',        label: 'Breach Monitor',    desc: 'Monitoraggio HIBP con k-anonymity',    icon: '⚠' },
  { to: '/domain',        label: 'Domain Reputation', desc: 'DNS, DNSBL, SSL, WHOIS analysis',      icon: '◈' },
  { to: '/web-scan',      label: 'Web Scanner',       desc: 'Scansione passiva di vulnerabilità',   icon: '⊕' },
  { to: '/email',         label: 'Email Protection',  desc: 'Phishing, DMARC, spoofing detection',  icon: '✉' },
  { to: '/sandbox',       label: 'File Sandbox',      desc: 'YARA rules, VirusTotal, analisi PE',   icon: '⧫' },
  { to: '/notifications', label: 'Notifications',     desc: 'Alert severity-based, webhook',        icon: '◉' },
];

export default function Dashboard() {
  const [stats, setStats] = useState({ emails: 0, domains: 0, unread: 0, threats: 0 });
  const [apiOk, setApiOk] = useState(null);

  useEffect(() => {
    fetch('/api/v1/health')
      .then((r) => r.json())
      .then((d) => setApiOk(d.status === 'ok' || d.status === 'healthy'))
      .catch(() => setApiOk(false));

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
            API {apiOk === null ? 'checking…' : apiOk ? 'online' : 'offline'}
          </span>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        <StatCard label="Email monitorate" value={stats.emails} />
        <StatCard label="Domini tracciati" value={stats.domains} />
        <StatCard label="Notifiche non lette" value={stats.unread} accent={stats.unread > 0} />
        <StatCard label="File malicious" value={stats.threats} accent={stats.threats > 0} />
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
