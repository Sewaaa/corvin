import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { domain as domainApi } from '../api/domain';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';

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
  const handleScan = action(domainApi.scan, {
    'must be verified': 'Devi prima verificare il dominio prima di poterlo scansionare.',
    'not found': 'Dominio non trovato.',
  });
  const handleDelete = async (id) => {
    if (!confirm('Rimuovere questo dominio?')) return;
    action(domainApi.remove)(id);
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Domain Reputation</h1>
        <p className="text-gray-400 text-sm mt-1">DNS health, DNSBL, SSL e WHOIS analysis</p>
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
                      TXT: <code className="text-yellow-400">corvin-verify={d.verification_token}</code>
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
                      {busyId === d.id ? 'Scansione…' : 'Scansiona'}
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
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
