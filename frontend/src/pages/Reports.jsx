import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { reports as reportsApi } from '../api/reports';
import { useSettings } from '../context/SettingsContext';
import LoadingSpinner from '../components/LoadingSpinner';
import StatCard from '../components/StatCard';
import InfoModal from '../components/InfoModal';

const INFO_SECTIONS = [
  {
    heading: 'Cos\'è',
    text: 'Reports aggrega i dati da tutti i moduli in un\'unica vista di sintesi: email monitorate, domini, minacce email, file analizzati, notifiche. Permette anche di scaricare un report PDF completo.',
  },
  {
    heading: 'Come si usa',
    items: [
      'La pagina si carica automaticamente con il sommario aggiornato.',
      'Clicca <strong>↻ Aggiorna</strong> per ricaricare i dati in tempo reale.',
      'Clicca <strong>↓ Scarica PDF</strong> per generare e scaricare un report completo.',
      'Il PDF include tutti i moduli con severity breakdown e timestamp di generazione.',
    ],
  },
  {
    heading: 'Dati nel PDF',
    items: [
      'Breach Monitor: email monitorate, compromesse, nomi breach.',
      'Domain Reputation: domini, punteggi, finding.',
      'Web Scanner: scansioni, finding per severity.',
      'Email Protection: account, minacce, in quarantena.',
      'File Sandbox: file analizzati, distribuzione per stato.',
      'Notifications: totale alert per severity.',
    ],
  },
];

function SectionCard({ title, children }) {
  return (
    <div className="bg-white rounded-xl shadow-card border border-corvin-200 p-5">
      <h3 className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-4">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value, highlight = false }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-corvin-100 last:border-0">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={`text-sm font-semibold ${highlight ? 'text-red-600' : 'text-gray-900'}`}>{value ?? '—'}</span>
    </div>
  );
}

const SEV_COLORS = { critical: 'text-red-600', high: 'text-orange-600', medium: 'text-amber-600', low: 'text-blue-600', info: 'text-gray-500' };

function SeverityRows({ data }) {
  return Object.entries(data).map(([sev, count]) => (
    <div key={sev} className="flex items-center justify-between py-2 border-b border-corvin-100 last:border-0">
      <span className="text-sm text-gray-500 capitalize">{sev}</span>
      <span className={`text-sm font-semibold ${SEV_COLORS[sev] ?? 'text-gray-900'}`}>{count}</span>
    </div>
  ));
}

export default function Reports() {
  const { t } = useSettings();
  const { data: summary, loading, error, refetch } = useApi(() => reportsApi.summary());
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');
  const [showInfo, setShowInfo] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    setDownloadError('');
    try {
      await reportsApi.downloadPdf();
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div>
      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} title="Reports — Guida" sections={INFO_SECTIONS} />

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('report.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">
            {t('report.subtitle')}
            {summary && (
              <span className="ml-2 text-gray-400">
                {t('report.generated')} {new Date(summary.generated_at).toLocaleString('it-IT')}
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => setShowInfo(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>
            {t('common.guide')}
          </button>
          <button onClick={refetch} className="btn-secondary">{t('report.refresh')}</button>
          <button onClick={handleDownload} disabled={downloading || loading} className="btn-primary flex items-center gap-2">
            {downloading ? (
              <><span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />{t('report.downloading')}</>
            ) : t('report.download')}
          </button>
        </div>
      </div>

      {downloadError && <p className="text-red-600 text-sm mb-4">{downloadError}</p>}
      {loading && <LoadingSpinner />}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {summary && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard label={t('report.stat.emails')} value={summary.breach_monitor.monitored_emails} sub={t('report.stat.emailsSub', { count: summary.breach_monitor.breached_emails })} accent={summary.breach_monitor.breached_emails > 0} />
            <StatCard label={t('report.stat.domains')} value={summary.domain_reputation.total_domains} sub={t('report.stat.domainsSub', { score: summary.domain_reputation.average_score ?? '—' })} />
            <StatCard label={t('report.stat.threats')} value={summary.email_protection.total_threats} sub={t('report.stat.threatsSub', { count: summary.email_protection.critical_threats })} accent={summary.email_protection.critical_threats > 0} />
            <StatCard label={t('report.stat.files')} value={summary.file_sandbox.by_status?.malicious ?? 0} sub={t('report.stat.filesSub', { count: summary.file_sandbox.total_files })} accent={(summary.file_sandbox.by_status?.malicious ?? 0) > 0} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SectionCard title={t('report.section.breach')}>
              <Row label={t('report.row.monitoredEmails')} value={summary.breach_monitor.monitored_emails} />
              <Row label={t('report.row.breachedEmails')} value={summary.breach_monitor.breached_emails} highlight={summary.breach_monitor.breached_emails > 0} />
              <Row label={t('report.row.breachRate')} value={`${summary.breach_monitor.breach_rate_pct}%`} highlight={summary.breach_monitor.breach_rate_pct > 0} />
              <Row label={t('report.row.totalBreachRecords')} value={summary.breach_monitor.total_breach_records} />
            </SectionCard>

            <SectionCard title={t('report.section.domain')}>
              <Row label={t('report.row.monitoredDomains')} value={summary.domain_reputation.total_domains} />
              <Row label={t('report.row.verifiedDomains')} value={summary.domain_reputation.verified_domains} />
              <Row label={t('report.row.averageScore')} value={summary.domain_reputation.average_score ?? '—'} />
            </SectionCard>

            <SectionCard title={t('report.section.scanner')}>
              <Row label={t('report.row.totalScans')} value={summary.web_scanner.total_scans} />
              <Row label={t('report.row.completedScans')} value={summary.web_scanner.completed_scans} />
              <Row label={t('report.row.totalFindings')} value={summary.web_scanner.total_findings} />
              <div className="mt-2 pt-2 border-t border-corvin-100">
                <p className="text-xs text-gray-400 mb-1 font-medium">{t('report.row.bySeverity')}</p>
                <SeverityRows data={summary.web_scanner.findings_by_severity} />
              </div>
            </SectionCard>

            <SectionCard title={t('report.section.email')}>
              <Row label={t('report.row.monitoredAccounts')} value={summary.email_protection.monitored_accounts} />
              <Row label={t('report.row.totalThreats')} value={summary.email_protection.total_threats} />
              <Row label={t('report.row.criticalThreats')} value={summary.email_protection.critical_threats} highlight={summary.email_protection.critical_threats > 0} />
              <Row label={t('report.row.quarantined')} value={summary.email_protection.quarantined} />
            </SectionCard>

            <SectionCard title={t('report.section.sandbox')}>
              <Row label={t('report.row.analyzedFiles')} value={summary.file_sandbox.total_files} />
              {Object.entries(summary.file_sandbox.by_status ?? {}).map(([st, count]) => (
                <Row key={st} label={st.charAt(0).toUpperCase() + st.slice(1)} value={count} highlight={st === 'malicious' && count > 0} />
              ))}
            </SectionCard>

            <SectionCard title={t('report.section.notifications')}>
              <Row label={t('report.row.total')} value={summary.notifications.total} />
              <Row label={t('report.row.unread')} value={summary.notifications.unread} highlight={summary.notifications.unread > 0} />
              <div className="mt-2 pt-2 border-t border-corvin-100">
                <p className="text-xs text-gray-400 mb-1 font-medium">{t('report.row.bySeverity')}</p>
                <SeverityRows data={summary.notifications.by_severity} />
              </div>
            </SectionCard>
          </div>
        </>
      )}
    </div>
  );
}
