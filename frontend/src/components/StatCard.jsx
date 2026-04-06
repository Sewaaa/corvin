import { Link } from 'react-router-dom';

export default function StatCard({ label, value, sub, accent = false, to }) {
  const inner = (
    <>
      <p className="text-sm text-gray-500 mb-1 font-medium">{label}</p>
      <p className={`text-3xl font-bold ${accent ? 'text-red-600' : 'text-gray-900'}`}>
        {value ?? '—'}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-1.5">{sub}</p>}
    </>
  );

  const cls = `bg-white rounded-xl shadow-card border p-5 ${
    accent ? 'border-red-200' : 'border-corvin-200'
  } ${to ? 'hover:shadow-card-md hover:border-blue-300 transition-all cursor-pointer' : ''}`;

  if (to) {
    return <Link to={to} className={`block ${cls}`}>{inner}</Link>;
  }

  return <div className={cls}>{inner}</div>;
}
