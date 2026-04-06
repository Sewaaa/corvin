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
      'Inserisci un dominio (es. <code class="text-yellow-300">example.com</code>) e clicca <strong>+ Aggiungi</strong>.',
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
  const color = score >= 80 ? 'bg-green-500' : score >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-corvin-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs text-gray-400 w-8 text-right">{score}</span>
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
      // Poll every 3s for up to 30s waiting for background scan to complete
      let found = false;
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const updated = await refetch();
        const domain = (updated ?? []).find((d) => d.id === id);
        if (domain?.last_scan_at) { found = true; break; }
      }
      if (!found) await refetch();
    } catch (err) {
      const msg = err.message ?? '';
      if (msg.toLowerCase().includes('must be verified')) {
        setActionError('Devi prima verificare il dominio prima di poterlo scansionare.');
      } else if (msg.toLowerCase().includes('not found')) {
        setActionError('Dominio non trovato.');
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
      <InfoModal
        open={showInfo}
        onClose={() => setShowInfo(false)}
        title="Domain Reputation — Guida"
        sections={INFO_SECTIONS}
      />

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Domain Reputation</h1>
          <p className="text-gray-400 text-sm mt-1">DNS health, DNSBL, SSL e WHOIS analysis</p>
        </div>
        <button
          onClick={() => setShowInfo(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-corvin-accent border border-corvin-accent/30 rounded-lg hover:bg-corvin-accent/10 transition-colors"
        >
          <span>ⓘ</span> Info
        </button>
      </div>

      <form onSubmit={handleAdd} className="flex gap-3 mb-6">
        <input
          type="text"
          placeholder="example.com"
          value={newDomain}
          onChange={(e) => setNewDomain(e.target.value)}
          required
          className="flex-1 bg-corvin-800 border border-corvin-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent"
        />
        <button
          type="submit"
          disabled={adding}
          className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg hover:bg-corvin-accent/90 disabled:opacity-50"
        >
          {adding ? 'Aggiunta…' : '+ Aggiungi'}
        </button>
      </form>
      {addError && <p className="text-red-400 text-sm mb-4">{addError}</p>}
      {actionError && <p className="text-red-400 text-sm mb-4">{actionError}</p>}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && domains?.length === 0 && (
        <EmptyState
          title="Nessun dominio monitorato"
          description="Aggiungi un dominio e verificalo con il record DNS TXT."
        />
      )}

      {!loading && domains?.length > 0 && (
        <div className="space-y-3">
          {domains.map((d) => (
            <div key={d.id} className="bg-corvin-800 border border-corvin-700 rounded-xl p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-white">{d.domain}</span>
                    <SeverityBadge value={d.is_verified ? 'verified' : 'unverified'} />
                  </div>
                  {d.reputation_score != null && (
                    <div className="max-w-xs">
                      <ScoreBar score={d.reputation_score} />
                    </div>
                  )}
                  {d.verification_token && !d.is_verified && (
                    <p className="text-xs text-gray-500 mt-1">
                      TXT: <code className="text-yellow-400">{d.verification_token}</code>
                    </p>
                  )}
                  {d.last_scan_at && (
                    <p className="text-xs text-gray-500 mt-1">
                      Ultima scan: {new Date(d.last_scan_at).toLocaleString('it-IT')}
                    </p>
                  )}
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  {!d.is_verified && (
                    <button
                      onClick={() => handleVerify(d.id)}
                      disabled={busyId === d.id}
                      className="text-xs text-corvin-accent hover:underline disabled:opacity-50"
                    >
                      Verifica
                    </button>
                  )}
                  {d.is_verified && (
                    <button
                      onClick={() => handleScan(d.id)}
                      disabled={busyId === d.id}
                      className="text-xs text-corvin-accent hover:underline disabled:opacity-50"
                    >
                      {scanningId === d.id ? 'Scansione in corso…' : 'Scansiona'}
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(d.id)}
                    className="text-xs text-red-400 hover:underline"
                  >
                    Rimuovi
                  </button>
                </div>
              </div>
              {d.scan_findings?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-corvin-700 space-y-1">
                  {d.scan_findings.map((f, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <SeverityBadge value={f.severity} />
                      <span className="text-gray-300">{f.title ?? f.message ?? f.check}</span>
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
