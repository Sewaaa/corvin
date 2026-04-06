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
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        active ? 'border-corvin-accent text-white' : 'border-transparent text-gray-400 hover:text-white'
      }`}
    >
      {label}
    </button>
  );
}

const ROLE_LABELS = { admin: 'Admin', analyst: 'Analyst', viewer: 'Viewer' };
const ROLE_COLORS = {
  admin: 'text-red-400 bg-red-900/30 border-red-800',
  analyst: 'text-corvin-accent bg-corvin-accent/10 border-corvin-accent/30',
  viewer: 'text-gray-400 bg-corvin-700/40 border-corvin-600',
};

// ── Users tab ────────────────────────────────────────────────────────────────
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
    try {
      await usersApi.updateRole(userId, newRole);
      refetch();
    } catch (err) {
      setActionError(err.message ?? 'Errore durante il cambio ruolo.');
    }
  };

  const handleDeactivate = async (userId) => {
    if (!window.confirm('Disattivare questo utente? Non potrà più accedere.')) return;
    setActionError('');
    try {
      await usersApi.deactivate(userId);
      refetch();
    } catch (err) {
      setActionError(err.message ?? 'Errore durante la disattivazione.');
    }
  };

  return (
    <div>
      {actionError && <p className="text-red-400 text-sm mb-4">{actionError}</p>}

      {/* Invite button */}
      {isAdmin && (
        <div className="flex justify-end mb-4">
          <button
            onClick={() => { setShowInvite((v) => !v); setSaveError(''); }}
            className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg"
          >
            {showInvite ? '✕ Annulla' : '+ Invita utente'}
          </button>
        </div>
      )}

      {/* Invite form */}
      {showInvite && (
        <form onSubmit={handleInvite} className="bg-corvin-800 border border-corvin-700 rounded-xl p-4 mb-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Email</label>
              <input type="email" value={form.email} onChange={(e) => setForm(f => ({...f, email: e.target.value}))}
                required className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Nome completo</label>
              <input type="text" value={form.full_name} onChange={(e) => setForm(f => ({...f, full_name: e.target.value}))}
                required className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Password temporanea</label>
              <input type="password" value={form.temporary_password} onChange={(e) => setForm(f => ({...f, temporary_password: e.target.value}))}
                required className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Ruolo</label>
              <select value={form.role} onChange={(e) => setForm(f => ({...f, role: e.target.value}))}
                className="w-full bg-corvin-700 border border-corvin-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent">
                <option value="viewer">Viewer</option>
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          {saveError && <p className="text-red-400 text-sm">{saveError}</p>}
          <button type="submit" disabled={saving}
            className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg disabled:opacity-50">
            {saving ? 'Invito in corso...' : 'Invia invito'}
          </button>
        </form>
      )}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && (userList ?? []).length === 0 && (
        <EmptyState title="Nessun utente" description="Nessun utente trovato." />
      )}

      {!loading && (userList ?? []).length > 0 && (
        <div className="space-y-2">
          {userList.map((u) => (
            <div key={u.id} className={`bg-corvin-800 border rounded-xl px-4 py-3 ${
              u.is_active ? 'border-corvin-700' : 'border-corvin-700/50 opacity-50'
            }`}>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-full bg-corvin-700 flex items-center justify-center text-xs text-gray-400 font-medium flex-shrink-0">
                    {u.full_name?.charAt(0)?.toUpperCase() ?? '?'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-white font-medium truncate">{u.full_name}</span>
                      {!u.is_active && <span className="text-xs text-gray-500">(disattivato)</span>}
                      {u.id === currentUser?.id && <span className="text-xs text-corvin-accent">(tu)</span>}
                    </div>
                    <p className="text-xs text-gray-500 truncate">{u.email}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className={`px-2 py-0.5 text-xs rounded-full border ${ROLE_COLORS[u.role] ?? ROLE_COLORS.viewer}`}>
                    {ROLE_LABELS[u.role] ?? u.role}
                  </span>

                  {isAdmin && u.id !== currentUser?.id && u.is_active && (
                    <>
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className="bg-corvin-700 border border-corvin-600 rounded px-2 py-1 text-xs text-white"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="analyst">Analyst</option>
                        <option value="admin">Admin</option>
                      </select>
                      <button
                        onClick={() => handleDeactivate(u.id)}
                        className="text-xs text-red-400 hover:underline"
                      >
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

// ── Audit Log tab ────────────────────────────────────────────────────────────
function AuditTab() {
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('');
  const { data, loading, error } = useApi(
    () => auditApi.list(page, 50, filter),
    [page, filter],
  );

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 50);

  const ACTION_ICONS = {
    'user.login': '🔑',
    'user.register': '📝',
    'user.invite': '📨',
    'user.role_change': '👤',
    'user.deactivate': '🚫',
    'breach.check': '⚠',
    'breach.email_removed': '🗑',
    'domain.add': '🌐',
    'domain.verified': '✓',
    'scan.create': '🔍',
    'sandbox.upload': '📁',
  };

  return (
    <div>
      {/* Filter */}
      <div className="flex gap-3 mb-4">
        <select
          value={filter}
          onChange={(e) => { setFilter(e.target.value); setPage(1); }}
          className="bg-corvin-800 border border-corvin-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-corvin-accent"
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
        <span className="text-xs text-gray-500 self-center">{total} eventi trovati</span>
      </div>

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && items.length === 0 && (
        <EmptyState title="Nessun evento" description="Il log di audit apparirà qui con le attività degli utenti." />
      )}

      {!loading && items.length > 0 && (
        <>
          <div className="space-y-1.5">
            {items.map((entry) => (
              <div key={entry.id} className="bg-corvin-800 border border-corvin-700 rounded-lg px-4 py-2.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="text-sm flex-shrink-0">{ACTION_ICONS[entry.action] ?? '📋'}</span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="text-xs text-corvin-accent font-mono">{entry.action}</code>
                        {entry.resource_type && (
                          <span className="text-xs text-gray-500">
                            {entry.resource_type}
                            {entry.resource_id && ` #${entry.resource_id.slice(0, 8)}`}
                          </span>
                        )}
                      </div>
                      {entry.user_email && (
                        <p className="text-xs text-gray-400 mt-0.5">{entry.user_email}</p>
                      )}
                      {entry.ip_address && (
                        <p className="text-xs text-gray-600">IP: {entry.ip_address}</p>
                      )}
                      {entry.details && Object.keys(entry.details).length > 0 && (
                        <p className="text-xs text-gray-600 mt-0.5 font-mono">
                          {JSON.stringify(entry.details)}
                        </p>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-gray-600 flex-shrink-0 whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString('it-IT')}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="text-xs text-gray-400 hover:text-white disabled:opacity-30"
              >
                ← Precedente
              </button>
              <span className="text-xs text-gray-500">
                Pagina {page} di {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="text-xs text-gray-400 hover:text-white disabled:opacity-30"
              >
                Successiva →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Org Info tab ─────────────────────────────────────────────────────────────
function OrgInfoTab() {
  const { data: orgData, loading } = useApi(() =>
    import('../api/client').then(({ api }) => api.get('/organizations/')),
  );

  if (loading) return <LoadingSpinner />;
  if (!orgData) return <p className="text-gray-500 text-sm">Impossibile caricare i dati dell'organizzazione.</p>;

  return (
    <div className="bg-corvin-800 border border-corvin-700 rounded-xl p-5 max-w-lg">
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Nome organizzazione</label>
          <p className="text-sm text-white font-medium">{orgData.name}</p>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Slug</label>
          <code className="text-sm text-gray-300 bg-corvin-700/40 px-2 py-0.5 rounded">{orgData.slug}</code>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Stato</label>
          <SeverityBadge value={orgData.is_active ? 'active' : 'inactive'} />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Creata il</label>
          <p className="text-sm text-gray-300">{new Date(orgData.created_at).toLocaleString('it-IT')}</p>
        </div>
      </div>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function Settings() {
  const [tab, setTab] = useState('users');

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Impostazioni</h1>
        <p className="text-gray-400 text-sm mt-1">Gestione utenti, organizzazione e audit trail</p>
      </div>

      <div className="flex border-b border-corvin-700 mb-6 gap-1">
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
