import { lazy, Suspense, useState, useMemo, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { fmtTime, extractRunId } from '../../utils'
import DocumentCard from './DocumentCard'
import { getDocumentMetadata, getDocumentDownloadUrl } from '../../api/client'
import { bareToolName, summarizeToolCall } from '../../utils/toolSummary'

const ChatChart = lazy(() => import('./ChatChart'))

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function InlineDocumentLink({ path, fallbackName, onPreview }) {
  const [metadata, setMetadata] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    getDocumentMetadata(path)
      .then(data => {
        if (!active) return
        if (data.exists) {
          setMetadata(data)
        } else {
          setError(true)
        }
        setLoading(false)
      })
      .catch(() => {
        if (!active) return
        setError(true)
        setLoading(false)
      })
    return () => { active = false }
  }, [path])

  const handleDownload = (e) => {
    e.stopPropagation()
    const url = getDocumentDownloadUrl(path)
    const link = document.createElement('a')
    link.href = url
    link.download = metadata?.name || fallbackName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handlePreview = (e) => {
    e.preventDefault()
    if (onPreview) {
      onPreview(path)
    }
  }

  if (loading) {
    return <span className="inline-doc-loading">📄 {fallbackName}...</span>
  }

  if (error || !metadata) {
    return <span className="inline-doc-error">⚠️ {fallbackName} (Unavailable)</span>
  }

  return (
    <span className="inline-doc-link-container">
      <button 
        className="inline-doc-download-btn" 
        onClick={handleDownload} 
        title="Download file"
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
      </button>
      <a 
        href="#" 
        className="inline-doc-preview-link" 
        onClick={handlePreview} 
        title="Click to preview"
      >
        {metadata.name}
      </a>
      <span className="inline-doc-size">({formatBytes(metadata.size)})</span>
    </span>
  )
}

