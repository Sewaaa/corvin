import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { email as emailApi } from '../api/email';
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
  {
    heading: 'Cosa rileva',
    items: [
      'Phishing: link sospetti, domini typosquatting, urgency language.',
      'Spoofing: From != MAIL FROM, SPF/DKIM/DMARC fail.',
      'Malware hint: allegati .exe, .js, .bat, script inline.',
      'Ogni minaccia ha severity: low / medium / high / critical.',
    ],
  },
];

// ── Pannello minacce di un singolo account ────────────────────────────────────
function ThreatPanel({ emailAddress, onClose }) {
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
    <div className="border-t border-corvin-700 mt-3 pt-3">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Minacce rilevate
        </span>
        <button onClick={onClose} className="text-xs text-gray-500 hover:text-white">✕ Chiudi</button>
      </div>

      {actionError && <p className="text-red-400 text-xs mb-2">⚠ {actionError}</p>}
      {loading && <p className="text-xs text-gray-500 py-2">Caricamento…</p>}
      {error && <p className="text-red-400 text-xs py-2">{error}</p>}

      {!loading && threats.length === 0 && (
        <p className="text-xs text-gray-500 py-2">Nessuna minaccia trovata per questo account.</p>
      )}

      {!loading && threats.length > 0 && (
        <div className="space-y-2">
          {threats.map((t) => (
            <div key={t.id} className="bg-corvin-700/40 rounded-lg px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <SeverityBadge value={t.severity} />
                    <span className="text-xs text-white font-medium">{t.threat_type}</span>
                    {t.is_quarantined && (
                      <span className="text-xs bg-yellow-900/50 text-yellow-400 px-2 py-0.5 rounded-full">quarantena</span>
                    )}
                    {t.is_released && (
                      <span className="text-xs bg-green-900/50 text-green-400 px-2 py-0.5 rounded-full">rilasciata</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 truncate">Da: {t.sender}</p>
                  {t.subject && <p className="text-xs text-gray-500 truncate">Oggetto: {t.subject}</p>}
                  {t.detection_reasons?.length > 0 && (
                    <p className="text-xs text-gray-600 mt-0.5">↳ {t.detection_reasons.join(', ')}</p>
                  )}
                  <div className="flex gap-3 mt-1 text-xs">
                    {t.spf_result && (
                      <span className={t.spf_result === 'pass' ? 'text-green-500' : 'text-red-400'}>
                        SPF: {t.spf_result}
                      </span>
                    )}
                    {t.dkim_result && (
                      <span className={t.dkim_result === 'pass' ? 'text-green-500' : 'text-red-400'}>
                        DKIM: {t.dkim_result}
                      </span>
                    )}
                    {t.dmarc_result && (
                      <span className={t.dmarc_result === 'pass' ? 'text-green-500' : 'text-red-400'}>
                        DMARC: {t.dmarc_result}
                      </span>
                    )}
                  </div>
                </div>
                <div className="shrink-0">
                  {!t.is_quarantined && !t.is_released && (
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
  );
}

// ── Card singolo account ──────────────────────────────────────────────────────
function AccountCard({ account, onScan, onRemove, scanning, removing }) {
  const [showThreats, setShowThreats] = useState(false);

  return (
    <div className={`bg-corvin-800 border rounded-xl px-4 py-3 transition-colors ${
      showThreats ? 'border-corvin-accent/40' : 'border-corvin-700'
    }`}>
      {/* Riga principale */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-white font-medium truncate">{account.email_address}</p>
          <p className="text-xs text-gray-500 mt-0.5">{account.imap_host}:{account.imap_port}</p>
        </div>
        {account.threats_count > 0 ? (
          <span className="text-xs font-semibold text-red-400 bg-red-900/30 px-2 py-0.5 rounded-full shrink-0">
            {account.threats_count} minacce
          </span>
        ) : (
          <span className="text-xs text-green-500 shrink-0">✓ nessuna minaccia</span>
        )}
      </div>

      {/* Riga secondaria: stato scan + azioni */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-corvin-700/50 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          {account.last_scan_status
            ? <SeverityBadge value={account.last_scan_status === 'ok' ? 'safe' : 'failed'} />
            : <span className="text-xs text-gray-500">Mai scansionato</span>}
          {account.last_scanned_at && (
            <span className="text-xs text-gray-600">
              {new Date(account.last_scanned_at).toLocaleString('it-IT')}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Vedi minacce — visibile solo se ce ne sono */}
          {account.threats_count > 0 && (
            <button
              onClick={() => setShowThreats((v) => !v)}
              className={`px-3 py-1 text-xs font-medium rounded-lg border transition-colors ${
                showThreats
                  ? 'bg-corvin-accent/20 text-corvin-accent border-corvin-accent/40'
                  : 'bg-transparent text-gray-300 border-corvin-700 hover:border-corvin-accent/40 hover:text-corvin-accent'
              }`}
            >
              {showThreats ? '▲ Nascondi minacce' : `▼ Vedi minacce (${account.threats_count})`}
            </button>
          )}

          <button
            onClick={() => onScan(account.id)}
            disabled={scanning}
            className="px-3 py-1 text-xs font-medium bg-corvin-accent/20 text-corvin-accent border border-corvin-accent/30 rounded-lg hover:bg-corvin-accent/30 disabled:opacity-50 transition-colors"
          >
            {scanning ? '⟳ Scan in corso…' : '▶ Avvia scan'}
          </button>

          <button
            onClick={() => onRemove(account.id)}
            disabled={removing}
            className="text-xs text-gray-500 hover:text-red-400 transition-colors disabled:opacity-50"
          >
            {removing ? '…' : '✕'}
          </button>
        </div>
      </div>

      {/* Pannello minacce inline */}
      {showThreats && (
        <ThreatPanel
          emailAddress={account.email_address}
          onClose={() => setShowThreats(false)}
        />
      )}
    </div>
  );
}

// ── Pagina principale ─────────────────────────────────────────────────────────
export default function EmailProtection() {
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
        setSaveError('Impossibile connettersi al server IMAP. Controlla host, porta e credenziali.');
      } else if (msg.includes('già monitorato')) {
        setSaveError('Questo account è già nella lista.');
      } else {
        setSaveError(msg || 'Errore durante il salvataggio. Riprova.');
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
      setPageError(err.message ?? 'Errore durante la scansione.');
    } finally {
      setScanningId(null);
    }
  };

  const handleRemove = async (id) => {
    if (!window.confirm('Rimuovere questo account? Verranno cancellate anche tutte le minacce associate.')) return;
    setRemovingId(id);
    setPageError('');
    try {
      await emailApi.deleteAccount(id);
      await refetch();
    } catch (err) {
      setPageError(err.message ?? 'Errore durante la rimozione.');
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <div>
      <InfoModal
        open={showInfo}
        onClose={() => setShowInfo(false)}
        title="Email Protection — Guida"
        sections={INFO_SECTIONS}
      />

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Email Protection</h1>
          <p className="text-gray-400 text-sm mt-1">IMAP scan, phishing detection, SPF/DKIM/DMARC analysis</p>
        </div>
        <button
          onClick={() => setShowInfo(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-corvin-accent border border-corvin-accent/30 rounded-lg hover:bg-corvin-accent/10 transition-colors"
        >
          <span>ⓘ</span> Info
        </button>
      </div>

      {pageError && <p className="text-red-400 text-sm mb-4">⚠ {pageError}</p>}

      {/* Bottone aggiungi */}
      <div className="flex justify-end mb-4">
        <button
          onClick={() => { setShowForm((v) => !v); setSaveError(''); }}
          className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg"
        >
          {showForm ? '✕ Annulla' : '+ Aggiungi account'}
        </button>
      </div>

      {/* Form aggiunta account */}
      {showForm && (
        <form onSubmit={handleAdd} className="bg-corvin-800 border border-corvin-700 rounded-xl p-4 mb-4 space-y-3">
          <div className="bg-corvin-700/40 rounded-lg px-3 py-2 text-xs text-gray-400 space-y-0.5">
            <p>• <strong className="text-gray-300">Gmail</strong>: host <code>imap.gmail.com</code>, porta 993 — usa un'<strong className="text-gray-300">App Password</strong></p>
            <p>• <strong className="text-gray-300">Outlook</strong>: host <code>outlook.office365.com</code>, porta 993</p>
            <p>• <strong className="text-gray-300">Yahoo</strong>: host <code>imap.mail.yahoo.com</code>, porta 993</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Email" type="email" value={form.email_address} onChange={set('email_address')} required />
            <Field label="Password IMAP / App Password" type="password" value={form.password} onChange={set('password')} required />
            <Field label="IMAP Host" value={form.imap_host} onChange={set('imap_host')} placeholder="imap.gmail.com" required />
            <Field label="Porta" type="number" value={form.imap_port} onChange={set('imap_port')} />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input type="checkbox" checked={form.use_ssl} onChange={set('use_ssl')} className="rounded" />
            Usa SSL (raccomandato)
          </label>
          {saveError && <p className="text-red-400 text-sm">{saveError}</p>}
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg disabled:opacity-50"
            >
              {saving ? 'Verifica connessione IMAP…' : 'Salva account'}
            </button>
            <p className="text-xs text-gray-500">La connessione IMAP viene testata prima del salvataggio.</p>
          </div>
        </form>
      )}

      {/* Lista account */}
      {loading && <LoadingSpinner />}
      {!loading && (accounts ?? []).length === 0 && (
        <EmptyState
          title="Nessun account IMAP"
          description="Aggiungi un account per avviare il monitoraggio email."
        />
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
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        placeholder={placeholder}
        className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent placeholder:text-gray-600"
      />
    </div>
  );
}
