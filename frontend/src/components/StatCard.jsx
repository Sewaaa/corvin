import { Link } from 'react-router-dom';

export default function StatCard({ label, value, sub, accent = false, to }) {
  const inner = (
    <>
      <p className="text-sm text-gray-400 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${accent ? 'text-corvin-accent' : 'text-white'}`}>
        {value ?? '—'}
      </p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </>
  );

  const cls = `bg-corvin-800 border rounded-xl p-5 ${accent ? 'border-corvin-accent' : 'border-corvin-700'} ${
    to ? 'hover:border-corvin-accent/60 transition-colors cursor-pointer' : ''
  }`;

  if (to) {
    return <Link to={to} className={`block ${cls}`}>{inner}</Link>;
  }

  return <div className={cls}>{inner}</div>;
}
