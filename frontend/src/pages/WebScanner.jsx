import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { webScan } from '../api/webScan';
import { domain as domainApi } from '../api/domain';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';
import InfoModal from '../components/InfoModal';

const INFO_SECTIONS = [
  {
    heading: 'Cos\'è',
    text: 'Web Scanner esegue una scansione passiva del sito associato a un dominio verificato: analizza header HTTP, cookies, redirect HTTPS, presenza di CSP/HSTS e altre configurazioni di sicurezza. Nessun payload offensivo viene inviato.',
  },
  {
    heading: 'Come si usa',
    items: [
      'Aggiungi e <strong>verifica</strong> un dominio nella sezione Domain Reputation.',
      'Torna qui, seleziona il dominio verificato dal menu e clicca <strong>Avvia scan</strong>.',
      'La scansione gira in background: attendi il completamento (di solito 10–30 secondi).',
      'Clicca sulla riga completata per vedere i <strong>finding</strong> con severity.',
      'In caso di errore usa <strong>↺ Riprova</strong>; usa <strong>✕</strong> per eliminare una scansione.',
    ],
  },
  {
    heading: 'Dominio di test consigliato',
    items: [
      { label: 'Dominio pubblico', value: 'example.com (aggiungilo prima in Domain Reputation)' },
      { label: 'Finding attesi', value: 'CSP mancante, HSTS assente, header X-Frame-Options' },
    ],
  },
  {
    heading: 'Note tecniche',
    items: [
      'La scansione fa max 20 richieste HTTP GET passive.',
      'Controlla: redirect HTTP→HTTPS, HSTS, CSP, X-Content-Type-Options, X-Frame-Options, cookie Secure/HttpOnly.',
      'I finding hanno severity: info / basso / medio / alto / critico.',
    ],
  },
];

