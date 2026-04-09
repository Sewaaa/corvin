/**
 * ErrorBanner — mostra errori API in modo prominente.
 * Per errori 403 (privilegi) usa un layout speciale con icona lucchetto.
 */
export default function ErrorBanner({ message, className = '' }) {
  if (!message) return null;

  const isForbidden =
    message.toLowerCase().includes('privilegi') ||
    message.toLowerCase().includes('permesso') ||
    message.toLowerCase().includes('forbidden');

  if (isForbidden) {
    return (
      <div className={`flex items-start gap-3 px-4 py-3 rounded-xl bg-red-50 border border-red-200 ${className}`}>
        <span className="mt-0.5 shrink-0 flex items-center justify-center w-7 h-7 rounded-full bg-red-100">
          <svg className="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
          </svg>
        </span>
        <div>
          <p className="text-sm font-bold text-red-700">Accesso non autorizzato</p>
          <p className="text-xs text-red-600 mt-0.5">{message}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-2 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm ${className}`}>
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      {message}
    </div>
  );
}
