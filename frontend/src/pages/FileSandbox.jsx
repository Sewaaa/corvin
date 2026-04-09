import { useState, useRef } from 'react';
import { useApi } from '../hooks/useApi';
import { sandbox as sandboxApi } from '../api/sandbox';
import { useSettings } from '../context/SettingsContext';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';
import InfoModal from '../components/InfoModal';
import ErrorBanner from '../components/ErrorBanner';

const INFO_SECTIONS = [
  {
    heading: 'Cos\'è',
    text: 'File Sandbox esegue analisi statica su file caricati: matching di regole YARA, lookup dell\'hash SHA-256 su VirusTotal, calcolo dell\'entropia (indicatore di packing/cifratura) e parsing PE per i file Windows.',
  },
  {
    heading: 'Come si usa',
    items: [
      'Trascina un file nella drop zone oppure clicca per selezionarlo.',
      'L\'analisi parte in background: attendi che lo stato passi da <em>analisi</em> a un risultato.',
      'Il risultato può essere: <strong>Sicuro</strong>, <strong>Sospetto</strong> o <strong>Malevolo</strong>.',
      'Clicca su un file per vedere i dettagli: match YARA, score VirusTotal, entropia.',
    ],
  },
  {
    heading: 'File di test consigliati',
    items: [
      { label: 'File sicuro', value: 'qualsiasi .txt, .pdf o immagine comune' },
      { label: 'EICAR test string', value: 'crea un .txt con la stringa EICAR per testare i matching AV' },
      { label: 'PDF con macro', value: 'upload di un PDF con JavaScript inline → suspicious' },
      { label: 'Max dimensione', value: '10 MB per file' },
    ],
  },
  {
    heading: 'Formati supportati',
    items: [
      'Tutti i tipi di file (analisi generica: hash + entropia + YARA).',
      'File PE (.exe, .dll) → parsing header, sezioni, imports.',
      'Archivi ZIP → analisi del contenuto (se non cifrati).',
      'Script (.ps1, .bat, .js, .vbs) → pattern matching YARA.',
    ],
  },
];

function DropZone({ onFile, t }) {
  const [drag, setDrag] = useState(false);
  const input = useRef();

  const handle = (file) => { if (file) onFile(file); };

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer mb-6 ${
        drag
          ? 'border-blue-500 bg-blue-50'
          : 'border-corvin-200 hover:border-blue-300 hover:bg-corvin-50 bg-white'
      }`}
      onClick={() => input.current.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]); }}
    >
      <input ref={input} type="file" className="hidden" onChange={(e) => handle(e.target.files[0])} />
      <div className="flex flex-col items-center gap-2">
        <svg className={`w-8 h-8 ${drag ? 'text-blue-500' : 'text-gray-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <p className="text-sm text-gray-600" dangerouslySetInnerHTML={{ __html: t('sandbox.dropHint') }} />
        <p className="text-xs text-gray-400">{t('sandbox.dropSub')}</p>
      </div>
    </div>
  );
}

function YaraMatches({ matches, t }) {
  if (!matches?.length) return <p className="text-xs text-gray-500">{t('sandbox.yaraEmpty')}</p>;
  return (
    <div className="space-y-1">
      {matches.map((m, i) => (
        <div key={i} className="flex items-center gap-2">
          <SeverityBadge value={m.severity} />
          <span className="text-xs text-gray-900 font-medium">{m.rule}</span>
          <span className="text-xs text-gray-500">· {m.description}</span>
        </div>
      ))}
    </div>
  );
}

