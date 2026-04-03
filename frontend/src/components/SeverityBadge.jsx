const SEVERITY_STYLES = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low:      'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info:     'bg-gray-500/20 text-gray-400 border-gray-500/30',
  safe:     'bg-green-500/20 text-green-400 border-green-500/30',
  suspicious: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  malicious:  'bg-red-500/20 text-red-400 border-red-500/30',
  pending:    'bg-gray-500/20 text-gray-400 border-gray-500/30',
  analyzing:  'bg-blue-500/20 text-blue-400 border-blue-500/30',
  completed:  'bg-green-500/20 text-green-400 border-green-500/30',
  running:    'bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse',
  failed:     'bg-red-500/20 text-red-400 border-red-500/30',
};

export default function SeverityBadge({ value }) {
  const key = (value ?? 'info').toLowerCase();
  const style = SEVERITY_STYLES[key] ?? SEVERITY_STYLES.info;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${style}`}>
      {value}
    </span>
  );
}