export default function WebScanner() {
  const { data: scans, loading, error, refetch } = useApi(() => webScan.list());
  const { data: domains } = useApi(() => domainApi.list());
  const [selectedDomain, setSelectedDomain] = useState('');
  const [frequency, setFrequency] = useState('manual');
  const [starting, setStarting] = useState(false);
  const [retryingId, setRetryingId] = useState(null);
  const [removingId, setRemovingId] = useState(null);
  const [startError, setStartError] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [showInfo, setShowInfo] = useState(false);

  const verifiedDomains = (domains ?? []).filter((d) => d.is_verified);

  const pollScanCompletion = async (scanId) => {
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      const updated = await refetch();
      const found = (updated ?? []).find((s) => s.id === scanId);
      if (found && found.status !== 'pending' && found.status !== 'running') break;
    }
  };

  const handleStart = async (e) => {
    e.preventDefault();
    if (!selectedDomain) return;
    setStartError('');
    setStarting(true);
    try {
      const newScan = await webScan.start(selectedDomain, frequency);
      refetch();
      if (newScan?.id) await pollScanCompletion(newScan.id);
    } catch (err) {
      setStartError(err.message ?? 'Errore durante l\'avvio della scansione. Riprova più tardi.');
    } finally {
      setStarting(false);
    }
  };

  const handleRetry = async (scan) => {
    setRetryingId(scan.id);
    setStartError('');
    try {
      await webScan.remove(scan.id);
      const newScan = await webScan.start(scan.domain_id);
      refetch();
      if (newScan?.id) await pollScanCompletion(newScan.id);
    } catch (err) {
      setStartError(err.message ?? 'Errore durante il nuovo tentativo.');
    } finally {
      setRetryingId(null);
    }
  };

  const handleRemove = async (e, scanId) => {
    e.stopPropagation();
    if (!window.confirm('Rimuovere questa scansione?')) return;
    setRemovingId(scanId);
    try {
      await webScan.remove(scanId);
      if (detail?.id === scanId) { setDetail(null); setDetailError(''); }
      await refetch();
    } catch (err) {
      setStartError(err.message ?? 'Errore durante la rimozione.');
    } finally {
      setRemovingId(null);
    }
  };

  const handleDetail = async (id) => {
    if (detail?.id === id) { setDetail(null); setDetailError(''); return; }
    setDetailError('');
    try {
      const d = await webScan.get(id);
      setDetail(d);
    } catch (err) {
      setDetailError(err.message ?? 'Errore nel caricamento dei dettagli.');
    }
  };

  const isOpen = (id) => detail?.id === id;

  return (
    <div>
      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} title="Web Scanner — Guida" sections={INFO_SECTIONS} />

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Web Scanner</h1>
          <p className="text-gray-500 text-sm mt-1">Scansione passiva — max 20 richieste, nessun payload intrusivo</p>
        </div>
        <button onClick={() => setShowInfo(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>
          Guida
        </button>
      </div>

      <form onSubmit={handleStart} className="flex flex-wrap gap-3 mb-6">
        <select value={selectedDomain} onChange={(e) => setSelectedDomain(e.target.value)} className="form-select flex-1 min-w-[200px]">
          <option value="">Seleziona un dominio verificato…</option>
          {verifiedDomains.map((d) => (
            <option key={d.id} value={d.id}>{d.domain}</option>
          ))}
        </select>
        <select value={frequency} onChange={(e) => setFrequency(e.target.value)} className="form-select">
          <option value="manual">Una tantum</option>
          <option value="daily">Giornaliera</option>
          <option value="weekly">Settimanale</option>
          <option value="monthly">Mensile</option>
        </select>
        <button type="submit" disabled={starting || !selectedDomain} className="btn-primary">
          {starting ? 'Avvio in corso…' : '▶ Avvia scan'}
        </button>
      </form>

      {startError && <p className="text-red-600 text-sm mb-4">{startError}</p>}
      {detailError && <p className="text-red-600 text-sm mb-4">⚠ {detailError}</p>}
      {loading && <LoadingSpinner />}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {!loading && scans?.length === 0 && (
        <EmptyState title="Nessuna scansione" description="Aggiungi e verifica un dominio, poi avvia la prima scansione." />
      )}

      {!loading && scans?.length > 0 && (
        <div className="space-y-2">
          {scans.map((s) => (
            <div key={s.id} className={`bg-white rounded-xl shadow-card border transition-colors ${isOpen(s.id) ? 'border-blue-300' : 'border-corvin-200'}`}>
              <div
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-corvin-50 rounded-xl"
                onClick={() => s.status === 'completed' && handleDetail(s.id)}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <SeverityBadge value={s.status} />
                  <span className="text-sm text-gray-900 font-medium truncate">{s.target_url}</span>
                  {s.frequency && s.frequency !== 'manual' && (
                    <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-1.5 py-0.5 rounded shrink-0 font-medium">
                      {s.frequency === 'daily' ? 'giornaliera' : s.frequency === 'weekly' ? 'settimanale' : 'mensile'}
                    </span>
                  )}
                  {s.status === 'failed' && <span className="text-xs text-gray-400 shrink-0">sito non raggiungibile</span>}
                  {s.status === 'completed' && (
                    <span className="text-xs text-gray-500 shrink-0">
                      {s.findings_count > 0 ? `${s.findings_count} finding` : 'nessun finding'}
                      {s.critical_count > 0 && <span className="text-red-600 ml-1">· {s.critical_count} critici</span>}
                      {s.high_count > 0 && s.critical_count === 0 && <span className="text-orange-600 ml-1">· {s.high_count} alti</span>}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-3">
                  <span className="text-xs text-gray-400">{new Date(s.created_at).toLocaleString('it-IT')}</span>
                  {(s.status === 'pending' || s.status === 'failed') && (
                    <button onClick={(e) => { e.stopPropagation(); handleRetry(s); }} disabled={retryingId === s.id} className="text-xs text-blue-600 hover:underline disabled:opacity-50 font-medium">
                      {retryingId === s.id ? 'Avvio…' : '↺ Riprova'}
                    </button>
                  )}
                  {s.status === 'completed' && <span className="text-xs text-gray-400">{isOpen(s.id) ? '▲' : '▼ dettagli'}</span>}
                  <button onClick={(e) => handleRemove(e, s.id)} disabled={removingId === s.id} className="text-xs text-gray-400 hover:text-red-500 transition-colors disabled:opacity-40">
                    {removingId === s.id ? '…' : '✕'}
                  </button>
                </div>
              </div>

              {isOpen(s.id) && (
                <div className="border-t border-corvin-100 px-4 py-3">
                  <div className="flex gap-4 mb-3 text-xs">
                    {['critical', 'high', 'medium', 'low', 'info'].map((sev) => (
                      <span key={sev} className="text-gray-500">
                        <span className="text-gray-900 font-semibold">{detail.summary?.[sev] ?? 0}</span> {sev}
                      </span>
                    ))}
                  </div>
                  {detail.findings?.length === 0 && <p className="text-sm text-gray-500">Nessun finding rilevato.</p>}
                  <div className="space-y-2">
                    {detail.findings?.map((f, i) => (
                      <div key={i} className="bg-corvin-50 rounded-lg px-3 py-2 border border-corvin-100">
                        <div className="flex items-center gap-2 mb-0.5">
                          <SeverityBadge value={f.severity} />
                          <span className="text-sm text-gray-900 font-medium">{f.title}</span>
                        </div>
                        <p className="text-xs text-gray-500">{f.description}</p>
                        {f.recommendation && <p className="text-xs text-blue-600 mt-1">↳ {f.recommendation}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
