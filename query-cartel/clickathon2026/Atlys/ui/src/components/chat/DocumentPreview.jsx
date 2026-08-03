import { useEffect, useState, useMemo, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { getDocumentContent } from '../../api/client'

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async (e) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }, [text])

  return (
    <button className="btn btn-copy-preview" onClick={handleCopy} title="Copy content">
      {copied ? (
        <>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M20 6L9 17l-5-5"/>
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
          Copy
        </>
      )}
    </button>
  )
}

export default function DocumentPreview({ path, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!path) return
    setLoading(true)
    setError(null)
    setData(null)
    getDocumentContent(path)
      .then(res => {
        setData(res)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message || 'Failed to load document')
        setLoading(false)
      })
  }, [path])

  // Escape key to close
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!path) return null

  const filename = path.split('/').pop()
  const isMd = filename.endsWith('.md')

  const getIcon = (name) => {
    if (name.endsWith('.md'))     return '📝'
    if (name.endsWith('.sql'))    return '🗄️'
    if (name.endsWith('.json'))   return '⚙️'
    if (name.endsWith('.ndjson')) return '📥'
    return '📄'
  }

  const getLanguage = (name) => {
    const ext = name.split('.').pop().toLowerCase()
    if (ext === 'sql')   return 'sql'
    if (ext === 'json' || ext === 'ndjson') return 'json'
    if (ext === 'js' || ext === 'jsx') return 'javascript'
    if (ext === 'py')    return 'python'
    return 'text'
  }

  // Word count for .md files
  const wordCount = useMemo(() => {
    if (!isMd || !data?.content) return null
    const words = data.content.trim().split(/\s+/).filter(Boolean).length
    const mins = Math.max(1, Math.round(words / 200))
    return `${words.toLocaleString()} words · ~${mins} min read`
  }, [isMd, data])

  return (
    <div className="doc-preview-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={`Document: ${filename}`}>
      <div className="doc-preview-modal" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="doc-preview-header">
          <div className="doc-preview-title-block">
            <span className="doc-preview-icon">{getIcon(filename)}</span>
            <div className="doc-preview-text-block">
              <h3>{filename}</h3>
              <span className="doc-preview-path">
                {path}
                {wordCount && <span className="doc-preview-wordcount"> · {wordCount}</span>}
              </span>
            </div>
          </div>
          <div className="doc-preview-actions">
            {data?.content && <CopyButton text={data.content} />}
            <button className="btn btn-close-preview" onClick={onClose} title="Close (Esc)">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="doc-preview-body">
          {loading && (
            <div className="doc-preview-status">
              <span className="tool-spinner tool-spinner--lg" />
              <p>Loading document…</p>
            </div>
          )}

          {error && (
            <div className="doc-preview-status error">
              <span className="error-icon">⚠️</span>
              <p>{error}</p>
            </div>
          )}

          {!loading && !error && data && (
            <div className={`doc-preview-content${isMd ? ' doc-preview-content--md' : ''}`}>
              {isMd ? (
                <div className="markdown-preview-body markdown-preview-body--full">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {data.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <SyntaxHighlighter
                  style={vscDarkPlus}
                  language={getLanguage(filename)}
                  PreTag="div"
                  customStyle={{
                    margin: 0,
                    borderRadius: '8px',
                    fontSize: '13px',
                    background: 'rgba(0,0,0,0.5)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    height: '100%',
                    padding: '16px',
                    overflow: 'auto',
                  }}
                  showLineNumbers
                >
                  {data.content}
                </SyntaxHighlighter>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
