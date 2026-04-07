import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { notifications as notifApi } from '../api/notifications';
import { useSettings } from '../context/SettingsContext';
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
      'Ogni notifica ha una <strong>severity</strong> (info / basso / medio / alto / critico) e un modulo sorgente.',
      'Clicca <strong>✓ Letta</strong> per marcare una singola notifica come letta.',
      'Usa <strong>Segna tutte come lette</strong> per azzerare il badge del counter.',
    ],
  },
  {
    heading: 'Tab Webhook',
    items: [
      'Aggiungi un endpoint URL per ricevere notifiche in tempo reale via HTTP POST.',
      'Il payload JSON include: evento, severity, modulo, timestamp.',
      'Imposta un <strong>Secret HMAC</strong> per verificare l\'autenticità delle richieste (header <code class="text-blue-600">X-Corvin-Signature</code>).',
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
];

function Tab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
        active ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
      }`}
    >
      {label}
    </button>
  );
}

export default function Notifications() {
  const { t } = useSettings();
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
      await notifApi.addWebhook({ url: whForm.url, secret: whForm.secret || undefined, events: whForm.events });
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
      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} title="Notifications — Guida" sections={INFO_SECTIONS} />

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('notif.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('notif.subtitle')}</p>
        </div>
        <button onClick={() => setShowInfo(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>
          {t('common.guide')}
        </button>
      </div>

      <div className="flex border-b border-corvin-200 mb-6 gap-1">
        <Tab
          label={data?.unread > 0 ? t('notif.tabNotifUnread', { count: data.unread }) : t('notif.tabNotif')}
          active={tab === 'notifications'}
          onClick={() => setTab('notifications')}
        />
        <Tab label={t('notif.tabWebhook')} active={tab === 'webhooks'} onClick={() => setTab('webhooks')} />
      </div>

      {tab === 'notifications' && (
        <div>
          {data?.unread > 0 && (
            <div className="flex justify-end mb-4">
              <button onClick={handleMarkAll} className="text-xs text-blue-600 hover:text-blue-800 font-medium">
                {t('notif.markAll')}
              </button>
            </div>
          )}

          {loading && <LoadingSpinner />}
          {error && <p className="text-red-600 text-sm">{error}</p>}

          {!loading && data?.items?.length === 0 && (
            <EmptyState title={t('notif.emptyTitle')} description={t('notif.emptyDesc')} />
          )}

          {!loading && data?.items?.length > 0 && (
            <div className="space-y-2">
              {data.items.map((n) => (
                <div
                  key={n.id}
                  className={`bg-white rounded-xl shadow-card border p-4 transition-opacity ${
                    n.is_read ? 'border-corvin-200 opacity-60' : 'border-corvin-200'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1.5">
                        <SeverityBadge value={n.severity} />
                        <span className="text-sm text-gray-900 font-semibold">{n.title}</span>
                        {!n.is_read && (
                          <span className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0" />
                        )}
                      </div>
                      <p className="text-sm text-gray-600">{n.message}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {n.source_module} · {new Date(n.created_at).toLocaleString('it-IT')}
                      </p>
                    </div>
                    {!n.is_read && (
                      <button
                        onClick={() => handleMarkRead(n.id)}
                        className="text-xs text-gray-400 hover:text-gray-700 flex-shrink-0 font-medium"
                      >
                        {t('notif.markRead')}
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
            <button onClick={() => setShowWhForm((v) => !v)} className={showWhForm ? 'btn-secondary' : 'btn-primary'}>
              {showWhForm ? t('common.cancel') : t('notif.addWebhook')}
            </button>
          </div>

          {showWhForm && (
            <form onSubmit={handleAddWebhook} className="bg-white rounded-xl shadow-card border border-corvin-200 p-4 mb-4 space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('notif.whUrl')}</label>
                <input
                  type="url"
                  value={whForm.url}
                  onChange={(e) => setWhForm((f) => ({ ...f, url: e.target.value }))}
                  required
                  placeholder="https://hooks.example.com/corvin"
                  className="form-input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('notif.whSecret')}</label>
                <input
                  type="password"
                  value={whForm.secret}
                  onChange={(e) => setWhForm((f) => ({ ...f, secret: e.target.value }))}
                  className="form-input"
                />
              </div>
              {whError && <p className="text-red-600 text-sm">{whError}</p>}
              <button type="submit" disabled={savingWh} className="btn-primary">
                {savingWh ? t('notif.whSaving') : t('notif.whSave')}
              </button>
            </form>
          )}

          {loadingW && <LoadingSpinner />}
          {!loadingW && webhooks?.length === 0 && (
            <EmptyState title={t('notif.whEmptyTitle')} description={t('notif.whEmptyDesc')} />
          )}
          {!loadingW && webhooks?.length > 0 && (
            <div className="bg-white rounded-xl shadow-card border border-corvin-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-corvin-200 bg-corvin-50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{t('notif.whUrl')}</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{t('notif.whEvents')}</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{t('notif.whStatus')}</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {webhooks.map((w) => (
                    <tr key={w.id} className="border-b border-corvin-100 hover:bg-corvin-50 transition-colors">
                      <td className="px-4 py-3 text-gray-900 font-mono text-xs truncate max-w-xs">{w.url}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{w.events?.join(', ')}</td>
                      <td className="px-4 py-3"><SeverityBadge value={w.is_active ? 'active' : 'inactive'} /></td>
                      <td className="px-4 py-3">
                        <div className="flex gap-3 justify-end">
                          <button onClick={() => handleTestWebhook(w.id)} className="text-xs text-blue-600 hover:underline font-medium">{t('notif.whTest')}</button>
                          <button onClick={() => notifApi.deleteWebhook(w.id).then(refetchW)} className="text-xs text-red-500 hover:underline font-medium">{t('common.remove')}</button>
                        </div>
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
