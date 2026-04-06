import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { domain as domainApi } from '../api/domain';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';
import InfoModal from '../components/InfoModal';

const INFO_SECTIONS = [
  {
    heading: 'Cos\'è',
    text: 'Domain Reputation analizza la salute di un dominio: record DNS, presenza in blacklist DNSBL, certificato SSL, dati WHOIS e punteggio di reputazione aggregato.',
  },
  {
    heading: 'Come si usa',
    items: [
      'Inserisci un dominio (es. <code class="text-blue-600">example.com</code>) e clicca <strong>+ Aggiungi</strong>.',
      'Il sistema genera un <strong>token di verifica TXT</strong>: aggiungilo al DNS del dominio come record TXT per confermare la proprietà.',
      'Clicca <strong>Verifica</strong> quando il record DNS si è propagato (max 48h, di solito pochi minuti).',
      'Dopo la verifica, clicca <strong>Scansiona</strong> per avviare l\'analisi completa.',
      'I risultati mostrano il punteggio (0–100) e i finding per severity.',
    ],
  },
  {
    heading: 'Domini di test consigliati',
    items: [
      { label: 'Dominio pubblico sicuro', value: 'example.com' },
      { label: 'Google (certificato ottimo)', value: 'google.com' },
      { label: 'Senza verifica DNS', value: 'qualsiasi dominio, salta la verifica in demo' },
    ],
  },
  {
    heading: 'Note tecniche',
    items: [
      'La verifica DNS richiede un record TXT nella zona radice del dominio.',
      'La scansione include: MX, SPF, DKIM hint, DNSBL lookup, SSL expiry, WHOIS.',
      'Il punteggio è calcolato sommando penalità per ogni finding rilevato.',
    ],
  },
];

function ScoreBar({ score }) {
  const color = score >= 80 ? 'bg-green-500' : score >= 50 ? 'bg-amber-500' : 'bg-red-500';
  const textColor = score >= 80 ? 'text-green-700' : score >= 50 ? 'text-amber-700' : 'text-red-700';
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
      <span className={`text-sm font-semibold w-8 text-right ${textColor}`}>{score}</span>
    </div>
  );
}

export default function DomainReputation() {
  const { data: domains, loading, error, refetch } = useApi(() => domainApi.list());
  const [newDomain, setNewDomain] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState('');
  const [scanningId, setScanningId] = useState(null);
  const [showInfo, setShowInfo] = useState(false);

  const handleAdd = async (e) => {
    e.preventDefault();
    setAddError('');
    setAdding(true);
    try {
      await domainApi.add(newDomain);
      setNewDomain('');
      refetch();
    } catch (err) {
      setAddError(err.message);
    } finally {
      setAdding(false);
    }
  };

  const action = (fn, errorMap = {}) => async (id) => {
    setBusyId(id);
    setActionError('');
    try { await fn(id); refetch(); } catch (err) {
      const msg = err.message ?? '';
      const mapped = Object.entries(errorMap).find(([key]) => msg.toLowerCase().includes(key.toLowerCase()));
      setActionError(mapped ? mapped[1] : 'Si è verificato un errore. Riprova più tardi.');
    }
    finally { setBusyId(null); }
  };

  const handleVerify = action(domainApi.verify, {
    'Verification failed': 'Verifica fallita. Assicurati di aver aggiunto il record TXT al DNS del dominio. La propagazione DNS può richiedere fino a 48 ore.',
    'not found': 'Dominio non trovato.',
  });
  const handleScan = async (id) => {
    setBusyId(id);
    setScanningId(id);
    setActionError('');
    try {
      await domainApi.scan(id);
      let found = false;
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const updated = await refetch();
        const d = (updated ?? []).find((d) => d.id === id);
        if (d?.last_scan_at) { found = true; break; }
      }
      if (!found) await refetch();
    } catch (err) {
      const msg = err.message ?? '';
      if (msg.toLowerCase().includes('must be verified')) {
        setActionError('Devi prima verificare il dominio prima di poterlo scansionare.');
      } else {
        setActionError('Si è verificato un errore. Riprova più tardi.');
      }
    } finally {
      setBusyId(null);
      setScanningId(null);
    }
  };
  const handleDelete = async (id) => {
    if (!confirm('Rimuovere questo dominio?')) return;
    action(domainApi.remove)(id);
  };

  return (
    <div>
      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} title="Domain Reputation — Guida" sections={INFO_SECTIONS} />

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Domain Reputation</h1>
          <p className="text-gray-500 text-sm mt-1">Analisi DNS, blacklist, certificato SSL e WHOIS</p>
        </div>
        <button onClick={() => setShowInfo(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>
          Guida
        </button>
      </div>

      <form onSubmit={handleAdd} className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="example.com"
          value={newDomain}
          onChange={(e) => setNewDomain(e.target.value)}
          required
          className="form-input flex-1"
        />
        <button type="submit" disabled={adding} className="btn-primary whitespace-nowrap">
          {adding ? 'Aggiunta…' : '+ Aggiungi'}
        </button>
      </form>
      {addError && <p className="text-sm text-red-600 mb-4">{addError}</p>}
      {actionError && <p className="text-sm text-red-600 mb-4">{actionError}</p>}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {!loading && domains?.length === 0 && (
        <EmptyState title="Nessun dominio monitorato" description="Aggiungi un dominio e verificalo con il record DNS TXT." />
      )}

      {!loading && domains?.length > 0 && (
        <div className="space-y-3">
          {domains.map((d) => (
            <div key={d.id} className="bg-white rounded-xl shadow-card border border-corvin-200 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-semibold text-gray-900">{d.domain}</span>
                    <SeverityBadge value={d.is_verified ? 'verified' : 'unverified'} />
                  </div>
                  {d.reputation_score != null && (
                    <div className="max-w-xs mb-2">
                      <p className="text-xs text-gray-500 mb-1">Punteggio reputazione</p>
                      <ScoreBar score={d.reputation_score} />
                    </div>
                  )}
                  {d.verification_token && !d.is_verified && (
                    <div className="mt-2 p-2.5 bg-amber-50 border border-amber-200 rounded-lg">
                      <p className="text-xs text-amber-700 font-medium mb-1">Aggiungi questo record TXT al DNS del dominio:</p>
                      <code className="text-xs text-amber-800 font-mono break-all">{d.verification_token}</code>
                    </div>
                  )}
                  {d.last_scan_at && (
                    <p className="text-xs text-gray-400 mt-1">
                      Ultima scansione: {new Date(d.last_scan_at).toLocaleString('it-IT')}
                    </p>
                  )}
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  {!d.is_verified && (
                    <button
                      onClick={() => handleVerify(d.id)}
                      disabled={busyId === d.id}
                      className="text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50"
                    >
                      Verifica
                    </button>
                  )}
                  {d.is_verified && (
                    <button
                      onClick={() => handleScan(d.id)}
                      disabled={busyId === d.id}
                      className="text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50"
                    >
                      {scanningId === d.id ? 'Scansione in corso…' : 'Scansiona'}
                    </button>
                  )}
                  <button onClick={() => handleDelete(d.id)} className="text-xs font-medium text-red-500 hover:text-red-700">
                    Rimuovi
                  </button>
                </div>
              </div>
              {d.scan_findings?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-corvin-100 space-y-1.5">
                  {d.scan_findings.map((f, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <SeverityBadge value={f.severity} />
                      <span className="text-gray-700">{f.title ?? f.message ?? f.check}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
