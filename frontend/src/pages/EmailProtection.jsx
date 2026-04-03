import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { email as emailApi } from '../api/email';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';

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

export default function EmailProtection() {
  const [tab, setTab] = useState('accounts');
  const { data: accounts, loading: loadingA, refetch: refetchA } = useApi(() => emailApi.listAccounts());
  const { data: threatsData, loading: loadingT, refetch: refetchT } = useApi(() => emailApi.listThreats());
  const [form, setForm] = useState({ email_address: '', imap_host: '', imap_port: 993, password: '', use_ssl: true });
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  const handleAdd = async (e) => {
    e.preventDefault();
    setSaveError('');
    setSaving(true);
    try {
      await emailApi.addAccount({ ...form, imap_port: Number(form.imap_port) });
      setShowForm(false);
      setForm({ email_address: '', imap_host: '', imap_port: 993, password: '', use_ssl: true });
      refetchA();
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (id, action) => {
    try {
      await emailApi.updateThreat(id, action);
      refetchT();
    } catch {}
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Email Protection</h1>
        <p className="text-gray-400 text-sm mt-1">IMAP scan, phishing detection, SPF/DKIM/DMARC analysis</p>
      </div>

      <div className="flex border-b border-corvin-700 mb-6 gap-1">
        <Tab label="Account IMAP" active={tab === 'accounts'} onClick={() => setTab('accounts')} />
        <Tab
          label={`Minacce${threatsData?.total ? ` (${threatsData.total})` : ''}`}
          active={tab === 'threats'}
          onClick={() => setTab('threats')}
        />
      </div>

      {tab === 'accounts' && (
        <div>
          <div className="flex justify-end mb-4">
            <button
              onClick={() => setShowForm((v) => !v)}
              className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg"
            >
              {showForm ? '✕ Annulla' : '+ Aggiungi account'}
            </button>
          </div>

          {showForm && (
            <form onSubmit={handleAdd} className="bg-corvin-800 border border-corvin-700 rounded-xl p-4 mb-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Email" type="email" value={form.email_address} onChange={set('email_address')} required />
                <Field label="Password IMAP" type="password" value={form.password} onChange={set('password')} required />
                <Field label="IMAP Host" value={form.imap_host} onChange={set('imap_host')} required />
                <Field label="Porta" type="number" value={form.imap_port} onChange={set('imap_port')} />
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input type="checkbox" checked={form.use_ssl} onChange={set('use_ssl')} className="rounded" />
                Usa SSL
              </label>
              {saveError && <p className="text-red-400 text-sm">{saveError}</p>}
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg disabled:opacity-50"
              >
                {saving ? 'Test connessione…' : 'Salva account'}
              </button>
            </form>
          )}

          {loadingA && <LoadingSpinner />}
          {!loadingA && accounts?.length === 0 && (
            <EmptyState title="Nessun account IMAP" description="Aggiungi un account per avviare il monitoraggio email." />
          )}
          {!loadingA && accounts?.length > 0 && (
            <div className="bg-corvin-800 border border-corvin-700 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-corvin-700 text-gray-400 text-xs uppercase">
                    <th className="text-left px-4 py-3">Email</th>
                    <th className="text-left px-4 py-3">Host</th>
                    <th className="text-left px-4 py-3">Stato</th>
                    <th className="text-left px-4 py-3">Minacce</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((a) => (
                    <tr key={a.id} className="border-b border-corvin-700/50 hover:bg-corvin-700/30">
                      <td className="px-4 py-3 text-white">{a.email_address}</td>
                      <td className="px-4 py-3 text-gray-400">{a.imap_host}:{a.imap_port}</td>
                      <td className="px-4 py-3">
                        <SeverityBadge value={a.last_scan_status ?? 'mai'} />
                      </td>
                      <td className="px-4 py-3 text-white">{a.threats_count}</td>
                      <td className="px-4 py-3 flex gap-2 justify-end">
                        <button
                          onClick={() => emailApi.triggerScan(a.id).then(refetchA)}
                          className="text-xs text-corvin-accent hover:underline"
                        >
                          Scan
                        </button>
                        <button
                          onClick={() => emailApi.deleteAccount(a.id).then(refetchA)}
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

      {tab === 'threats' && (
        <div>
          {loadingT && <LoadingSpinner />}
          {!loadingT && (threatsData?.items?.length ?? 0) === 0 && (
            <EmptyState title="Nessuna minaccia rilevata" description="Il monitoraggio è attivo." />
          )}
          {!loadingT && threatsData?.items?.length > 0 && (
            <div className="space-y-2">
              {threatsData.items.map((t) => (
                <div key={t.id} className="bg-corvin-800 border border-corvin-700 rounded-xl p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <SeverityBadge value={t.severity} />
                        <span className="text-sm text-white font-medium">{t.threat_type}</span>
                        {t.is_quarantined && <SeverityBadge value="quarantined" />}
                      </div>
                      <p className="text-xs text-gray-400 truncate">Da: {t.sender}</p>
                      {t.subject && <p className="text-xs text-gray-500 truncate">Oggetto: {t.subject}</p>}
                      <div className="flex gap-3 mt-1 text-xs text-gray-500">
                        {t.spf_result && <span>SPF: {t.spf_result}</span>}
                        {t.dkim_result && <span>DKIM: {t.dkim_result}</span>}
                        {t.dmarc_result && <span>DMARC: {t.dmarc_result}</span>}
                      </div>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      {!t.is_quarantined && (
                        <button
                          onClick={() => handleAction(t.id, 'quarantine')}
                          className="text-xs text-yellow-400 hover:underline"
                        >
                          Quarantena
                        </button>
                      )}
                      {t.is_quarantined && (
                        <button
                          onClick={() => handleAction(t.id, 'release')}
                          className="text-xs text-green-400 hover:underline"
                        >
                          Rilascia
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Field({ label, type = 'text', value, onChange, required }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent"
      />
    </div>
  );
}
