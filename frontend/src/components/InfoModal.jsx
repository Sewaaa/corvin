import { useEffect } from 'react';

export default function InfoModal({ open, onClose, title, sections = [] }) {
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[85vh] flex flex-col shadow-2xl border border-corvin-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-corvin-200">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-blue-100 flex items-center justify-center">
              <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path strokeLinecap="round" d="M12 16v-4M12 8h.01" />
              </svg>
            </div>
            <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center"
            aria-label="Chiudi"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-5 py-4 space-y-5 text-sm">
          {sections.map((section, i) => (
            <div key={i}>
              <p className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-2">
                {section.heading}
              </p>

              {section.text && (
                <p className="text-gray-600 leading-relaxed">{section.text}</p>
              )}

              {Array.isArray(section.items) && section.items.length > 0 &&
                typeof section.items[0] === 'string' && (
                  <ul className="space-y-1.5">
                    {section.items.map((item, j) => (
                      <li key={j} className="flex gap-2 text-gray-600 leading-relaxed">
                        <span className="text-blue-500 flex-shrink-0 mt-0.5 font-bold">›</span>
                        <span dangerouslySetInnerHTML={{ __html: item }} />
                      </li>
                    ))}
                  </ul>
                )}

              {Array.isArray(section.items) && section.items.length > 0 &&
                typeof section.items[0] === 'object' && section.items[0].label && (
                  <div className="space-y-1.5">
                    {section.items.map((item, j) => (
                      <div key={j} className="flex flex-col sm:flex-row sm:items-baseline gap-0.5 sm:gap-2">
                        <span className="text-gray-500 text-xs flex-shrink-0">{item.label}:</span>
                        <code className="text-blue-700 text-xs bg-blue-50 px-1.5 py-0.5 rounded border border-blue-100 break-all">
                          {item.value}
                        </code>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-corvin-200 flex justify-end">
          <button
            onClick={onClose}
            className="btn-primary"
          >
            Chiudi
          </button>
        </div>
      </div>
    </div>
  );
}
