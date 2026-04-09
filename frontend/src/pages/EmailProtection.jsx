import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { email as emailApi } from '../api/email';
import { useSettings } from '../context/SettingsContext';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';
import InfoModal from '../components/InfoModal';

const INFO_SECTIONS = [
  {
    heading: 'Cos\'è',
    text: 'Email Protection connette account IMAP e analizza le email ricevute alla ricerca di phishing, spoofing e anomalie SPF/DKIM/DMARC. Le password sono cifrate con Fernet e non vengono mai esposte.',
  },
  {
    heading: 'Come si usa',
    items: [
      'Clicca <strong>+ Aggiungi account</strong> e inserisci le credenziali IMAP.',
      'La connessione IMAP viene testata prima del salvataggio: se fallisce nulla viene salvato.',
      'Clicca <strong>▶ Avvia scan</strong> per analizzare le ultime email della inbox.',
      'Se vengono rilevate minacce, compare il bottone <strong>▼ Vedi minacce</strong> con il conteggio.',
      'Dal pannello minacce puoi <strong>mettere in quarantena</strong> o <strong>rilasciare</strong> una email.',
    ],
  },
  {
    heading: 'Setup Gmail (test rapido)',
    items: [
      { label: 'IMAP Host', value: 'imap.gmail.com' },
      { label: 'Porta', value: '993' },
      { label: 'SSL', value: 'abilitato' },
      { label: 'Password', value: 'usa un\'App Password (non la password Google)' },
      { label: 'Come ottenere App Password', value: 'myaccount.google.com → Sicurezza → Verifica in 2 passaggi → App Password' },
    ],
  },
  {
    heading: 'Altri provider',
    items: [
      { label: 'Outlook / Office 365', value: 'outlook.office365.com : 993' },
      { label: 'Yahoo Mail', value: 'imap.mail.yahoo.com : 993' },
      { label: 'Provider generico', value: 'chiedi all\'admin il server IMAP e la porta' },
    ],
  },
];

