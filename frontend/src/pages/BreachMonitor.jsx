import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { breach } from '../api/breach';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import InfoModal from '../components/InfoModal';
import ErrorBanner from '../components/ErrorBanner';
import { useSettings } from '../context/SettingsContext';
import { useAuth } from '../context/AuthContext';

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
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-green-50 text-green-700 border border-green-200">
      ✓ Sicura
    </span>
  );
  if (count <= 3) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
      ⚠ {count} {count === 1 ? 'breach' : 'breach'}
    </span>
  );
  if (count <= 10) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-orange-50 text-orange-700 border border-orange-200">
      ⚠ {count} breach
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
      ✕ {count} breach
    </span>
  );
}

const ACTION_KEYS = [
  { icon: '1', key: 'breach.action1', urgent: true },
  { icon: '2', key: 'breach.action2', urgent: true },
  { icon: '3', key: 'breach.action3', urgent: true },
  { icon: '4', key: 'breach.action4', urgent: false },
  { icon: '5', key: 'breach.action5', urgent: false },
  { icon: '6', key: 'breach.action6', urgent: false },
];

const DATA_CLASS_COLORS = {
  'Passwords':         'text-red-700 bg-red-50 border-red-200',
  'Email addresses':   'text-amber-700 bg-amber-50 border-amber-200',
  'Phone numbers':     'text-orange-700 bg-orange-50 border-orange-200',
  'IP addresses':      'text-blue-700 bg-blue-50 border-blue-200',
  'Physical addresses':'text-purple-700 bg-purple-50 border-purple-200',
  'Credit cards':      'text-red-700 bg-red-50 border-red-200',
};
const getDataClassColor = (cls) => DATA_CLASS_COLORS[cls] ?? 'text-gray-600 bg-gray-100 border-gray-200';

export default function BreachMonitor() {
  const { t } = useSettings();
  const { user } = useAuth();
  const isViewer = user?.role === 'viewer';
  const { data: emails, loading, error, refetch } = useApi(() => breach.list());
  const { data: historyData } = useApi(() => breach.history(1, 100));
  const [newEmail, setNewEmail] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');
  const [addResult, setAddResult] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [showInfo, setShowInfo] = useState(false);

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
      setAddError(t('breach.addError'));
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm(t('breach.removeConfirm'))) return;
    try {
      await breach.remove(id);
      refetch();
    } catch {
      alert(t('breach.removeError'));
    }
  };

  const toggleExpand = (id) => setExpandedId(expandedId === id ? null : id);

  return (
    <div>
      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} title="Breach Monitor — Guida" sections={INFO_SECTIONS} />

      <div className="flex items-start justify-between flex-wrap gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('breach.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('breach.subtitle')}</p>
        </div>
        <button onClick={() => setShowInfo(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>
          {t('common.guide')}
        </button>
      </div>

      {!isViewer && (
        <form onSubmit={handleAdd} className="flex gap-3 mb-4">
          <input
            type="email"
            placeholder={t('breach.placeholder')}
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            required
            className="form-input flex-1"
          />
          <button type="submit" disabled={adding} className="btn-primary whitespace-nowrap">
            {adding ? t('breach.adding') : t('breach.addBtn')}
          </button>
        </form>
      )}

      {addError && <ErrorBanner message={addError} className="mb-4" />}

      {addResult && (
        <div className={`mb-4 p-3 rounded-lg text-sm flex items-center gap-2 ${
          addResult.is_breached
            ? 'bg-red-50 border border-red-200 text-red-700'
            : 'bg-green-50 border border-green-200 text-green-700'
        }`}>
          {addResult.is_breached
            ? `⚠ ${addResult.email_masked} ${t('breach.found', { count: addResult.breach_count })}`
            : `✓ ${addResult.email_masked} ${t('breach.notFound')}`}
        </div>
      )}

      {loading && <LoadingSpinner />}
      {error && <ErrorBanner message={error} />}

      {!loading && emails?.length === 0 && (
        <EmptyState title={t('breach.emptyTitle')} description={t('breach.emptyDesc')} />
      )}

      {!loading && emails?.length > 0 && (
        <div className="bg-white rounded-xl shadow-card border border-corvin-200 overflow-hidden">
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[480px]">
            <thead>
              <tr className="border-b border-corvin-200 bg-corvin-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{t('breach.thEmail')}</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden sm:table-cell">{t('breach.thLastCheck')}</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{t('breach.thStatus')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {emails.map((em) => (
                <>
                  <tr
                    key={em.id}
                    className="border-b border-corvin-100 hover:bg-corvin-50 cursor-pointer transition-colors"
                    onClick={() => toggleExpand(em.id)}
                  >
                    <td className="px-4 py-3 text-gray-900 font-medium max-w-[160px] truncate">{em.email_masked}</td>
                    <td className="px-4 py-3 text-gray-500 hidden sm:table-cell">
                      {em.last_checked ? new Date(em.last_checked).toLocaleDateString('it-IT') : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <BreachBadge count={em.breach_count} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-3 justify-end items-center">
                        {em.breach_count > 0 && (
                          <span className="text-xs text-gray-400 hidden sm:inline">
                            {expandedId === em.id ? t('breach.hide') : t('breach.details')}
                          </span>
                        )}
                        {!isViewer && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDelete(em.id); }}
                            className="text-xs text-red-500 hover:text-red-700 hover:underline"
                          >
                            {t('common.remove')}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {expandedId === em.id && em.breach_count > 0 && (
                    <tr key={`${em.id}-detail`} className="bg-corvin-50 border-b border-corvin-100">
                      <td colSpan={4} className="px-4 sm:px-6 py-4">
                        <p className="text-xs font-bold text-gray-500 mb-3 uppercase tracking-wide">
                          {t('breach.detected')} ({em.breach_count})
                        </p>
                        {/* Breach names — compact badges */}
                        <div className="flex flex-wrap gap-2 mb-3">
                          {(em.breach_names ?? []).map((name, i) => (
                            <span key={i} className="px-2 py-0.5 text-xs rounded bg-red-50 border border-red-200 text-red-600 font-medium">
                              {name}
                            </span>
                          ))}
                        </div>

                        {/* Data classes exposed — aggregated unique list */}
                        {(() => {
                          const allClasses = [...new Set(
                            (breachDetailsByEmail[em.email_masked] ?? [])
                              .flatMap(b => b.data_classes ?? [])
                          )];
                          if (!allClasses.length) return null;
                          return (
                            <div className="mb-4">
                              <p className="text-xs text-gray-500 mb-1.5 font-medium">{t('breach.dataExposed')}</p>
                              <div className="flex flex-wrap gap-1.5">
                                {allClasses.map((cls, j) => (
                                  <span key={j} className={`px-1.5 py-0.5 text-xs rounded border ${getDataClassColor(cls)}`}>
                                    {cls}
                                  </span>
                                ))}
                              </div>
                            </div>
                          );
                        })()}

                        <div className="border-t border-corvin-200 pt-3">
                          <p className="text-xs font-bold text-blue-600 mb-2.5 uppercase tracking-wide">
                            {t('breach.actionPlan')}
                          </p>
                          <div className="space-y-2">
                            {ACTION_KEYS.map((step, i) => (
                              <div key={i} className="flex items-start gap-2.5">
                                <span className={`text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                                  step.urgent ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-500'
                                }`}>
                                  {step.icon}
                                </span>
                                <span className={`text-sm ${step.urgent ? 'text-gray-900 font-medium' : 'text-gray-600'}`}>
                                  {t(step.key)}
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
        </div>
      )}
    </div>
  );
}
