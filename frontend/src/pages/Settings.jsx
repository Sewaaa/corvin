import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
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
  const { t } = useSettings();
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
      setSaveError(err.message ?? t('settings.inviteError'));
    } finally {
      setSaving(false);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    setActionError('');
    try { await usersApi.updateRole(userId, newRole); refetch(); }
    catch (err) { setActionError(err.message ?? t('settings.roleError')); }
  };

  const handleDeactivate = async (userId) => {
    if (!window.confirm(t('settings.deactivateConfirm'))) return;
    setActionError('');
    try { await usersApi.deactivate(userId); refetch(); }
    catch (err) { setActionError(err.message ?? t('settings.deactivateError')); }
  };

  return (
    <div>
      {actionError && <p className="text-red-600 text-sm mb-4">{actionError}</p>}

      {isAdmin && (
        <div className="flex justify-end mb-4">
          <button onClick={() => { setShowInvite((v) => !v); setSaveError(''); }} className={showInvite ? 'btn-secondary' : 'btn-primary'}>
            {showInvite ? t('common.cancel') : t('settings.inviteBtn')}
          </button>
        </div>
      )}

      {showInvite && (
        <form onSubmit={handleInvite} className="bg-white rounded-xl shadow-card border border-corvin-200 p-4 mb-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('settings.inviteEmail')}</label>
              <input type="email" value={form.email} onChange={(e) => setForm(f => ({...f, email: e.target.value}))} required className="form-input" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('settings.inviteName')}</label>
              <input type="text" value={form.full_name} onChange={(e) => setForm(f => ({...f, full_name: e.target.value}))} required className="form-input" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('settings.invitePassword')}</label>
              <input type="password" value={form.temporary_password} onChange={(e) => setForm(f => ({...f, temporary_password: e.target.value}))} required className="form-input" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('settings.inviteRole')}</label>
              <select value={form.role} onChange={(e) => setForm(f => ({...f, role: e.target.value}))} className="form-select w-full">
                <option value="viewer">Viewer</option>
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          {saveError && <p className="text-red-600 text-sm">{saveError}</p>}
          <button type="submit" disabled={saving} className="btn-primary">
            {saving ? t('settings.inviting') : t('settings.inviteSend')}
          </button>
        </form>
      )}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!loading && (userList ?? []).length === 0 && <EmptyState title={t('settings.noUsers')} description={t('settings.noUsersDesc')} />}

      {!loading && (userList ?? []).length > 0 && (
        <div className="space-y-2">
          {userList.map((u) => (
            <div key={u.id} className={`bg-white rounded-xl shadow-card border border-corvin-200 px-4 py-3 ${!u.is_active ? 'opacity-50' : ''}`}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-xs text-blue-700 font-bold flex-shrink-0">
                    {u.full_name?.charAt(0)?.toUpperCase() ?? '?'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-900 font-semibold truncate">{u.full_name}</span>
                      {!u.is_active && <span className="text-xs text-gray-400">{t('settings.deactivated')}</span>}
                      {u.id === currentUser?.id && <span className="text-xs text-blue-600 font-medium">{t('settings.you')}</span>}
                    </div>
                    <p className="text-xs text-gray-400 truncate">{u.email}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap flex-shrink-0">
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
                        {t('settings.deactivate')}
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
  const { t } = useSettings();
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
          <option value="">{t('settings.allActions')}</option>
          <option value="user.login">{t('settings.auditLogin')}</option>
          <option value="user.register">{t('settings.auditRegister')}</option>
          <option value="user.invite">{t('settings.auditInvite')}</option>
          <option value="user.role_change">{t('settings.auditRole')}</option>
          <option value="breach.check">{t('settings.auditBreach')}</option>
          <option value="domain.add">{t('settings.auditDomainAdd')}</option>
          <option value="domain.verified">{t('settings.auditDomainVerify')}</option>
          <option value="scan.create">{t('settings.auditScan')}</option>
          <option value="sandbox.upload">{t('settings.auditUpload')}</option>
        </select>
        <span className="text-sm text-gray-500">{t('settings.eventsFound', { count: total })}</span>
      </div>

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!loading && items.length === 0 && (
        <EmptyState title={t('settings.noEvents')} description={t('settings.noEventsDesc')} />
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
                {t('settings.prevPage')}
              </button>
              <span className="text-sm text-gray-500">{t('settings.pageOf', { page, total: totalPages })}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-30 font-medium">
                {t('settings.nextPage')}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function OrgInfoTab() {
  const { t } = useSettings();
  const { data: orgData, loading } = useApi(() =>
    import('../api/client').then(({ api }) => api.get('/organizations/')),
  );

  if (loading) return <LoadingSpinner />;
  if (!orgData) return <p className="text-gray-500 text-sm">{t('settings.orgError')}</p>;

  return (
    <div className="bg-white rounded-xl shadow-card border border-corvin-200 p-5 max-w-lg">
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{t('settings.orgName')}</label>
          <p className="text-sm text-gray-900 font-semibold">{orgData.name}</p>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{t('settings.orgSlug')}</label>
          <code className="text-sm text-gray-700 bg-corvin-100 px-2 py-0.5 rounded border border-corvin-200">{orgData.slug}</code>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{t('settings.orgStatus')}</label>
          <SeverityBadge value={orgData.is_active ? 'active' : 'inactive'} />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{t('settings.orgCreated')}</label>
          <p className="text-sm text-gray-700">{new Date(orgData.created_at).toLocaleString('it-IT')}</p>
        </div>
      </div>
    </div>
  );
}

export default function Settings() {
  const { t } = useSettings();
  const [tab, setTab] = useState('users');

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('settings.title')}</h1>
        <p className="text-gray-500 text-sm mt-1">{t('settings.subtitle')}</p>
      </div>

      <div className="flex border-b border-corvin-200 mb-6 gap-1">
        <Tab label={t('settings.tabUsers')} active={tab === 'users'} onClick={() => setTab('users')} />
        <Tab label={t('settings.tabAudit')} active={tab === 'audit'} onClick={() => setTab('audit')} />
        <Tab label={t('settings.tabOrg')} active={tab === 'org'} onClick={() => setTab('org')} />
      </div>

      {tab === 'users' && <UsersTab />}
      {tab === 'audit' && <AuditTab />}
      {tab === 'org' && <OrgInfoTab />}
    </div>
  );
}
