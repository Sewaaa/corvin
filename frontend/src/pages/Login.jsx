import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [form, setForm] = useState({
    email: '', password: '', full_name: '', organization_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(form.email, form.password);
      } else {
        await register({
          email: form.email,
          password: form.password,
          full_name: form.full_name,
          organization_name: form.organization_name,
        });
      }
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-corvin-900 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-corvin-accent">Corvin</h1>
          <p className="text-gray-400 text-sm mt-1">Silent guardian for your digital perimeter.</p>
        </div>

        <div className="bg-corvin-800 border border-corvin-700 rounded-xl p-6">
          <div className="flex mb-6 bg-corvin-700/50 rounded-lg p-1">
            {['login', 'register'].map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); }}
                className={`flex-1 py-1.5 text-sm rounded-md transition-colors ${
                  mode === m ? 'bg-corvin-accent text-white font-medium' : 'text-gray-400 hover:text-white'
                }`}
              >
                {m === 'login' ? 'Accedi' : 'Registrati'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <>
                <Field label="Nome completo" value={form.full_name} onChange={set('full_name')} required />
                <Field label="Nome organizzazione" value={form.organization_name} onChange={set('organization_name')} required />
              </>
            )}
            <Field label="Email" type="email" value={form.email} onChange={set('email')} required />
            <Field label="Password" type="password" value={form.password} onChange={set('password')} required />

            {error && (
              <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-corvin-accent hover:bg-corvin-accent/90 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? 'Caricamento…' : mode === 'login' ? 'Accedi' : 'Crea account'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Field({ label, type = 'text', value, onChange, required }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-corvin-accent transition-colors"
      />
    </div>
  );
}
