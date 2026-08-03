import { useEffect, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { getDocumentMetadata, getDocumentContent } from '../../api/client'

function CopyButton({ text, className = 'doc-copy-btn' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async (e) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback
    }
  }, [text])

  return (
    <button className={className} onClick={handleCopy} title="Copy to clipboard">
      {copied ? (
        <>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M20 6L9 17l-5-5"/>
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
          Copy
        </>
      )}
    </button>
  )
}

export default function DocumentCard({ path, fallbackName, onPreview }) {
  const [metadata, setMetadata] = useState(null)
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true

    const fetchDoc = async () => {
      try {
        const meta = await getDocumentMetadata(path)
        if (!active) return

        if (!meta.exists) {
          setError(true)
          setLoading(false)
          return
        }

        setMetadata(meta)

        const contentData = await getDocumentContent(path)
        if (!active) return

        setContent(contentData.content)
        setLoading(false)
      } catch {
        if (!active) return
        setError(true)
        setLoading(false)
      }
    }

    fetchDoc()
    return () => { active = false }
  }, [path])

  if (loading) {
    return (
      <div className="document-card-container loading">
        <div className="document-card-header">
          <div className="doc-header-info">
            <span className="doc-icon-placeholder" />
            <div className="doc-details-placeholder">
              <div className="line-placeholder short" />
            </div>
          </div>
        </div>
        <div className="document-card-body-placeholder" />
      </div>
    )
  }

  if (error || !metadata) {
    return (
      <div className="document-card-container error">
        <div className="document-card-header border-none">
          <div className="doc-header-info">
            <span className="doc-icon-emoji">⚠️</span>
            <span className="doc-name">{fallbackName || path.split('/').pop()}</span>
          </div>
          <span className="doc-meta text-error">File not available</span>
        </div>
      </div>
    )
  }

  const filename = metadata.name || fallbackName || path.split('/').pop()
  const isMd = filename.endsWith('.md')

  const getIcon = (ext) => {
    switch (ext) {
      case '.md':     return '📝'
      case '.sql':    return '🗄️'
      case '.json':   return '⚙️'
      case '.ndjson': return '📥'
      default:        return '📄'
    }
  }

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  }

  const getLanguage = (name) => {
    const ext = name.split('.').pop().toLowerCase()
    if (ext === 'sql') return 'sql'
    if (ext === 'json' || ext === 'ndjson') return 'json'
    if (ext === 'js' || ext === 'jsx') return 'javascript'
    if (ext === 'py') return 'python'
    return 'text'
  }

  return (
    <div className="document-card-container">
      <div className="document-card-header">
        <div className="doc-header-info">
          <span className="doc-icon-emoji">{getIcon(metadata.extension)}</span>
          <div className="doc-details">
            <span className="doc-name">{filename}</span>
            <span className="doc-meta">{formatBytes(metadata.size)} · {metadata.extension.toUpperCase().slice(1)}</span>
          </div>
        </div>
        <div className="doc-header-actions">
          {content && <CopyButton text={content} />}
          {isMd && onPreview && (
            <button
              className="doc-header-open-btn"
              onClick={() => onPreview(path)}
              title="Open full document"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15 3 21 3 21 9"/>
                <line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
              Open
            </button>
          )}
        </div>
      </div>

      <div className={`document-card-body${isMd ? ' md-preview' : ''}`}>
        {isMd ? (
          <div className="markdown-preview-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content || ''}
            </ReactMarkdown>
          </div>
        ) : (
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={getLanguage(filename)}
            PreTag="div"
            customStyle={{
              margin: 0,
              background: 'transparent',
              fontSize: '12px',
              padding: '12px',
            }}
            showLineNumbers
          >
            {content || ''}
          </SyntaxHighlighter>
        )}
      </div>
    </div>
  )
}
