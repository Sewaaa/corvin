import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { notifications as notifApi } from '../api/notifications';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';
import InfoModal from '../components/InfoModal';

const INFO_SECTIONS = [
  {
    heading: 'Cos\'è',
    text: 'Notifications raccoglie gli alert generati da tutti i moduli (breach rilevata, scan completato, minaccia email, file malicious) e li presenta in un feed con severity. Supporta anche webhook con firma HMAC-SHA256 per integrazioni esterne.',
  },
  {
    heading: 'Tab Notifiche',
    items: [
      'Le notifiche arrivano automaticamente quando i moduli rilevano eventi.',
      'Ogni notifica ha una <strong>severity</strong> (info / low / medium / high / critical) e un modulo sorgente.',
      'Clicca <strong>✓ Letta</strong> per marcare una singola notifica come letta.',
      'Usa <strong>Segna tutte come lette</strong> per azzerare il badge del counter.',
    ],
  },
  {
    heading: 'Tab Webhook',
    items: [
      'Aggiungi un endpoint URL per ricevere notifiche in tempo reale via HTTP POST.',
      'Il payload JSON include: evento, severity, modulo, timestamp.',
      'Imposta un <strong>Secret HMAC</strong> per verificare l\'autenticità delle richieste (header <code class="text-yellow-300">X-Corvin-Signature</code>).',
      'Usa il tasto <strong>Test</strong> per inviare un evento di prova all\'endpoint.',
    ],
  },
  {
    heading: 'URL webhook di test gratuiti',
    items: [
      { label: 'webhook.site', value: 'https://webhook.site (genera un URL temporaneo istantaneo)' },
      { label: 'requestbin', value: 'https://requestbin.com' },
      { label: 'Pipedream', value: 'https://pipedream.com/requestbin' },
    ],
  },
  {
    heading: 'Come generare notifiche demo',
    items: [
      'Aggiungi una email in Breach Monitor → notifica generata se trovata in breach.',
      'Avvia uno scan Web Scanner → notifica al completamento con finding count.',
      'Carica un file in File Sandbox → notifica se risulta suspicious/malicious.',
    ],
  },
];

