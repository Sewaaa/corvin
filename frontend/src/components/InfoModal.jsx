import { useEffect } from 'react';

/**
 * InfoModal — modale tutorial riutilizzabile.
 *
 * Props:
 *   open      : bool
 *   onClose   : () => void
 *   title     : string
 *   sections  : Array<{ heading: string, items: string[] | { label, value }[] }>
 *               oppure Array<{ heading: string, text: string }>
 */
export default function InfoModal({ open, onClose, title, sections = [] }) {
  // Chiudi con Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-corvin-800 border border-corvin-700 rounded-2xl w-full max-w-lg max-h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-corvin-700">
          <div className="flex items-center gap-2">
            <span className="text-corvin-accent text-lg">ⓘ</span>
            <h2 className="text-base font-semibold text-white">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white transition-colors text-xl leading-none"
            aria-label="Chiudi"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-5 py-4 space-y-5 text-sm">
          {sections.map((section, i) => (
            <div key={i}>
              <p className="text-xs font-semibold text-corvin-accent uppercase tracking-wider mb-2">
                {section.heading}
              </p>

              {/* Plain text */}
              {section.text && (
                <p className="text-gray-300 leading-relaxed">{section.text}</p>
              )}

              {/* Bullet list (string[]) */}
              {Array.isArray(section.items) && section.items.length > 0 &&
                typeof section.items[0] === 'string' && (
                  <ul className="space-y-1.5">
                    {section.items.map((item, j) => (
                      <li key={j} className="flex gap-2 text-gray-300 leading-relaxed">
                        <span className="text-corvin-accent flex-shrink-0 mt-0.5">›</span>
                        <span dangerouslySetInnerHTML={{ __html: item }} />
                      </li>
                    ))}
                  </ul>
                )}

              {/* Key-value list ({ label, value }[]) */}
              {Array.isArray(section.items) && section.items.length > 0 &&
                typeof section.items[0] === 'object' && section.items[0].label && (
                  <div className="space-y-1.5">
                    {section.items.map((item, j) => (
                      <div key={j} className="flex flex-col sm:flex-row sm:items-baseline gap-0.5 sm:gap-2">
                        <span className="text-gray-400 text-xs flex-shrink-0">{item.label}:</span>
                        <code className="text-yellow-300 text-xs bg-corvin-700/60 px-1.5 py-0.5 rounded break-all">
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
        <div className="px-5 py-3 border-t border-corvin-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-corvin-accent text-white text-sm font-medium rounded-lg hover:bg-corvin-accent/90 transition-colors"
          >
            Chiudi
          </button>
        </div>
      </div>
    </div>
  );
}
