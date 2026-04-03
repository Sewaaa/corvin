import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { webScan } from '../api/webScan';
import { domain as domainApi } from '../api/domain';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';

export default function WebScanner() {
  const { data: scans, loading, error, refetch } = useApi(() => webScan.list());
  const { data: domains } = useApi(() => domainApi.list());
  const [selectedDomain, setSelectedDomain] = useState('');
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');
  const [detail, setDetail] = useState(null);

  const verifiedDomains = (domains ?? []).filter((d) => d.is_verified);

  const handleStart = async (e) => {
    e.preventDefault();
    if (!selectedDomain) return;
    setStartError('');
    setStarting(true);
    try {
      await webScan.start(selectedDomain);
      refetch();
    } catch (err) {
      setStartError(err.message);
    } finally {
      setStarting(false);
    }
  };

  const handleDetail = async (id) => {
    if (detail?.id === id) { setDetail(null); return; }
    try {
      const d = await webScan.get(id);
      setDetail(d);
    } catch {}
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Web Scanner</h1>
        <p className="text-gray-400 text-sm mt-1">Scansione passiva — max 20 richieste, nessun payload intrusivo</p>
      </div>

      {/* Start scan */}
      <form onSubmit={handleStart} className="flex gap-3 mb-6">
        <select
          value={selectedDomain}
          onChange={(e) => setSelectedDomain(e.target.value)}
          className="flex-1 bg-corvin-800 border border-corvin-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent"
        >
          <option value="">Seleziona un dominio verificato…</option>
          {verifiedDomains.map((d) => (
            <option key={d.id} value={d.id}>{d.domain}</option>
          ))}
        </select>
        <button
          type="submit"
          disabled={starting || !selectedDomain}
          className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg hover:bg-corvin-accent/90 disabled:opacity-50"
        >
          {starting ? 'Avvio…' : '▶ Avvia scan'}
        </button>
      </form>
      {startError && <p className="text-red-400 text-sm mb-4">{startError}</p>}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && scans?.length === 0 && (
        <EmptyState
          title="Nessuna scansione"
          description="Aggiungi e verifica un dominio, poi avvia la prima scansione."
        />
      )}

      {!loading && scans?.length > 0 && (
        <div className="space-y-2">
          {scans.map((s) => (
            <div key={s.id} className="bg-corvin-800 border border-corvin-700 rounded-xl">
              <div
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-corvin-700/30"
                onClick={() => handleDetail(s.id)}
              >
                <div className="flex items-center gap-3">
                  <SeverityBadge value={s.status} />
                  <span className="text-sm text-white">{s.target_url}</span>
                </div>
                <span className="text-xs text-gray-500">
                  {new Date(s.created_at).toLocaleString('it-IT')}
                </span>
              </div>

              {detail?.id === s.id && (
                <div className="border-t border-corvin-700 px-4 py-3">
                  <div className="flex gap-4 mb-3 text-xs">
                    {['critical','high','medium','low','info'].map((sev) => (
                      <span key={sev} className="text-gray-400">
                        <span className="text-white font-medium">{detail.summary?.[sev] ?? 0}</span> {sev}
                      </span>
                    ))}
                  </div>
                  {detail.findings?.length === 0 && (
                    <p className="text-xs text-gray-500">Nessun finding rilevato.</p>
                  )}
                  <div className="space-y-2">
                    {detail.findings?.map((f, i) => (
                      <div key={i} className="bg-corvin-700/50 rounded-lg px-3 py-2">
                        <div className="flex items-center gap-2 mb-0.5">
                          <SeverityBadge value={f.severity} />
                          <span className="text-sm text-white">{f.title}</span>
                        </div>
                        <p className="text-xs text-gray-400">{f.description}</p>
                        {f.recommendation && (
                          <p className="text-xs text-corvin-accent mt-1">↳ {f.recommendation}</p>
                        )}
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