function Tab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        active ? 'border-corvin-accent text-white' : 'border-transparent text-gray-400 hover:text-white'
      }`}
    >
      {label}
    </button>
  );
}

export default function Notifications() {
  const [tab, setTab] = useState('notifications');
  const { data, loading, error, refetch } = useApi(() => notifApi.list());
  const { data: webhooks, loading: loadingW, refetch: refetchW } = useApi(() => notifApi.listWebhooks());
  const [whForm, setWhForm] = useState({ url: '', secret: '', events: ['*'] });
  const [showWhForm, setShowWhForm] = useState(false);
  const [savingWh, setSavingWh] = useState(false);
  const [whError, setWhError] = useState('');
  const [showInfo, setShowInfo] = useState(false);

  const handleMarkRead = async (id) => {
    try { await notifApi.markRead(id); refetch(); } catch {}
  };

  const handleMarkAll = async () => {
    try { await notifApi.markAllRead(); refetch(); } catch {}
  };

  const handleAddWebhook = async (e) => {
    e.preventDefault();
    setWhError('');
    setSavingWh(true);
    try {
      await notifApi.addWebhook({
        url: whForm.url,
        secret: whForm.secret || undefined,
        events: whForm.events,
      });
      setShowWhForm(false);
      setWhForm({ url: '', secret: '', events: ['*'] });
      refetchW();
    } catch (err) {
      setWhError(err.message);
    } finally {
      setSavingWh(false);
    }
  };

  const handleTestWebhook = async (id) => {
    try { await notifApi.testWebhook(id); } catch {}
  };

  return (
    <div>
      <InfoModal
        open={showInfo}
        onClose={() => setShowInfo(false)}
        title="Notifications — Guida"
        sections={INFO_SECTIONS}
      />

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Notifications</h1>
          <p className="text-gray-400 text-sm mt-1">Alert in-app, email SMTP e webhook con firma HMAC-SHA256</p>
        </div>
        <button
          onClick={() => setShowInfo(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-corvin-accent border border-corvin-accent/30 rounded-lg hover:bg-corvin-accent/10 transition-colors"
        >
          <span>ⓘ</span> Info
        </button>
      </div>

      <div className="flex border-b border-corvin-700 mb-6 gap-1">
        <Tab
          label={`Notifiche${data?.unread ? ` · ${data.unread} non lette` : ''}`}
          active={tab === 'notifications'}
          onClick={() => setTab('notifications')}
        />
        <Tab label="Webhook" active={tab === 'webhooks'} onClick={() => setTab('webhooks')} />
      </div>

      {tab === 'notifications' && (
        <div>
          {data?.unread > 0 && (
            <div className="flex justify-end mb-4">
              <button
                onClick={handleMarkAll}
                className="text-xs text-corvin-accent hover:underline"
              >
                Segna tutte come lette
              </button>
            </div>
          )}

          {loading && <LoadingSpinner />}
          {error && <p className="text-red-400 text-sm">{error}</p>}

          {!loading && data?.items?.length === 0 && (
            <EmptyState title="Nessuna notifica" description="Le notifiche appariranno qui quando i moduli rilevano eventi." />
          )}

          {!loading && data?.items?.length > 0 && (
            <div className="space-y-2">
              {data.items.map((n) => (
                <div
                  key={n.id}
                  className={`bg-corvin-800 border rounded-xl p-4 ${
                    n.is_read ? 'border-corvin-700/50 opacity-60' : 'border-corvin-700'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <SeverityBadge value={n.severity} />
                        <span className="text-sm text-white font-medium">{n.title}</span>
                        {!n.is_read && (
                          <span className="w-2 h-2 rounded-full bg-corvin-accent flex-shrink-0" />
                        )}
                      </div>
                      <p className="text-xs text-gray-400">{n.message}</p>
                      <p className="text-xs text-gray-600 mt-1">
                        {n.source_module} · {new Date(n.created_at).toLocaleString('it-IT')}
                      </p>
                    </div>
                    {!n.is_read && (
                      <button
                        onClick={() => handleMarkRead(n.id)}
                        className="text-xs text-gray-500 hover:text-white flex-shrink-0"
                      >
                        ✓ Letta
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'webhooks' && (
        <div>
          <div className="flex justify-end mb-4">
            <button
              onClick={() => setShowWhForm((v) => !v)}
              className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg"
            >
              {showWhForm ? '✕ Annulla' : '+ Aggiungi webhook'}
            </button>
          </div>

          {showWhForm && (
            <form onSubmit={handleAddWebhook} className="bg-corvin-800 border border-corvin-700 rounded-xl p-4 mb-4 space-y-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">URL</label>
                <input
                  type="url"
                  value={whForm.url}
                  onChange={(e) => setWhForm((f) => ({ ...f, url: e.target.value }))}
                  required
                  placeholder="https://hooks.example.com/corvin"
                  className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Secret HMAC (opzionale)</label>
                <input
                  type="password"
                  value={whForm.secret}
                  onChange={(e) => setWhForm((f) => ({ ...f, secret: e.target.value }))}
                  className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent"
                />
              </div>
              {whError && <p className="text-red-400 text-sm">{whError}</p>}
              <button
                type="submit"
                disabled={savingWh}
                className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg disabled:opacity-50"
              >
                {savingWh ? 'Salvataggio…' : 'Salva webhook'}
              </button>
            </form>
          )}

          {loadingW && <LoadingSpinner />}
          {!loadingW && webhooks?.length === 0 && (
            <EmptyState title="Nessun webhook configurato" description="Aggiungi un endpoint per ricevere notifiche in tempo reale." />
          )}
          {!loadingW && webhooks?.length > 0 && (
            <div className="bg-corvin-800 border border-corvin-700 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-corvin-700 text-gray-400 text-xs uppercase">
                    <th className="text-left px-4 py-3">URL</th>
                    <th className="text-left px-4 py-3">Eventi</th>
                    <th className="text-left px-4 py-3">Stato</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {webhooks.map((w) => (
                    <tr key={w.id} className="border-b border-corvin-700/50 hover:bg-corvin-700/30">
                      <td className="px-4 py-3 text-white font-mono text-xs truncate max-w-xs">{w.url}</td>
                      <td className="px-4 py-3 text-gray-400 text-xs">{w.events?.join(', ')}</td>
                      <td className="px-4 py-3">
                        <SeverityBadge value={w.is_active ? 'active' : 'inactive'} />
                      </td>
                      <td className="px-4 py-3 flex gap-2 justify-end">
                        <button
                          onClick={() => handleTestWebhook(w.id)}
                          className="text-xs text-corvin-accent hover:underline"
                        >
                          Test
                        </button>
                        <button
                          onClick={() => notifApi.deleteWebhook(w.id).then(refetchW)}
                          className="text-xs text-red-400 hover:underline"
                        >
                          Rimuovi
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
