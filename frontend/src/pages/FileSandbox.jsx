import { useState, useRef } from 'react';
import { useApi } from '../hooks/useApi';
import { sandbox as sandboxApi } from '../api/sandbox';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';
import InfoModal from '../components/InfoModal';

const INFO_SECTIONS = [
  {
    heading: 'Cos\'è',
    text: 'File Sandbox esegue analisi statica su file caricati: matching di regole YARA, lookup dell\'hash SHA-256 su VirusTotal, calcolo dell\'entropia (indicatore di packing/cifratura) e parsing PE per i file Windows.',
  },
  {
    heading: 'Come si usa',
    items: [
      'Trascina un file nella drop zone oppure clicca per selezionarlo.',
      'L\'analisi parte in background: attendi che lo stato passi da <em>analyzing</em> a un risultato.',
      'Il risultato può essere: <strong>safe</strong>, <strong>suspicious</strong> o <strong>malicious</strong>.',
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

function DropZone({ onFile }) {
  const [drag, setDrag] = useState(false);
  const input = useRef();

  const handle = (file) => { if (file) onFile(file); };

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer mb-6 ${
        drag ? 'border-corvin-accent bg-corvin-accent/5' : 'border-corvin-700 hover:border-corvin-accent/50'
      }`}
      onClick={() => input.current.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]); }}
    >
      <input ref={input} type="file" className="hidden" onChange={(e) => handle(e.target.files[0])} />
      <p className="text-gray-400 text-sm">
        Trascina un file qui, oppure <span className="text-corvin-accent">clicca per selezionare</span>
      </p>
      <p className="text-xs text-gray-600 mt-1">Max 10 MB · YARA + VirusTotal hash lookup</p>
    </div>
  );
}

function YaraMatches({ matches }) {
  if (!matches?.length) return <p className="text-xs text-gray-500">Nessun match YARA.</p>;
  return (
    <div className="space-y-1">
      {matches.map((m, i) => (
        <div key={i} className="flex items-center gap-2">
          <SeverityBadge value={m.severity} />
          <span className="text-xs text-white">{m.rule}</span>
          <span className="text-xs text-gray-500">· {m.description}</span>
        </div>
      ))}
    </div>
  );
}

export default function FileSandbox() {
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
      // Poll ogni 3s per max 45s in attesa che l'analisi background completi
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
        setUploadError('File troppo grande. Dimensione massima: 10 MB.');
      } else if (msg.includes('non supportato') || msg.includes('415')) {
        setUploadError('Tipo di file non supportato. Controlla i formati accettati.');
      } else {
        setUploadError(err.message ?? 'Errore durante l\'upload. Riprova più tardi.');
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
    if (!window.confirm('Rimuovere questo file dall\'elenco?')) return;
    setRemovingId(id);
    try {
      await sandboxApi.remove(id);
      if (detail?.id === id) setDetail(null);
      await refetch();
    } catch (err) {
      setUploadError(err.message ?? 'Errore durante la rimozione.');
    } finally {
      setRemovingId(null);
    }
  };

  const formatSize = (b) =>
    b > 1_048_576 ? `${(b / 1_048_576).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`;

  return (
    <div>
      <InfoModal
        open={showInfo}
        onClose={() => setShowInfo(false)}
        title="File Sandbox — Guida"
        sections={INFO_SECTIONS}
      />

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">File Sandbox</h1>
          <p className="text-gray-400 text-sm mt-1">Analisi statica: YARA, VirusTotal hash, entropia, PE parsing</p>
        </div>
        <button
          onClick={() => setShowInfo(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-corvin-accent border border-corvin-accent/30 rounded-lg hover:bg-corvin-accent/10 transition-colors"
        >
          <span>ⓘ</span> Info
        </button>
      </div>

      <DropZone onFile={handleFile} />
      {uploading && <p className="text-sm text-corvin-accent mb-4 animate-pulse">Upload in corso…</p>}
      {uploadError && <p className="text-red-400 text-sm mb-4">{uploadError}</p>}

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && files?.length === 0 && (
        <EmptyState title="Nessun file analizzato" description="Carica un file per avviare l'analisi." />
      )}

      {!loading && files?.length > 0 && (
        <div className="space-y-2">
          {files.map((f) => (
            <div key={f.id} className="bg-corvin-800 border border-corvin-700 rounded-xl">
              <div
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-corvin-700/30"
                onClick={() => handleDetail(f.id)}
              >
                <div className="flex items-center gap-3">
                  <SeverityBadge value={f.status} />
                  <span className="text-sm text-white font-mono">{f.original_filename}</span>
                  <span className="text-xs text-gray-500">{formatSize(f.file_size)}</span>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs text-gray-500">{new Date(f.created_at).toLocaleString('it-IT')}</span>
                  <button
                    onClick={(e) => handleRemove(e, f.id)}
                    disabled={removingId === f.id}
                    className="text-xs text-gray-500 hover:text-red-400 transition-colors disabled:opacity-50"
                  >
                    {removingId === f.id ? '...' : '✕'}
                  </button>
                </div>
              </div>

              {detail?.id === f.id && (
                <div className="border-t border-corvin-700 px-4 py-3 space-y-3">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-gray-400">SHA-256: </span>
                      <code className="text-gray-300 break-all">{detail.sha256_hash}</code>
                    </div>
                    <div>
                      <span className="text-gray-400">MIME: </span>
                      <span className="text-white">{detail.mime_type ?? '—'}</span>
                    </div>
                    {detail.metadata_extracted?.entropy != null && (
                      <div>
                        <span className="text-gray-400">Entropia: </span>
                        <span className={detail.metadata_extracted.high_entropy ? 'text-red-400' : 'text-white'}>
                          {detail.metadata_extracted.entropy}
                          {detail.metadata_extracted.high_entropy && ' ⚠ alta'}
                        </span>
                      </div>
                    )}
                    {detail.virustotal_result && (
                      <div>
                        <span className="text-gray-400">VirusTotal: </span>
                        <span className={detail.virustotal_result.detections > 0 ? 'text-red-400' : 'text-green-400'}>
                          {detail.virustotal_result.status === 'not_found'
                            ? 'non trovato'
                            : `${detail.virustotal_result.detections}/${detail.virustotal_result.total}`}
                        </span>
                      </div>
                    )}
                  </div>

                  <div>
                    <p className="text-xs text-gray-400 font-medium mb-1">YARA matches</p>
                    <YaraMatches matches={detail.yara_matches} />
                  </div>

                  {detail.metadata_extracted?.suspicious_strings?.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 font-medium mb-1">Stringhe sospette</p>
                      <div className="bg-corvin-700/50 rounded p-2 max-h-24 overflow-y-auto">
                        {detail.metadata_extracted.suspicious_strings.map((s, i) => (
                          <code key={i} className="block text-xs text-yellow-400">{s}</code>
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
