import { useState, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { breach } from '../api/breach';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import InfoModal from '../components/InfoModal';

const INFO_SECTIONS = [
  {
    heading: 'Cos\'è',
    text: 'Breach Monitor controlla se un indirizzo email è comparso in data breach pubblici, usando l\'API XposedOrNot con k-anonymity: la password non viene mai inviata in chiaro.',
  },
  {
    heading: 'Come si usa',
    items: [
      'Inserisci un indirizzo email nel campo e clicca <strong>Aggiungi e verifica</strong>.',
      'Il sistema interroga XposedOrNot e mostra quante breach coinvolgono quell\'indirizzo.',
      'Clicca su una riga per espandere i <strong>dettagli</strong>: breach rilevate, dati esposti e un <strong>piano d\'azione consigliato</strong>.',
      'I dati esposti includono: password, email, numeri di telefono, indirizzi IP, ecc.',
      'Le email rimangono monitorate: puoi rimuoverle con il tasto <strong>Rimuovi</strong>.',
    ],
  },
  {
    heading: 'Dati di test consigliati',
    items: [
      { label: 'Email con molte breach', value: 'test@example.com' },
      { label: 'Email sicura (nessuna breach)', value: 'nobreaches@corvin-demo.local' },
      { label: 'Suggerimento reale', value: 'prova con la tua email personale' },
    ],
  },
  {
    heading: 'Note tecniche',
    items: [
      'Le breach vengono recuperate da <strong>XposedOrNot</strong> (xposedornot.com).',
      'Solo i primi 5 caratteri dell\'hash SHA-1 vengono inviati all\'API (k-anonymity).',
      'Il conteggio si aggiorna ad ogni verifica manuale.',
    ],
  },
];

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

// ── Piano d'azione guidato ───────────────────────────────────────────────────
const ACTION_PLAN = [
  { icon: '1', text: 'Cambia immediatamente la password dell\'account compromesso.', urgent: true },
  { icon: '2', text: 'Abilita l\'autenticazione a due fattori (2FA/MFA) dove disponibile.', urgent: true },
  { icon: '3', text: 'Controlla se hai usato la stessa password su altri servizi e cambiale tutte.', urgent: true },
  { icon: '4', text: 'Verifica gli accessi recenti sull\'account e revoca sessioni sospette.', urgent: false },
  { icon: '5', text: 'Monitora l\'account per attività insolite nelle prossime settimane.', urgent: false },
  { icon: '6', text: 'Considera l\'uso di un password manager per generare password uniche.', urgent: false },
];

// ── Data class badges (categorization of exposed data) ───────────────────────
const DATA_CLASS_COLORS = {
  'Passwords': 'text-red-400 bg-red-900/30 border-red-800',
  'Email addresses': 'text-yellow-400 bg-yellow-900/30 border-yellow-800',
  'Phone numbers': 'text-orange-400 bg-orange-900/30 border-orange-800',
  'IP addresses': 'text-blue-400 bg-blue-900/30 border-blue-800',
  'Physical addresses': 'text-purple-400 bg-purple-900/30 border-purple-800',
  'Credit cards': 'text-red-400 bg-red-900/30 border-red-800',
};
const getDataClassColor = (cls) => DATA_CLASS_COLORS[cls] ?? 'text-gray-300 bg-corvin-700/40 border-corvin-600';

export default function BreachMonitor() {
  const { data: emails, loading, error, refetch } = useApi(() => breach.list());
  const { data: historyData } = useApi(() => breach.history(1, 100));
  const [newEmail, setNewEmail] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');
  const [addResult, setAddResult] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [showInfo, setShowInfo] = useState(false);

  // Map breach details by email_masked for expanded view
  const breachDetailsByEmail = {};
  if (historyData?.items) {
    for (const item of historyData.items) {
      breachDetailsByEmail[item.email_masked] = item.breaches ?? [];
    }
  }

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
      <InfoModal
        open={showInfo}
        onClose={() => setShowInfo(false)}
        title="Breach Monitor — Guida"
        sections={INFO_SECTIONS}
      />

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Breach Monitor</h1>
          <p className="text-gray-400 text-sm mt-1">Monitoraggio breaches tramite XposedOrNot</p>
        </div>
        <button
          onClick={() => setShowInfo(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-corvin-accent border border-corvin-accent/30 rounded-lg hover:bg-corvin-accent/10 transition-colors"
        >
          <span>ⓘ</span> Info
        </button>
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
                      <td colSpan={4} className="px-6 py-4">
                        {/* Breach list with data_classes */}
                        <p className="text-xs text-gray-400 mb-3 font-semibold uppercase tracking-wide">
                          Breach rilevate ({em.breach_count})
                        </p>
                        <div className="space-y-3 mb-4">
                          {(breachDetailsByEmail[em.email_masked] ?? em.breach_names.map(n => ({ breach_name: n, data_classes: [] }))).map((b, i) => (
                            <div key={i} className="bg-corvin-800/60 rounded-lg px-3 py-2">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-medium text-red-300">{b.breach_name}</span>
                                {b.breach_date && (
                                  <span className="text-xs text-gray-500">{b.breach_date}</span>
                                )}
                              </div>
                              {b.data_classes?.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mt-1">
                                  <span className="text-xs text-gray-500 mr-1">Dati esposti:</span>
                                  {b.data_classes.map((cls, j) => (
                                    <span
                                      key={j}
                                      className={`px-1.5 py-0.5 text-xs rounded border ${getDataClassColor(cls)}`}
                                    >
                                      {cls}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {b.description && (
                                <p className="text-xs text-gray-500 mt-1 line-clamp-2">{b.description}</p>
                              )}
                            </div>
                          ))}
                        </div>

                        {/* Action plan */}
                        <div className="border-t border-corvin-700 pt-3">
                          <p className="text-xs text-corvin-accent mb-2 font-semibold uppercase tracking-wide">
                            Piano d'azione consigliato
                          </p>
                          <div className="space-y-1.5">
                            {ACTION_PLAN.map((step, i) => (
                              <div key={i} className="flex items-start gap-2">
                                <span className={`text-xs font-bold w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                                  step.urgent ? 'bg-red-900/40 text-red-400' : 'bg-corvin-700 text-gray-400'
                                }`}>
                                  {step.icon}
                                </span>
                                <span className={`text-xs ${step.urgent ? 'text-white' : 'text-gray-400'}`}>
                                  {step.text}
                                </span>
                              </div>
                            ))}
                          </div>
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
