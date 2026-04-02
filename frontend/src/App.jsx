import { useState, useEffect } from 'react';

const MODULE_CARDS = [
  { id: 'email', label: 'Email Protection', desc: 'Phishing, DMARC, attachment scanning' },
  { id: 'breach', label: 'Breach Monitor', desc: 'HIBP integration with k-anonymity' },
  { id: 'domain', label: 'Domain Reputation', desc: 'DNS health, DNSBL, SSL monitoring' },
  { id: 'scanner', label: 'Web Scanner', desc: 'Passive vulnerability detection' },
  { id: 'sandbox', label: 'File Sandbox', desc: 'YARA rules, static analysis' },
  { id: 'notifications', label: 'Notifications', desc: 'Smart severity-based alerting' },
];

function StatusDot({ status }) {
  const colors = {
    online: 'bg-green-400',
    offline: 'bg-red-400',
    checking: 'bg-yellow-400 animate-pulse',
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status] ?? colors.checking}`} />;
}

export default function App() {
  const [apiStatus, setApiStatus] = useState('checking');

  useEffect(() => {
    fetch('/api/v1/health')
      .then((res) => res.json())
      .then((data) => setApiStatus(data.status === 'ok' ? 'online' : 'offline'))
      .catch(() => setApiStatus('offline'));
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-5xl font-bold tracking-tight mb-2">
          <span className="text-corvin-accent">Corvin</span>
        </h1>
        <p className="text-gray-400 text-lg">Silent guardian for your digital perimeter.</p>
        <div className="mt-4 inline-flex items-center gap-2 text-sm text-gray-500">
          <StatusDot status={apiStatus} />
          <span>API: <span className={apiStatus === 'online' ? 'text-green-400' : 'text-red-400'}>{apiStatus}</span></span>
        </div>
      </div>

      {/* Module grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 w-full max-w-4xl">
        {MODULE_CARDS.map((mod) => (
          <div
            key={mod.id}
            className="bg-corvin-800 border border-corvin-700 rounded-xl p-5 hover:border-corvin-accent transition-colors cursor-default"
          >
            <h3 className="font-semibold text-white mb-1">{mod.label}</h3>
            <p className="text-sm text-gray-400">{mod.desc}</p>
          </div>
        ))}
      </div>

      <p className="mt-12 text-xs text-corvin-600">
        Dashboard coming soon — backend API at{' '}
        <a href="/docs" className="text-corvin-accent hover:underline">/docs</a>
      </p>
    </div>
  );
}
