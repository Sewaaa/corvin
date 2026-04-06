import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { breach } from '../api/breach';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';

function BreachBadge({ count }) {
  if (count === 0) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-900/40 text-green-400 border border-green-700">
      ✓ Sicura
    </span>
  );
  if (count <= 3) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-900/40 text-yellow-400 border border-yellow-700">
      ⚠ {count} breach
    </span>
  );
  if (count <= 10) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-orange-900/40 text-orange-400 border border-orange-700">
      ⚠ {count} breach
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-900/40 text-red-400 border border-red-700">
      ✕ {count} breach
    </span>
  );
}

export default function BreachMonitor() {
  const { data: emails, loading, error, refetch } = useApi(() => breach.list());
  const [newEmail, setNewEmail] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');
  const [addResult, setAddResult] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const handleAdd = async (e) => {
    e.preventDefault();
    setAddError('');
    setAddResult(null);
    setAdding(true);
    try {
      const results = await breach.add(newEmail);
      setNewEmail('');
      setAddResult(results?.[0] ?? null);
      refetch();
    } catch (err) {
      setAddError('Errore durante la verifica. Riprova più tardi.');
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Rimuovere questo indirizzo email?')) return;
    try {
      await breach.remove(id);
      refetch();
    } catch {
      alert('Errore durante la rimozione. Riprova più tardi.');
    }
  };

  const toggleExpand = (id) => setExpandedId(expandedId === id ? null : id);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Breach Monitor</h1>
        <p className="text-gray-400 text-sm mt-1">Monitoraggio breaches tramite XposedOrNot</p>
      </div>

      <form onSubmit={handleAdd} className="flex gap-3 mb-3">
        <input
          type="email"
          placeholder="email@example.com"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          required
          className="flex-1 bg-corvin-800 border border-corvin-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent"
        />
        <button
          type="submit"
          disabled={adding}
          className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg hover:bg-corvin-accent/90 disabled:opacity-50"
        >
          {adding ? 'Verifica in corso…' : 'Aggiungi e verifica'}
        </button>
      </form>

      {addError && <p className="text-red-400 text-sm mb-4">{addError}</p>}

      {addResult && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${addResult.is_breached ? 'bg-red-900/30 border border-red-700 text-red-300' : 'bg-green-900/30 border border-green-700 text-green-300'}`}>
          {addResult.is_breached
            ? `⚠ ${addResult.email_masked} trovata in ${addResult.breach_count} breach.`
            : `✓ ${addResult.email_masked} non trovata in nessuna breach nota.`}
        </div>
      )}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && emails?.length === 0 && (
        <EmptyState
          title="Nessuna email monitorata"
          description="Aggiungi un indirizzo email per avviare il monitoraggio breach."
        />
      )}

      {!loading && emails?.length > 0 && (
        <div className="bg-corvin-800 border border-corvin-700 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-corvin-700 text-gray-400 text-xs uppercase">
                <th className="text-left px-4 py-3">Email</th>
                <th className="text-left px-4 py-3">Ultima verifica</th>
                <th className="text-left px-4 py-3">Stato</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {emails.map((em) => (
                <>
                  <tr
                    key={em.id}
                    className="border-b border-corvin-700/50 hover:bg-corvin-700/30 cursor-pointer"
                    onClick={() => toggleExpand(em.id)}
                  >
                    <td className="px-4 py-3 text-white font-medium">{em.email_masked}</td>
                    <td className="px-4 py-3 text-gray-400">
                      {em.last_checked
                        ? new Date(em.last_checked).toLocaleDateString('it-IT')
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <BreachBadge count={em.breach_count} />
                    </td>
                    <td className="px-4 py-3 flex gap-3 justify-end items-center">
                      {em.breach_count > 0 && (
                        <span className="text-xs text-gray-400">
                          {expandedId === em.id ? '▲ Nascondi' : '▼ Dettagli'}
                        </span>
                      )}
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(em.id); }}
                        className="text-xs text-red-400 hover:underline"
                      >
                        Rimuovi
                      </button>
                    </td>
                  </tr>
                  {expandedId === em.id && em.breach_count > 0 && (
                    <tr key={`${em.id}-detail`} className="bg-corvin-900/50 border-b border-corvin-700/50">
                      <td colSpan={4} className="px-6 py-3">
                        <p className="text-xs text-gray-400 mb-2 font-semibold uppercase tracking-wide">
                          Breach rilevate ({em.breach_count})
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {em.breach_names.map((name, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 text-xs rounded bg-red-900/30 border border-red-800 text-red-300"
                            >
                              {name}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
