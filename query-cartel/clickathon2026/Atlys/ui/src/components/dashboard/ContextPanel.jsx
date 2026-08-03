import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import Tooltip from '../common/Tooltip'
import { fmtDateTime } from '../../utils'

const mdComponents = {
  code({ node, inline, className, children, ...props }) {
    const lang = /language-(\w+)/.exec(className || '')?.[1]
    if (!inline && lang) {
      return (
        <SyntaxHighlighter
          style={vscDarkPlus}
          language={lang}
          PreTag="div"
          customStyle={{
            margin: '10px 0',
            borderRadius: '8px',
            fontSize: '12px',
            background: 'rgba(0,0,0,0.45)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
          {...props}
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      )
    }
    return <code className={className} {...props}>{children}</code>
  },
}

export default function ContextPanel({ ctx, versions = [], onVersionChange, langfuseBaseUrl, langfuseProjectId }) {
  if (!ctx || !ctx.content) {
    return (
      <div className="empty-state">
        <svg className="empty-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
        <span>No context snapshot yet</span>
      </div>
    )
  }

  const traceUrl = ctx.trace_id
    ? langfuseProjectId
      ? `${langfuseBaseUrl.replace(/\/$/, '')}/project/${langfuseProjectId}/traces/${ctx.trace_id}`
      : `${langfuseBaseUrl.replace(/\/$/, '')}/traces?search=${ctx.trace_id}`
    : null

  return (
    <div className="context-panel-wrap">
      {/* ── Toolbar ── */}
      <div className="context-toolbar">
        <div className="context-toolbar-left">
          {/* Version select */}
          <Tooltip content="Context version — pick an older snapshot to compare." position="bottom" focusable={false}>
            <div className="context-version-pill">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              {versions.length > 0 ? (
                <select
                  className="context-version-select"
                  value={ctx.version}
                  onChange={e => onVersionChange(Number(e.target.value))}
                  aria-label="Select context version"
                >
                  {versions.map(v => (
                    <option key={v} value={v}>v{v}</option>
                  ))}
                </select>
              ) : (
                <span>v{ctx.version}</span>
              )}
            </div>
          </Tooltip>

          {ctx.created_at && (
            <Tooltip content="When this context snapshot was created.">
              <span className="context-updated">
                Updated {fmtDateTime(ctx.created_at)}
              </span>
            </Tooltip>
          )}
          {ctx.content_hash && (
            <Tooltip content={`Content hash: ${ctx.content_hash} — changes whenever the context is re-derived.`}>
              <span className="context-hash">{ctx.content_hash.slice(0, 10)}</span>
            </Tooltip>
          )}
        </div>

        <div className="context-toolbar-right">
          {ctx.trace_id && traceUrl && (
            <a
              href={traceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="trace-link"
              title="Open trace in Langfuse"
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              Trace {ctx.trace_id.slice(0, 8)}
            </a>
          )}
        </div>
      </div>

      {/* ── Diff collapsible ── */}
      {ctx.diff_from_prev && (
        <Tooltip content="What changed vs the previous context snapshot — why this version is fresher." position="bottom" focusable={false}>
          <details className="context-diff-details">
            <summary className="context-diff-summary">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
              </svg>
              Changes from previous version
            </summary>
            <pre className="diff-block">{ctx.diff_from_prev}</pre>
          </details>
        </Tooltip>
      )}

      {/* ── Markdown viewer ── */}
      <div className="context-md-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
          {ctx.content}
        </ReactMarkdown>
      </div>
    </div>
  )
}
