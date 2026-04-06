import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { users as usersApi } from '../api/users';
import { audit as auditApi } from '../api/audit';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';

function Tab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
        active ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
      }`}
    >
      {label}
    </button>
  );
}

const ROLE_LABELS = { admin: 'Admin', analyst: 'Analyst', viewer: 'Viewer' };
const ROLE_COLORS = {
  admin:   'text-red-700 bg-red-50 border-red-200',
  analyst: 'text-blue-700 bg-blue-50 border-blue-200',
  viewer:  'text-gray-600 bg-gray-100 border-gray-200',
};

function UsersTab() {
  const { user: currentUser } = useAuth();
  const { data: userList, loading, error, refetch } = useApi(() => usersApi.list());
  const [showInvite, setShowInvite] = useState(false);
  const [form, setForm] = useState({ email: '', full_name: '', temporary_password: '', role: 'viewer' });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [actionError, setActionError] = useState('');

  const isAdmin = currentUser?.role === 'admin';

  const handleInvite = async (e) => {
    e.preventDefault();
    setSaveError('');
    setSaving(true);
    try {
      await usersApi.invite(form);
      setShowInvite(false);
      setForm({ email: '', full_name: '', temporary_password: '', role: 'viewer' });
      refetch();
    } catch (err) {
      setSaveError(err.message ?? 'Errore durante l\'invito.');
    } finally {
      setSaving(false);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    setActionError('');
    try { await usersApi.updateRole(userId, newRole); refetch(); }
    catch (err) { setActionError(err.message ?? 'Errore durante il cambio ruolo.'); }
  };

  const handleDeactivate = async (userId) => {
    if (!window.confirm('Disattivare questo utente? Non potrà più accedere.')) return;
    setActionError('');
    try { await usersApi.deactivate(userId); refetch(); }
    catch (err) { setActionError(err.message ?? 'Errore durante la disattivazione.'); }
  };

  return (
    <div>
      {actionError && <p className="text-red-600 text-sm mb-4">{actionError}</p>}

      {isAdmin && (
        <div className="flex justify-end mb-4">
          <button onClick={() => { setShowInvite((v) => !v); setSaveError(''); }} className={showInvite ? 'btn-secondary' : 'btn-primary'}>
            {showInvite ? '✕ Annulla' : '+ Invita utente'}
          </button>
        </div>
      )}

      {showInvite && (
        <form onSubmit={handleInvite} className="bg-white rounded-xl shadow-card border border-corvin-200 p-4 mb-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
              <input type="email" value={form.email} onChange={(e) => setForm(f => ({...f, email: e.target.value}))} required className="form-input" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Nome completo</label>
              <input type="text" value={form.full_name} onChange={(e) => setForm(f => ({...f, full_name: e.target.value}))} required className="form-input" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Password temporanea</label>
              <input type="password" value={form.temporary_password} onChange={(e) => setForm(f => ({...f, temporary_password: e.target.value}))} required className="form-input" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Ruolo</label>
              <select value={form.role} onChange={(e) => setForm(f => ({...f, role: e.target.value}))} className="form-select w-full">
                <option value="viewer">Viewer</option>
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          {saveError && <p className="text-red-600 text-sm">{saveError}</p>}
          <button type="submit" disabled={saving} className="btn-primary">
            {saving ? 'Invito in corso...' : 'Invia invito'}
          </button>
        </form>
      )}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!loading && (userList ?? []).length === 0 && <EmptyState title="Nessun utente" description="Nessun utente trovato." />}

      {!loading && (userList ?? []).length > 0 && (
        <div className="space-y-2">
          {userList.map((u) => (
            <div key={u.id} className={`bg-white rounded-xl shadow-card border border-corvin-200 px-4 py-3 ${!u.is_active ? 'opacity-50' : ''}`}>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-xs text-blue-700 font-bold flex-shrink-0">
                    {u.full_name?.charAt(0)?.toUpperCase() ?? '?'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-900 font-semibold truncate">{u.full_name}</span>
                      {!u.is_active && <span className="text-xs text-gray-400">(disattivato)</span>}
                      {u.id === currentUser?.id && <span className="text-xs text-blue-600 font-medium">(tu)</span>}
                    </div>
                    <p className="text-xs text-gray-400 truncate">{u.email}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className={`px-2 py-0.5 text-xs rounded-full border font-semibold ${ROLE_COLORS[u.role] ?? ROLE_COLORS.viewer}`}>
                    {ROLE_LABELS[u.role] ?? u.role}
                  </span>
                  {isAdmin && u.id !== currentUser?.id && u.is_active && (
                    <>
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className="form-select text-xs py-1 px-2"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="analyst">Analyst</option>
                        <option value="admin">Admin</option>
                      </select>
                      <button onClick={() => handleDeactivate(u.id)} className="text-xs text-red-500 hover:text-red-700 font-medium">
                        Disattiva
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AuditTab() {
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('');
  const { data, loading, error } = useApi(() => auditApi.list(page, 50, filter), [page, filter]);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 50);

  const ACTION_ICONS = {
    'user.login': '🔑', 'user.register': '📝', 'user.invite': '📨',
    'user.role_change': '👤', 'user.deactivate': '🚫', 'breach.check': '⚠',
    'breach.email_removed': '🗑', 'domain.add': '🌐', 'domain.verified': '✓',
    'scan.create': '🔍', 'sandbox.upload': '📁',
  };

  return (
    <div>
      <div className="flex gap-3 mb-4 items-center">
        <select
          value={filter}
          onChange={(e) => { setFilter(e.target.value); setPage(1); }}
          className="form-select"
        >
          <option value="">Tutte le azioni</option>
          <option value="user.login">Login</option>
          <option value="user.register">Registrazione</option>
          <option value="user.invite">Inviti</option>
          <option value="user.role_change">Cambio ruolo</option>
          <option value="breach.check">Breach check</option>
          <option value="domain.add">Dominio aggiunto</option>
          <option value="domain.verified">Dominio verificato</option>
          <option value="scan.create">Scan creata</option>
          <option value="sandbox.upload">File caricato</option>
        </select>
        <span className="text-sm text-gray-500">{total} eventi trovati</span>
      </div>

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!loading && items.length === 0 && (
        <EmptyState title="Nessun evento" description="Il log di audit apparirà qui con le attività degli utenti." />
      )}

      {!loading && items.length > 0 && (
        <>
          <div className="space-y-1.5">
            {items.map((entry) => (
              <div key={entry.id} className="bg-white rounded-xl shadow-card border border-corvin-200 px-4 py-2.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5 min-w-0">
                    <span className="text-sm flex-shrink-0">{ACTION_ICONS[entry.action] ?? '📋'}</span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="text-xs text-blue-600 font-mono font-semibold">{entry.action}</code>
                        {entry.resource_type && (
                          <span className="text-xs text-gray-400">
                            {entry.resource_type}
                            {entry.resource_id && ` #${entry.resource_id.slice(0, 8)}`}
                          </span>
                        )}
                      </div>
                      {entry.user_email && <p className="text-xs text-gray-500 mt-0.5">{entry.user_email}</p>}
                      {entry.ip_address && <p className="text-xs text-gray-400">IP: {entry.ip_address}</p>}
                      {entry.details && Object.keys(entry.details).length > 0 && (
                        <p className="text-xs text-gray-400 mt-0.5 font-mono">{JSON.stringify(entry.details)}</p>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 flex-shrink-0 whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString('it-IT')}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 mt-4">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-30 font-medium">
                ← Precedente
              </button>
              <span className="text-sm text-gray-500">Pagina {page} di {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-30 font-medium">
                Successiva →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function OrgInfoTab() {
  const { data: orgData, loading } = useApi(() =>
    import('../api/client').then(({ api }) => api.get('/organizations/')),
  );

  if (loading) return <LoadingSpinner />;
  if (!orgData) return <p className="text-gray-500 text-sm">Impossibile caricare i dati dell'organizzazione.</p>;

  return (
    <div className="bg-white rounded-xl shadow-card border border-corvin-200 p-5 max-w-lg">
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Nome organizzazione</label>
          <p className="text-sm text-gray-900 font-semibold">{orgData.name}</p>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Slug</label>
          <code className="text-sm text-gray-700 bg-corvin-100 px-2 py-0.5 rounded border border-corvin-200">{orgData.slug}</code>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Stato</label>
          <SeverityBadge value={orgData.is_active ? 'active' : 'inactive'} />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Creata il</label>
          <p className="text-sm text-gray-700">{new Date(orgData.created_at).toLocaleString('it-IT')}</p>
        </div>
      </div>
    </div>
  );
}

export default function Settings() {
  const [tab, setTab] = useState('users');

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Impostazioni</h1>
        <p className="text-gray-500 text-sm mt-1">Gestione utenti, organizzazione e audit trail</p>
      </div>

      <div className="flex border-b border-corvin-200 mb-6 gap-1">
        <Tab label="Utenti" active={tab === 'users'} onClick={() => setTab('users')} />
        <Tab label="Audit Log" active={tab === 'audit'} onClick={() => setTab('audit')} />
        <Tab label="Organizzazione" active={tab === 'org'} onClick={() => setTab('org')} />
      </div>

      {tab === 'users' && <UsersTab />}
      {tab === 'audit' && <AuditTab />}
      {tab === 'org' && <OrgInfoTab />}
    </div>
  );
}