function ThreatPanel({ emailAddress, onClose }) {
  const { t } = useSettings();
  const { data, loading, error, refetch } = useApi(
    () => emailApi.listThreatsByAccount(emailAddress),
    [emailAddress],
  );
  const [actionError, setActionError] = useState('');

  const handleAction = async (id, action) => {
    setActionError('');
    try {
      await emailApi.updateThreat(id, action);
      refetch();
    } catch (err) {
      setActionError(err.message ?? 'Errore durante l\'operazione.');
    }
  };

  const threats = data?.items ?? [];

  return (
    <div className="border-t border-corvin-100 mt-3 pt-3">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">{t('email.threatPanel')}</span>
        <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-700 font-medium">{t('email.threatClose')}</button>
      </div>

      {actionError && <p className="text-red-600 text-xs mb-2">⚠ {actionError}</p>}
      {loading && <p className="text-xs text-gray-500 py-2">Caricamento…</p>}
      {error && <p className="text-red-600 text-xs py-2">{error}</p>}

      {!loading && threats.length === 0 && (
        <p className="text-sm text-gray-500 py-2">{t('email.threatEmpty')}</p>
      )}

      {!loading && threats.length > 0 && (
        <div className="divide-y divide-corvin-100">
          {threats.map((th) => {
            const authFail = [
              th.spf_result !== 'pass' && th.spf_result ? `SPF: ${th.spf_result}` : null,
              th.dkim_result !== 'pass' && th.dkim_result ? `DKIM: ${th.dkim_result}` : null,
              th.dmarc_result !== 'pass' && th.dmarc_result ? `DMARC: ${th.dmarc_result}` : null,
            ].filter(Boolean);

            return (
              <div key={th.id} className="py-2.5 flex items-center gap-3">
                <SeverityBadge value={th.severity} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-gray-700">{th.threat_type}</span>
                  </div>
                  <p className="text-xs text-gray-400 truncate mt-0.5">
                    {th.sender}
                    {th.subject && <span className="text-gray-300"> · </span>}
                    {th.subject && <span className="italic">{th.subject}</span>}
                  </p>
                  {authFail.length > 0 && (
                    <p className="text-xs text-red-500 mt-0.5">{authFail.join(' · ')}</p>
                  )}
                </div>
                <div className="shrink-0">
                  {!th.is_quarantined && (
                    <button
                      onClick={() => handleAction(th.id, 'quarantine')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-600 text-white hover:bg-red-700 active:bg-red-800 shadow-sm transition-colors cursor-pointer"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z"/></svg>
                      {t('email.quarantine')}
                    </button>
                  )}
                  {th.is_quarantined && (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-gray-100 text-gray-500 border border-gray-200">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/></svg>
                      {t('email.quarantined')}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AccountCard({ account, onScan, onRemove, scanning, removing, isViewer }) {
  const { t } = useSettings();
  const [showThreats, setShowThreats] = useState(false);

  return (
    <div className={`bg-white rounded-xl shadow-card border transition-colors px-4 py-3 ${showThreats ? 'border-blue-300' : 'border-corvin-200'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-gray-900 font-semibold truncate">{account.email_address}</p>
          <p className="text-xs text-gray-400 mt-0.5">{account.imap_host}:{account.imap_port}</p>
        </div>
        {account.threats_count > 0 ? (
          <span className="text-xs font-semibold text-red-700 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full shrink-0">
            {t('email.threats', { count: account.threats_count })}
          </span>
        ) : (
          <span className="text-xs text-green-600 font-medium shrink-0">{t('email.noThreats')}</span>
        )}
      </div>

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-corvin-100 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          {account.last_scan_status
            ? <SeverityBadge value={account.last_scan_status === 'ok' ? 'safe' : 'failed'} />
            : <span className="text-xs text-gray-400">{t('email.neverScanned')}</span>}
          {account.last_scanned_at && (
            <span className="text-xs text-gray-400">
              {new Date(account.last_scanned_at).toLocaleString('it-IT')}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {account.threats_count > 0 && (
            <button
              onClick={() => setShowThreats((v) => !v)}
              className={`px-3 py-1 text-xs font-medium rounded-lg border transition-colors ${
                showThreats
                  ? 'bg-blue-50 text-blue-700 border-blue-200'
                  : 'bg-white text-gray-600 border-corvin-200 hover:border-blue-300 hover:text-blue-700'
              }`}
            >
              {showThreats ? t('email.hideThreats') : t('email.showThreats', { count: account.threats_count })}
            </button>
          )}

          {!isViewer && (
            <button
              onClick={() => onScan(account.id)}
              disabled={scanning}
              className="px-3 py-1 text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-100 disabled:opacity-50 transition-colors"
            >
              {scanning ? t('email.scanning') : t('email.startScan')}
            </button>
          )}

          {!isViewer && (
            <button
              onClick={() => onRemove(account.id)}
              disabled={removing}
              className="text-xs text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
            >
              {removing ? '…' : '✕'}
            </button>
          )}
        </div>
      </div>

      {showThreats && (
        <ThreatPanel emailAddress={account.email_address} onClose={() => setShowThreats(false)} />
      )}
    </div>
  );
}

export default function EmailProtection() {
  const { t } = useSettings();
  const { user } = useAuth();
  const isViewer = user?.role === 'viewer';
  const { data: accounts, loading, refetch } = useApi(() => emailApi.listAccounts());
  const [form, setForm] = useState({ email_address: '', imap_host: '', imap_port: 993, password: '', use_ssl: true });
  const [showForm, setShowForm] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [scanningId, setScanningId] = useState(null);
  const [removingId, setRemovingId] = useState(null);
  const [pageError, setPageError] = useState('');

  const set = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  const handleAdd = async (e) => {
    e.preventDefault();
    setSaveError('');
    setSaving(true);
    try {
      await emailApi.addAccount({ ...form, imap_port: Number(form.imap_port) });
      setShowForm(false);
      setForm({ email_address: '', imap_host: '', imap_port: 993, password: '', use_ssl: true });
      refetch();
    } catch (err) {
      const msg = err.message ?? '';
      if (msg.includes('IMAP') || msg.includes('connettersi')) {
        setSaveError(t('email.imapFail'));
      } else if (msg.includes('già monitorato')) {
        setSaveError(t('email.duplicate'));
      } else {
        setSaveError(msg || t('email.saveError'));
      }
    } finally {
      setSaving(false);
    }
  };

  const handleScan = async (id) => {
    setScanningId(id);
    setPageError('');
    try {
      await emailApi.triggerScan(id);
      await new Promise((r) => setTimeout(r, 3000));
      await refetch();
    } catch (err) {
      setPageError(err.message ?? t('email.scanError'));
    } finally {
      setScanningId(null);
    }
  };

  const handleRemove = async (id) => {
    if (!window.confirm(t('email.removeConfirm'))) return;
    setRemovingId(id);
    setPageError('');
    try {
      await emailApi.deleteAccount(id);
      await refetch();
    } catch (err) {
      setPageError(err.message ?? t('email.removeError'));
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <div>
      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} title="Email Protection — Guida" sections={INFO_SECTIONS} />

      <div className="flex items-start justify-between flex-wrap gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('email.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('email.subtitle')}</p>
        </div>
        <button onClick={() => setShowInfo(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>
          {t('common.guide')}
        </button>
      </div>

      {pageError && <p className="text-red-600 text-sm mb-4">⚠ {pageError}</p>}

      {!isViewer && (
        <div className="flex justify-end mb-4">
          <button onClick={() => { setShowForm((v) => !v); setSaveError(''); }} className={showForm ? 'btn-secondary' : 'btn-primary'}>
            {showForm ? t('email.cancelBtn') : t('email.addBtn')}
          </button>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleAdd} className="bg-white rounded-xl shadow-card border border-corvin-200 p-4 mb-4 space-y-3">
          <div className="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 text-xs text-blue-700 space-y-0.5">
            <p>• <strong>Gmail</strong>: host <code>imap.gmail.com</code>, porta 993 — usa un'<strong>App Password</strong></p>
            <p>• <strong>Outlook</strong>: host <code>outlook.office365.com</code>, porta 993</p>
            <p>• <strong>Yahoo</strong>: host <code>imap.mail.yahoo.com</code>, porta 993</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label={t('email.fieldEmail')} type="email" value={form.email_address} onChange={set('email_address')} required />
            <Field label={t('email.fieldPassword')} type="password" value={form.password} onChange={set('password')} required />
            <Field label={t('email.fieldHost')} value={form.imap_host} onChange={set('imap_host')} placeholder="imap.gmail.com" required />
            <Field label={t('email.fieldPort')} type="number" value={form.imap_port} onChange={set('imap_port')} />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input type="checkbox" checked={form.use_ssl} onChange={set('use_ssl')} className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            {t('email.fieldSsl')}
          </label>
          {saveError && <p className="text-red-600 text-sm">{saveError}</p>}
          <div className="flex items-center gap-3">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? t('email.saving') : t('email.saveBtn')}
            </button>
            <p className="text-xs text-gray-400">{t('email.saveHint')}</p>
          </div>
        </form>
      )}

      {loading && <LoadingSpinner />}
      {!loading && (accounts ?? []).length === 0 && (
        <EmptyState title={t('email.emptyTitle')} description={t('email.emptyDesc')} />
      )}
      {!loading && (accounts ?? []).length > 0 && (
        <div className="space-y-3">
          {accounts.map((a) => (
            <AccountCard
              key={a.id}
              account={a}
              onScan={handleScan}
              onRemove={handleRemove}
              scanning={scanningId === a.id}
              removing={removingId === a.id}
              isViewer={isViewer}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Field({ label, type = 'text', value, onChange, required, placeholder }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        placeholder={placeholder}
        className="form-input"
      />
    </div>
  );
}
