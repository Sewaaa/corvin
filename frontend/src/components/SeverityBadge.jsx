const SEVERITY_CONFIG = {
  critical:   { style: 'bg-red-50 text-red-700 border-red-200',       label: 'Critico' },
  high:       { style: 'bg-orange-50 text-orange-700 border-orange-200', label: 'Alto' },
  medium:     { style: 'bg-amber-50 text-amber-700 border-amber-200',  label: 'Medio' },
  low:        { style: 'bg-blue-50 text-blue-700 border-blue-200',     label: 'Basso' },
  info:       { style: 'bg-gray-100 text-gray-600 border-gray-200',    label: 'Info' },
  safe:       { style: 'bg-green-50 text-green-700 border-green-200',  label: 'Sicuro' },
  suspicious: { style: 'bg-amber-50 text-amber-700 border-amber-200',  label: 'Sospetto' },
  malicious:  { style: 'bg-red-50 text-red-700 border-red-200',        label: 'Malevolo' },
  pending:    { style: 'bg-gray-100 text-gray-500 border-gray-200',    label: 'In attesa' },
  analyzing:  { style: 'bg-blue-50 text-blue-700 border-blue-200',     label: 'Analisi' },
  completed:  { style: 'bg-green-50 text-green-700 border-green-200',  label: 'Completato' },
  running:    { style: 'bg-blue-50 text-blue-700 border-blue-200 animate-pulse', label: 'In corso' },
  failed:     { style: 'bg-red-50 text-red-700 border-red-200',        label: 'Fallito' },
  verified:   { style: 'bg-green-50 text-green-700 border-green-200',  label: 'Verificato' },
  unverified: { style: 'bg-gray-100 text-gray-500 border-gray-200',    label: 'Da verificare' },
  active:     { style: 'bg-green-50 text-green-700 border-green-200',  label: 'Attivo' },
  inactive:   { style: 'bg-gray-100 text-gray-500 border-gray-200',    label: 'Inattivo' },
};

const FALLBACK = { style: 'bg-gray-100 text-gray-600 border-gray-200', label: null };

export default function SeverityBadge({ value }) {
  const key = (value ?? 'info').toLowerCase();
  const config = SEVERITY_CONFIG[key] ?? FALLBACK;
  const displayLabel = config.label ?? value;

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-xs font-semibold ${config.style}`}>
      {displayLabel}
    </span>
  );
}
