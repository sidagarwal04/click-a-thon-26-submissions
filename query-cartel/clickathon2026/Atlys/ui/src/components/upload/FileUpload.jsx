import { useState, useRef, useCallback } from 'react'
import { uploadSpec } from '../../api/client'

const STEP_IDLE      = 'idle'
const STEP_UPLOADING = 'uploading'
const STEP_DONE      = 'done'

function FileRow({ label, accept, file, onAdd }) {
  const ready = !!file
  return (
    <div className={`upload-file-row ${ready ? 'ready' : ''}`}>
      <div className="upload-file-icon">
        {ready
          ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5" /></svg>
          : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
        }
      </div>
      <div className="upload-file-info">
        <span className="upload-file-name">
          {ready ? file.name : <span className="upload-file-placeholder">{label}</span>}
        </span>
        {ready && (
          <span className="upload-file-size">{(file.size / 1024).toFixed(1)} KB</span>
        )}
      </div>
      {!ready && (
        <button className="upload-add-btn" onClick={onAdd}>
          Browse
        </button>
      )}
    </div>
  )
}

export default function FileUpload({ onUploaded, onClose }) {
  const [specFile,   setSpecFile]   = useState(null)
  const [eventsFile, setEventsFile] = useState(null)
  const [step,       setStep]       = useState(STEP_IDLE)
  const [error,      setError]      = useState(null)
  const [pending,    setPending]    = useState(null)  // which slot triggered browse
  const fileInput = useRef(null)

  const classify = useCallback((files) => {
    let s = specFile, e = eventsFile
    for (const f of files) {
      const name = f.name.toLowerCase()
      if (name.endsWith('.md'))                          s = f
      else if (name.endsWith('.ndjson') || name.endsWith('.jsonl')) e = f
      else if (pending === 'spec')   s = f
      else if (pending === 'events') e = f
    }
    setSpecFile(s)
    setEventsFile(e)
    setError(null)
    setPending(null)
  }, [specFile, eventsFile, pending])

  const openBrowse = useCallback((slot) => {
    setPending(slot)
    fileInput.current?.click()
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    classify(Array.from(e.dataTransfer.files))
  }, [classify])

  const handleUpload = useCallback(async () => {
    if (!specFile || !eventsFile) {
      setError('Both files are required before uploading.')
      return
    }
    setStep(STEP_UPLOADING)
    setError(null)
    try {
      const result = await uploadSpec(specFile, eventsFile)
      setStep(STEP_DONE)
      setTimeout(() => onUploaded(result.feature), 900)
    } catch (err) {
      setError(err.message)
      setStep(STEP_IDLE)
    }
  }, [specFile, eventsFile, onUploaded])

  const bothReady = specFile && eventsFile
  const isDone    = step === STEP_DONE
  const isUploading = step === STEP_UPLOADING

  return (
    <div
      className={`upload-zone ${isDone ? 'success' : ''}`}
      onDragOver={e => { e.preventDefault() }}
      onDrop={onDrop}
    >
      {/* Hidden file input */}
      <input
        ref={fileInput}
        type="file"
        multiple
        accept=".md,.ndjson,.jsonl"
        style={{ display: 'none' }}
        onChange={e => classify(Array.from(e.target.files))}
        id="spec-file-input"
      />

      {isDone ? (
        /* ── Done state ── */
        <div className="upload-done">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-success)" strokeWidth="2.5">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          <span>Files uploaded — interrogating spec…</span>
        </div>
      ) : (
        <>
          {/* ── Header ── */}
          <div className="upload-header">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span>Upload two files to get started</span>
          </div>

          {/* ── File rows ── */}
          <div className="upload-file-slots">
            <FileRow
              label="spec.md — feature specification"
              accept=".md"
              file={specFile}
              onAdd={() => openBrowse('spec')}
            />
            <FileRow
              label="events.ndjson — sample event data"
              accept=".ndjson,.jsonl"
              file={eventsFile}
              onAdd={() => openBrowse('events')}
            />
          </div>

          {/* ── Progress label ── */}
          <div className="upload-progress-label">
            {!specFile && !eventsFile && 'Drop both files here, or click Browse above'}
            {specFile  && !eventsFile && '✅ Spec ready — now add events.ndjson'}
            {!specFile && eventsFile  && '✅ Events ready — now add spec.md'}
            {bothReady                 && '✅ Both files ready — click Upload to continue'}
          </div>

          {error && (
            <div className="upload-error">{error}</div>
          )}

          {/* ── Action buttons ── */}
          <div className="upload-actions">
            <button
              className="btn btn-approve"
              style={{ fontSize: 12, padding: '7px 16px' }}
              disabled={!bothReady || isUploading}
              onClick={handleUpload}
            >
              {isUploading
                ? <><span className="tool-spinner" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)', width: 10, height: 10, borderWidth: 2 }} /> Uploading…</>
                : '↑ Upload Spec'}
            </button>
            <button
              className="btn btn-reject"
              style={{ fontSize: 12, padding: '7px 14px' }}
              onClick={onClose}
            >
              Cancel
            </button>
          </div>
        </>
      )}
    </div>
  )
}
