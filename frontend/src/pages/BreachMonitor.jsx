import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { breach } from '../api/breach';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';

export default function BreachMonitor() {
  const { data: emails, loading, error, refetch } = useApi(() => breach.list());
  const [newEmail, setNewEmail] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');
  const [checkingId, setCheckingId] = useState(null);

  const handleAdd = async (e) => {
    e.preventDefault();
    setAddError('');
    setAdding(true);
    try {
      await breach.add(newEmail);
      setNewEmail('');
      refetch();
    } catch (err) {
      setAddError(err.message);
    } finally {
      setAdding(false);
    }
  };

  const handleCheck = async (id) => {
    setCheckingId(id);
    try {
      await breach.check(id);
      refetch();
    } catch {
      // ignore
    } finally {
      setCheckingId(null);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Rimuovere questo indirizzo email?')) return;
    try {
      await breach.remove(id);
      refetch();
    } catch {}
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Breach Monitor</h1>
        <p className="text-gray-400 text-sm mt-1">Monitoraggio breaches tramite HIBP con k-anonymity</p>
      </div>

      {/* Add email form */}
      <form onSubmit={handleAdd} className="flex gap-3 mb-6">
        <input
          type="email"
          placeholder="email@company.com"
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
          {adding ? 'Aggiunta…' : '+ Aggiungi'}
        </button>
      </form>
      {addError && <p className="text-red-400 text-sm mb-4">{addError}</p>}

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
                <th className="text-left px-4 py-3">Breaches</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {emails.map((em) => (
                <tr key={em.id} className="border-b border-corvin-700/50 hover:bg-corvin-700/30">
                  <td className="px-4 py-3 text-white">{em.email}</td>
                  <td className="px-4 py-3 text-gray-400">
                    {em.last_checked_at
                      ? new Date(em.last_checked_at).toLocaleDateString('it-IT')
                      : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {em.breach_count > 0 ? (
                      <SeverityBadge value={`${em.breach_count} breach`} />
                    ) : (
                      <SeverityBadge value="safe" />
                    )}
                  </td>
                  <td className="px-4 py-3 flex gap-2 justify-end">
                    <button
                      onClick={() => handleCheck(em.id)}
                      disabled={checkingId === em.id}
                      className="text-xs text-corvin-accent hover:underline disabled:opacity-50"
                    >
                      {checkingId === em.id ? 'Verifica…' : 'Verifica'}
                    </button>
                    <button
                      onClick={() => handleDelete(em.id)}
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
  );
}