export function getRelativeDocumentPath(href) {
  if (!href) return null;
  let path = href.trim();
  
  // Extract path from download API URL if present
  const downloadMatch = path.match(/\/api\/documents\/download\?path=([^&]+)/)
  if (downloadMatch) {
    return decodeURIComponent(downloadMatch[1]);
  }
  
  if (path.startsWith('file://')) {
    path = path.replace(/^file:\/\/\/?/, '');
  }
  
  const atlysIndex = path.indexOf('Atlys/');
  if (atlysIndex !== -1) {
    path = path.slice(atlysIndex + 6);
  }
  
  // Strip leading ./ or /
  path = path.replace(/^\.\//, '').replace(/^\//, '');
  
  if (path.startsWith('specs/') || path.startsWith('generated/') || path === 'base_context.md') {
    return path;
  }
  
  return null;
}

/** Path written by a save_document tool row (from call args or result). */
export function savedDocPathFromToolMsg(msg) {
  if (!msg || msg.role !== 'tool') return null
  if (bareToolName(msg.toolName || msg.name) !== 'save_document') return null

  if (msg.args) {
    try {
      const args = typeof msg.args === 'object' ? msg.args : JSON.parse(msg.args)
      const filename = args?.filename
      const subdir = args?.subdirectory || 'reports'
      if (
        filename
        && !filename.includes('/')
        && !filename.includes('\\')
        && !filename.includes('..')
      ) {
        return `generated/${subdir}/${filename}`
      }
    } catch { /* ignore */ }
  }

  const resultPayload = msg.result ?? (msg.toolPhase === 'result' ? msg.content : '')
  if (resultPayload) {
    try {
      const parsed = typeof resultPayload === 'object' ? resultPayload : JSON.parse(resultPayload)
      if (parsed?.success && parsed?.path) return String(parsed.path).replace(/^\.\//, '')
    } catch { /* ignore */ }
  }
  return null
}

/**
 * Models often copy the prompt's nested-fence example and emit:
 *   ````
 *   ```atlyschart
 *   {...}
 *   ```
 *   ````
 * React-markdown then treats the outer fence as a plain code block, so the
 * chart never mounts. Unwrap those (and bare JSON fences that are charts).
 */
export function normalizeAtlysChartFences(text) {
  if (!text) return text

  let out = text

  // Outer fence (3+ backticks, optional lang) whose body is only an atlyschart fence.
  out = out.replace(
    /(^|\n)(`{3,})[^\n]*\n\s*(```atlyschart\n[\s\S]*?\n```)\s*\n\2(?=\n|$)/g,
    '$1$3',
  )

  // Outer fence whose body is raw chart JSON (no inner language tag).
  out = out.replace(
    /(^|\n)(`{3,})(?!atlyschart\b)[^\n]*\n(\s*\{[\s\S]*?"type"\s*:\s*"(?:bar|line|pie|horizontal_bar)"[\s\S]*?\})\s*\n\2(?=\n|$)/g,
    '$1```atlyschart\n$3\n```',
  )

  return out
}

export function injectDocumentLinks(text) {
  if (!text) return '';
  
  // Unescape backslashes before markdown link symbols and punctuation (e.g. GLM escaped output \[...\] or \_)
  let cleanText = text.replace(/\\([_\[\]()!.-])/g, '$1');
  
  const regex = /(\[.*?\]\((?:.*?)\))|(\b(?:file:\/\/\/\S+?\/Atlys\/|\b)(?:generated|specs)\/[a-zA-Z0-9_./-]+|(?:\b|^)base_context\.md\b)/gi;
  return cleanText.replace(regex, (match, group1, group2) => {
    if (group1) {
      // Check if it is a markdown link we should rewrite to a proper download endpoint
      const matchUrl = group1.match(/\[(.*?)\]\((.*?)\)/)
      if (matchUrl) {
        const linkText = matchUrl[1]
        const href = matchUrl[2]
        const relPath = getRelativeDocumentPath(href)
        if (relPath) {
          return `[${linkText}](/api/documents/download?path=${encodeURIComponent(relPath)})`
        }
      }
      return group1;
    }
    if (group2) {
      let cleanPath = group2;
      if (cleanPath.startsWith('file:///')) {
        const atlysIndex = cleanPath.indexOf('/Atlys/');
        if (atlysIndex !== -1) {
          cleanPath = cleanPath.slice(atlysIndex + 7);
        }
      }
      const filename = cleanPath.split('/').pop();
      return `[${filename}](/api/documents/download?path=${encodeURIComponent(cleanPath)})`;
    }
    return match;
  });
}

// ── Tool-call block parser (legacy fences still in old transcripts) ───────────

/**
 * Parse ALL tool_call blocks out of raw LLM content.
 * Handles:
 *   ```tool_call\nname: foo\narguments:\n  x: y\n```
 *   tool_call:\n  name: foo\n  arguments:\n    x: y\n
 */
export function parseToolCallBlocks(content) {
  const blocks = []

  const fencedRe = /```tool[_-]call\n([\s\S]*?)```/gi
  let m
  while ((m = fencedRe.exec(content)) !== null) {
    const inner = m[1]
    const name  = /^\s*name[:\s]+([^\s\n,]+)/m.exec(inner)?.[1]?.trim() ?? 'tool'
    const argsMatch = /arguments?:\s*\n([\s\S]*)$/i.exec(inner)
    blocks.push({ name, args: argsMatch?.[1]?.trimEnd() ?? '', raw: m[0] })
  }

  const inlineRe = /tool[_-]call:\s*\n((?:[ \t]+[^\n]+\n?)+)/gi
  while ((m = inlineRe.exec(content)) !== null) {
    if (blocks.some(b => b.raw === m[0])) continue
    const inner = m[1]
    const name  = /name:\s*([^\s\n,]+)/.exec(inner)?.[1]?.trim() ?? 'tool'
    const argsMatch = /arguments?:\s*\n([\s\S]*)$/i.exec(inner)
    blocks.push({ name, args: argsMatch?.[1]?.trimEnd() ?? inner, raw: m[0] })
  }

  return blocks
}

/**
 * Split content around tool_call blocks.
 * Returns: Array<{ type: 'text'|'tool', content?: string, name?: string, args?: string }>
 */
export function splitContentWithTools(rawContent) {
  const blocks = parseToolCallBlocks(rawContent)
  if (!blocks.length) return [{ type: 'text', content: rawContent }]

  const parts = []
  let cursor = 0

  for (const block of blocks) {
    const idx = rawContent.indexOf(block.raw, cursor)
    if (idx === -1) continue

    const before = rawContent.slice(cursor, idx).trim()
    if (before) parts.push({ type: 'text', content: before })
    parts.push({ type: 'tool', name: block.name, args: block.args })
    cursor = idx + block.raw.length
  }

  const after = rawContent.slice(cursor).trim()
  if (after) parts.push({ type: 'text', content: after })

  return parts
}

/** Strip tool fences; return plain assistant text. */
export function stripToolCallFences(content) {
  return splitContentWithTools(content || '')
    .filter(p => p.type === 'text')
    .map(p => p.content)
    .join('\n')
    .trim()
}

/** True when the message contains a ClickHouse schema (CREATE TABLE). */
export function hasSchema(content) {
  return /CREATE\s+TABLE/i.test(content || '')
}

/** True when content looks like a Q&A / gap-questions turn. */
export function isQaTurn(content) {
  const trimmed = (content || '').trim()
  return trimmed.endsWith('?') || /^\d+\.\s+.+\?/m.test(trimmed)
}

// ── Tool step UI ──────────────────────────────────────────────────────────────

const TOOL_ICONS = {
  interrogate_spec:     '🔍',
  run_spec:             '⚙️',
  approve_schema:       '✅',
  reject_schema:        '❌',
  get_insight:          '💡',
  list_insights:        '📋',
  get_changelog:        '📜',
  get_context:          '📄',
  propose_context_update: '✏️',
  reconcile:            '🔀',
  ingest_events:        '📥',
  db_schema:            '🗂️',
  table_stats:          '📊',
  aggregate:            '∑',
  sample_rows:          '🔎',
  save_document:        '💾',
}

function formatArgs(args) {
  if (args == null || args === '') return ''
  if (typeof args === 'object') {
    try { return JSON.stringify(args, null, 2) } catch { return String(args) }
  }
  const s = String(args).trim()
  if (!s) return ''
  try { return JSON.stringify(JSON.parse(s), null, 2) } catch { return s }
}

function ToolStep({ name, args, result, status, phase, onPreview, summary }) {
  const [expanded, setExpanded] = useState(status === 'running')
  const bare  = bareToolName(name)
  const icon  = TOOL_ICONS[bare] ?? '🔧'
  const label = bare.replace(/_/g, ' ')
  const oneLiner = summary || summarizeToolCall(bare, args)
  const isRunning = status === 'running'
  const isError = status === 'error'
  const argsText = formatArgs(args)
  
  // Detect save_document results and extract path
  let isSaveDocResult = false
  let saveDocPath = null
  if (bare === 'save_document' && phase === 'result' && result) {
    try {
      const parsed = typeof result === 'object' ? result : JSON.parse(result)
      if (parsed && parsed.success && parsed.path) {
        isSaveDocResult = true
        saveDocPath = parsed.path
      }
    } catch (e) {
      // ignore
    }
  }

  const resultText = isSaveDocResult ? null : formatArgs(result)
  const hasBody = Boolean(argsText || resultText || isSaveDocResult)
  const phaseLabel = phase === 'result' ? 'result' : (isRunning ? 'running' : 'done')

  return (
    <div className={`tool-step ${isRunning ? 'tool-step--running' : ''} ${isError ? 'tool-step--error' : ''}`}>
      <button
        className="tool-step-header"
        onClick={() => hasBody && setExpanded(v => !v)}
        aria-expanded={expanded}
        style={{ cursor: hasBody ? 'pointer' : 'default' }}
      >
        <span className="tool-step-status">
          {isRunning
            ? <span className="tool-spinner tool-spinner--sm" />
            : isError
              ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
          }
        </span>

        <span className="tool-step-icon">{icon}</span>
        <span className="tool-step-main">
          <span className="tool-step-summary">{oneLiner}</span>
          <span className="tool-step-meta">
            <span className="tool-step-name">{label}</span>
            <span className="tool-step-phase">{phaseLabel}</span>
          </span>
        </span>

        {hasBody && (
          <span className={`tool-step-chevron ${expanded ? 'open' : ''}`}>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </span>
        )}
      </button>

      {expanded && hasBody && (
        <div className="tool-step-body">
          {argsText && (
            <>
              <div className="tool-step-section-label">Arguments</div>
              <pre className="tool-step-args">{argsText}</pre>
            </>
          )}
          {isSaveDocResult ? (
            <>
              <div className="tool-step-section-label">Saved Document</div>
              <div style={{ marginTop: '8px', marginBottom: '8px' }}>
                <DocumentCard path={saveDocPath} onPreview={onPreview} />
              </div>
            </>
          ) : resultText ? (
            <>
              <div className="tool-step-section-label">Result</div>
              <pre className="tool-step-args">{resultText}</pre>
            </>
          ) : null}
          {!resultText && !isSaveDocResult && phase === 'result' && (
            <pre className="tool-step-args tool-step-args--muted">No result payload</pre>
          )}
        </div>
      )}
    </div>
  )
}

/** Collapsed-by-default agent thinking / reasoning block. */
function ThinkingBlock({ text, pending }) {
  if (!text?.trim()) return null
  return (
    <details className={`thinking-block ${pending ? 'thinking-block--pending' : ''}`}>
      <summary>
        <span className="thinking-block-label">
          {pending ? 'Thinking…' : 'Thought process'}
        </span>
      </summary>
      <div className="thinking-block-body">{text}</div>
    </details>
  )
}

// ── Approval card ─────────────────────────────────────────────────────────────
function ApprovalCard({ runId, onApprove, onReject }) {
  return (
    <div className="approval-card">
      <div className="approval-card-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M9 12l2 2 4-4" /><circle cx="12" cy="12" r="10" />
        </svg>
        Schema ready — your approval needed
      </div>
      <div className="approval-card-actions">
        <button className="btn btn-approve" onClick={() => onApprove(runId)}>
          ✅ Approve &amp; Deploy
        </button>
        <button className="btn btn-reject" onClick={() => onReject(runId)}>
          ❌ Reject &amp; Revise
        </button>
      </div>
    </div>
  )
}

function markdownCellText(children) {
  if (children == null || children === false) return ''
  if (typeof children === 'string' || typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map(markdownCellText).join('')
  if (typeof children === 'object' && children.props) return markdownCellText(children.props.children)
  return ''
}

function isNumericCell(text) {
  const t = text.trim()
  return /^-?[\d,]+(\.\d+)?%?$/.test(t)
}

function isNumericHeader(text) {
  const t = text.trim()
  return isNumericCell(t) || /^(users?|events?|count|n|rows?|amount|total|uniq.*)$/i.test(t)
}

function makeMarkdownComponents({ pending, onPreview, compactDocPaths }) {
  const compact = compactDocPaths instanceof Set ? compactDocPaths : null
  return {
    table({ children }) {
      return (
        <div className="chat-table-wrap">
          <table>{children}</table>
        </div>
      )
    },
    td({ children, ...props }) {
      const numeric = isNumericCell(markdownCellText(children))
      return (
        <td className={numeric ? 'num' : undefined} {...props}>
          {children}
        </td>
      )
    },
    th({ children, ...props }) {
      const numeric = isNumericHeader(markdownCellText(children))
      return (
        <th className={numeric ? 'num' : undefined} {...props}>
          {children}
        </th>
      )
    },
    a({ node: _node, href, children, ...props }) {
      const relPath = getRelativeDocumentPath(href)
      if (relPath) {
        const fallbackName = children && children[0] ? String(children[0]) : relPath.split('/').pop()
        // Avoid a second full DocumentCard when save_document already rendered one.
        if (compact?.has(relPath)) {
          return (
            <InlineDocumentLink
              path={relPath}
              fallbackName={fallbackName}
              onPreview={onPreview}
            />
          )
        }
        return (
          <DocumentCard
            path={relPath}
            fallbackName={fallbackName}
            onPreview={onPreview}
          />
        )
      }
      return <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
    },
    code({ inline, className, children, ...props }) {
      const lang = /language-(\w+)/.exec(className || '')?.[1]
      const body = String(children).replace(/\n$/, '')

      if (!inline && lang === 'atlyschart') {
        if (pending) {
          return (
            <div className="chat-chart-pending" aria-live="polite">
              Chart loading…
            </div>
          )
        }
        return (
          <Suspense fallback={<div className="chat-chart-pending">Chart loading…</div>}>
            <ChatChart raw={body} />
          </Suspense>
        )
      }

      if (!inline && lang) {
        return (
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={lang}
            PreTag="div"
            customStyle={{
              margin: '8px 0',
              borderRadius: '8px',
              fontSize: '12px',
              background: 'rgba(0,0,0,0.45)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
            {...props}
          >
            {body}
          </SyntaxHighlighter>
        )
      }
      return <code className={className} {...props}>{children}</code>
    },
  }
}

// ── Main component ────────────────────────────────────────────────────────────

/**
 * Single chat message row.
 * Tool invocations are role:'tool' messages (call / result), not part of assistant text.
 */
export default function ChatMessage({ msg, onApprove, onReject, onPreview, shownDocPaths }) {
  const isUser      = msg.role === 'user'
  const isAssistant = msg.role === 'assistant'
  const isTool      = msg.role === 'tool'

  if (isTool) {
    const bare = bareToolName(msg.toolName || msg.name || '')
    const isSaveDoc = bare === 'save_document'
    const docPath = (isSaveDoc && msg.toolPhase === 'call' && msg.status === 'done')
      ? savedDocPathFromToolMsg(msg)
      : null
    // Dedupe: stream replay / older chats may have two save_document rows for one file.
    const showDocCard = Boolean(docPath) && !shownDocPaths?.has(docPath)

    return (
      <div className="msg tool" aria-live="polite" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <ToolStep
          name={msg.toolName || msg.name || 'tool'}
          args={msg.args}
          result={msg.result ?? (msg.toolPhase === 'result' ? msg.content : '')}
          status={msg.status || 'done'}
          phase={msg.toolPhase || 'call'}
          onPreview={onPreview}
          summary={msg.summary}
        />
        {showDocCard && (
          <div style={{ width: '100%', marginTop: '4px' }}>
            <DocumentCard path={docPath} fallbackName={docPath.split('/').pop()} onPreview={onPreview} />
          </div>
        )}
        {msg.ts && <span className="msg-time">{fmtTime(msg.ts)}</span>}
      </div>
    )
  }


  if (isUser) {
    return (
      <div className="msg user" aria-live="off">
        <div className="msg-bubble">
          <span>{msg.content}</span>
        </div>
        <span className="msg-time">{fmtTime(msg.ts)}</span>
      </div>
    )
  }

  if (isAssistant) {
    return (
      <AssistantMessage
        msg={msg}
        onApprove={onApprove}
        onReject={onReject}
        onPreview={onPreview}
        shownDocPaths={shownDocPaths}
      />
    )
  }

  return null
}

function AssistantMessage({ msg, onApprove, onReject, onPreview, shownDocPaths }) {
  const rawContent = msg.content || ''
  const isRunning = msg.pending === true
  const mdComponents = useMemo(
    () => makeMarkdownComponents({ pending: isRunning, onPreview, compactDocPaths: shownDocPaths }),
    [isRunning, onPreview, shownDocPaths],
  )

  // Legacy: fences still inside assistant content → strip for display; tools
  // should already be separate messages in new streams.
  const stripped = stripToolCallFences(rawContent) || (parseToolCallBlocks(rawContent).length ? '' : rawContent)
  const text = normalizeAtlysChartFences(stripped)
  const thinking = (msg.thinking || '').trim()
  const runId = extractRunId(text)
  const showApproval = !isRunning && runId && onApprove && hasSchema(text)

  // Empty finalized assistants are dropped; pending placeholders stay as the
  // "agent is working" indicator between tool steps / before the reply.
  if (!text && !thinking && !isRunning) return null

  const showWorkingDots = isRunning && !text
  const statusLabel = msg.statusText
    || (isRunning && !text ? (thinking ? 'Generating reply…' : 'Working…') : '')

  return (
    <div className="msg assistant" aria-live="polite">
      <div className="assistant-row">
        <div className="assistant-avatar" aria-hidden="true">A</div>
        <div className="assistant-body">
          {thinking && (
            <ThinkingBlock text={thinking} pending={isRunning && !text} />
          )}
          {text && (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
              {injectDocumentLinks(text)}
            </ReactMarkdown>
          )}
          {showWorkingDots && (
            <div className="loading-dots" aria-hidden="true">
              <span /><span /><span />
            </div>
          )}
          {statusLabel && (
            <div className="stream-status">{statusLabel}</div>
          )}
          {msg.ts && (
            <span className="msg-time">{fmtTime(msg.ts)}</span>
          )}
        </div>
      </div>

      {showApproval && (
        <ApprovalCard runId={runId} onApprove={onApprove} onReject={onReject} />
      )}
    </div>
  )
}
