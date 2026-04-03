import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { reports as reportsApi } from '../api/reports';
import LoadingSpinner from '../components/LoadingSpinner';
import StatCard from '../components/StatCard';

function SectionCard({ title, children }) {
  return (
    <div className="bg-corvin-800 border border-corvin-700 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-corvin-accent uppercase tracking-wider mb-4">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value, highlight = false }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-corvin-700/40 last:border-0">
      <span className="text-sm text-gray-400">{label}</span>
      <span className={`text-sm font-medium ${highlight ? 'text-red-400' : 'text-white'}`}>{value ?? '—'}</span>
    </div>
  );
}

function SeverityRows({ data }) {
  const colors = { critical: 'text-red-400', high: 'text-orange-400', medium: 'text-yellow-400', low: 'text-blue-400', info: 'text-gray-400' };
  return Object.entries(data).map(([sev, count]) => (
    <div key={sev} className="flex items-center justify-between py-1.5 border-b border-corvin-700/40 last:border-0">
      <span className="text-sm text-gray-400 capitalize">{sev}</span>
      <span className={`text-sm font-medium ${colors[sev] ?? 'text-white'}`}>{count}</span>
    </div>
  ));
}

export default function Reports() {
  const { data: summary, loading, error, refetch } = useApi(() => reportsApi.summary());
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');

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
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Reports</h1>
          <p className="text-gray-400 text-sm mt-1">
            Riepilogo aggregato da tutti i moduli
            {summary && (
              <span className="ml-2 text-gray-600">
                · generato {new Date(summary.generated_at).toLocaleString('it-IT')}
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={refetch}
            className="px-3 py-2 text-sm text-gray-400 hover:text-white border border-corvin-700 rounded-lg transition-colors"
          >
            ↻ Aggiorna
          </button>
          <button
            onClick={handleDownload}
            disabled={downloading || loading}
            className="px-4 py-2 bg-corvin-accent text-white text-sm font-medium rounded-lg hover:bg-corvin-accent/90 disabled:opacity-50 flex items-center gap-2"
          >
            {downloading ? (
              <>
                <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                Generazione…
              </>
            ) : (
              '↓ Scarica PDF'
            )}
          </button>
        </div>
      </div>

      {downloadError && (
        <p className="text-red-400 text-sm mb-4">{downloadError}</p>
      )}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {summary && (
        <>
          {/* Top stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard
              label="Email monitorate"
              value={summary.breach_monitor.monitored_emails}
              sub={`${summary.breach_monitor.breached_emails} compromesse`}
              accent={summary.breach_monitor.breached_emails > 0}
            />
            <StatCard
              label="Domini"
              value={summary.domain_reputation.total_domains}
              sub={`Score medio: ${summary.domain_reputation.average_score ?? '—'}`}
            />
            <StatCard
              label="Minacce email"
              value={summary.email_protection.total_threats}
              sub={`${summary.email_protection.critical_threats} critiche`}
              accent={summary.email_protection.critical_threats > 0}
            />
            <StatCard
              label="File malicious"
              value={summary.file_sandbox.by_status?.malicious ?? 0}
              sub={`${summary.file_sandbox.total_files} file totali`}
              accent={(summary.file_sandbox.by_status?.malicious ?? 0) > 0}
            />
          </div>

          {/* Module detail cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            <SectionCard title="Breach Monitor">
              <Row label="Email monitorate" value={summary.breach_monitor.monitored_emails} />
              <Row label="Email compromesse" value={summary.breach_monitor.breached_emails}
                highlight={summary.breach_monitor.breached_emails > 0} />
              <Row label="Breach rate" value={`${summary.breach_monitor.breach_rate_pct}%`}
                highlight={summary.breach_monitor.breach_rate_pct > 0} />
              <Row label="Breach records totali" value={summary.breach_monitor.total_breach_records} />
            </SectionCard>

            <SectionCard title="Domain Reputation">
              <Row label="Domini monitorati" value={summary.domain_reputation.total_domains} />
              <Row label="Domini verificati" value={summary.domain_reputation.verified_domains} />
              <Row label="Punteggio medio" value={summary.domain_reputation.average_score ?? '—'} />
            </SectionCard>

            <SectionCard title="Web Scanner">
              <Row label="Scansioni totali" value={summary.web_scanner.total_scans} />
              <Row label="Completate" value={summary.web_scanner.completed_scans} />
              <Row label="Finding totali" value={summary.web_scanner.total_findings} />
              <div className="mt-2 pt-2 border-t border-corvin-700/40">
                <p className="text-xs text-gray-500 mb-1">Per severity</p>
                <SeverityRows data={summary.web_scanner.findings_by_severity} />
              </div>
            </SectionCard>

            <SectionCard title="Email Protection">
              <Row label="Account monitorati" value={summary.email_protection.monitored_accounts} />
              <Row label="Minacce totali" value={summary.email_protection.total_threats} />
              <Row label="Critiche" value={summary.email_protection.critical_threats}
                highlight={summary.email_protection.critical_threats > 0} />
              <Row label="In quarantena" value={summary.email_protection.quarantined} />
            </SectionCard>

            <SectionCard title="File Sandbox">
              <Row label="File analizzati" value={summary.file_sandbox.total_files} />
              {Object.entries(summary.file_sandbox.by_status ?? {}).map(([st, count]) => (
                <Row key={st} label={st.charAt(0).toUpperCase() + st.slice(1)} value={count}
                  highlight={st === 'malicious' && count > 0} />
              ))}
            </SectionCard>

            <SectionCard title="Notifications">
              <Row label="Totali" value={summary.notifications.total} />
              <Row label="Non lette" value={summary.notifications.unread}
                highlight={summary.notifications.unread > 0} />
              <div className="mt-2 pt-2 border-t border-corvin-700/40">
                <p className="text-xs text-gray-500 mb-1">Per severity</p>
                <SeverityRows data={summary.notifications.by_severity} />
              </div>
            </SectionCard>
          </div>
        </>
      )}
    </div>
  );
}