export default function FileSandbox() {
  const { t } = useSettings();
  const { user } = useAuth();
  const isViewer = user?.role === 'viewer';
  const { data: files, loading, error, refetch } = useApi(() => sandboxApi.list());
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [detail, setDetail] = useState(null);
  const [showInfo, setShowInfo] = useState(false);
  const [removingId, setRemovingId] = useState(null);

  const handleFile = async (file) => {
    setUploadError('');
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const uploaded = await sandboxApi.upload(fd);
      refetch();
      if (uploaded?.id) {
        for (let i = 0; i < 15; i++) {
          await new Promise((r) => setTimeout(r, 3000));
          const updated = await refetch();
          const found = (updated ?? []).find((f) => f.id === uploaded.id);
          if (found && found.status !== 'pending' && found.status !== 'analyzing') break;
        }
      }
    } catch (err) {
      const msg = err.message ?? '';
      if (msg.includes('troppo grande') || msg.includes('413')) {
        setUploadError(t('sandbox.tooLarge'));
      } else if (msg.includes('non supportato') || msg.includes('415')) {
        setUploadError(t('sandbox.unsupported'));
      } else {
        setUploadError(err.message ?? t('sandbox.uploadError'));
      }
    } finally {
      setUploading(false);
    }
  };

  const handleDetail = async (id) => {
    if (detail?.id === id) { setDetail(null); return; }
    try { setDetail(await sandboxApi.get(id)); } catch {}
  };

  const handleRemove = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm(t('sandbox.removeConfirm'))) return;
    setRemovingId(id);
    try {
      await sandboxApi.remove(id);
      if (detail?.id === id) setDetail(null);
      await refetch();
    } catch (err) {
      setUploadError(err.message ?? t('sandbox.removeError'));
    } finally {
      setRemovingId(null);
    }
  };

  const formatSize = (b) =>
    b > 1_048_576 ? `${(b / 1_048_576).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`;

  return (
    <div>
      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} title="File Sandbox — Guida" sections={INFO_SECTIONS} />

      <div className="flex items-start justify-between flex-wrap gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('sandbox.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('sandbox.subtitle')}</p>
        </div>
        <button onClick={() => setShowInfo(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path strokeLinecap="round" d="M12 16v-4M12 8h.01" /></svg>
          {t('common.guide')}
        </button>
      </div>

      {!isViewer && <DropZone onFile={handleFile} t={t} />}
      {uploading && (
        <div className="flex items-center gap-2 text-sm text-blue-600 mb-4 animate-pulse">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
          {t('sandbox.uploading')}
        </div>
      )}
      {uploadError && <ErrorBanner message={uploadError} className="mb-4" />}

      {loading && <LoadingSpinner />}
      {error && <ErrorBanner message={error} />}

      {!loading && files?.length === 0 && (
        <EmptyState title={t('sandbox.emptyTitle')} description={t('sandbox.emptyDesc')} />
      )}

      {!loading && files?.length > 0 && (
        <div className="space-y-2">
          {files.map((f) => (
            <div key={f.id} className="bg-white rounded-xl shadow-card border border-corvin-200">
              <div
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-corvin-50 rounded-xl"
                onClick={() => handleDetail(f.id)}
              >
                <div className="flex items-center gap-3">
                  <SeverityBadge value={f.status} />
                  <span className="text-sm text-gray-900 font-medium font-mono">{f.original_filename}</span>
                  <span className="text-xs text-gray-400">{formatSize(f.file_size)}</span>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs text-gray-400 hidden sm:inline">{new Date(f.created_at).toLocaleString('it-IT')}</span>
                  <button
                    onClick={(e) => handleRemove(e, f.id)}
                    disabled={removingId === f.id}
                    className="text-xs text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
                  >
                    {removingId === f.id ? '...' : '✕'}
                  </button>
                </div>
              </div>

              {detail?.id === f.id && (
                <div className="border-t border-corvin-100 px-4 py-3 space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-gray-500 font-medium">{t('sandbox.sha256')} </span>
                      <code className="text-gray-700 break-all">{detail.sha256_hash}</code>
                    </div>
                    <div>
                      <span className="text-gray-500 font-medium">{t('sandbox.mime')} </span>
                      <span className="text-gray-900">{detail.mime_type ?? '—'}</span>
                    </div>
                    {detail.metadata_extracted?.entropy != null && (
                      <div>
                        <span className="text-gray-500 font-medium">{t('sandbox.entropy')} </span>
                        <span className={detail.metadata_extracted.high_entropy ? 'text-red-600 font-semibold' : 'text-gray-900'}>
                          {detail.metadata_extracted.entropy}
                          {detail.metadata_extracted.high_entropy && ` ${t('sandbox.entropyHigh')}`}
                        </span>
                      </div>
                    )}
                    {detail.virustotal_result && (
                      <div>
                        <span className="text-gray-500 font-medium">{t('sandbox.vt')} </span>
                        <span className={detail.virustotal_result.detections > 0 ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'}>
                          {detail.virustotal_result.status === 'not_found'
                            ? t('sandbox.vtNotFound')
                            : `${detail.virustotal_result.detections}/${detail.virustotal_result.total}`}
                        </span>
                      </div>
                    )}
                  </div>

                  <div>
                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1.5">{t('sandbox.yaraTitle')}</p>
                    <YaraMatches matches={detail.yara_matches} t={t} />
                  </div>

                  {detail.metadata_extracted?.suspicious_strings?.length > 0 && (
                    <div>
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1.5">{t('sandbox.suspStrings')}</p>
                      <div className="bg-gray-900 rounded-lg p-2.5 max-h-24 overflow-y-auto">
                        {detail.metadata_extracted.suspicious_strings.map((s, i) => (
                          <code key={i} className="block text-xs text-amber-400 font-mono">{s}</code>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
