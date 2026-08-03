import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { flushSync } from 'react-dom'
import ChatMessage, {
  hasSchema,
  isQaTurn,
  stripToolCallFences,
  parseToolCallBlocks,
  savedDocPathFromToolMsg,
} from './ChatMessage'
import ChatHistory from './ChatHistory'
import FileUpload from '../upload/FileUpload'
import {
  chatStream,
  createConversation,
  getAgentStatus,
  getConversationMessages,
  isStreamDisconnectError,
  listConversations,
  newConversationId,
  resolveActiveChatId,
  saveConversationMessages,
  setStoredActiveChat,
  stopConversation,
  toolCallFingerprint,
  writeChatIdToUrl,
} from '../../api/client'
import { autoResize, estimateChatTokens, fmtCompact } from '../../utils'
import { bareToolName, summarizeToolCall } from '../../utils/toolSummary'

const MAX_AUTO_CONTINUE = 10   // guard against infinite tool-call loops
const DEFAULT_MAX_TOOL_CALLS = 50
/** glm-5.2 context window (librechat.yaml tokenConfig) — used for the usage gauge. */
const DEFAULT_CONTEXT_WINDOW = 1_000_000
const NEAR_BOTTOM_PX = 100
const EMPTY_DOC_PATHS = new Set()

const WELCOME_MSG = {
  role: 'assistant',
  content: 'Hi! I\'m **Atlys Copilot**. Upload a spec (click the upload button) and I\'ll interrogate it, design the ClickHouse schema, and generate a PM-ready insight — with your approval at each step.',
  ts: new Date().toISOString(),
  id: 'welcome',
}

function withWelcome(messages) {
  if (!messages?.length) return [WELCOME_MSG]
  if (messages.some(m => m.id === 'welcome')) return messages
  return [WELCOME_MSG, ...messages]
}

/**
 * True when the assistant turn *ends* on a tool_call block (needs a follow-up turn).
 * Native MCP tools run inside LibreChat's agent loop and are followed by more
 * assistant text in the same stream — those must NOT trigger auto-continue.
 */
function isToolCallTurn(content) {
  const trimmed = (content || '').trimEnd()
  return (
    /```tool[_-]call\n[\s\S]*?```\s*$/i.test(trimmed) ||
    /tool[_-]call:\s*\n(?:[ \t]+[^\n]+\n?)+\s*$/i.test(trimmed)
  )
}

/**
 * Decide what to do after an assistant turn completes:
 *  - 'continue' : tool_call block detected — auto-fire next turn silently
 *  - 'wait'     : Q&A questions or schema approval — stop and wait for user
 *  - 'idle'     : normal informational message — wait for user
 */
function classifyTurn(content) {
  if (isToolCallTurn(content))  return 'continue'
  if (hasSchema(content))       return 'wait'      // schema → show approval card
  if (isQaTurn(content))        return 'wait'      // questions → let user answer
  return 'idle'
}

/** Expand legacy ```tool_call``` fences inside assistant content into tool rows. */
function expandLegacyToolFences(messages) {
  const out = []
  for (const m of messages) {
    if (m.role !== 'assistant' || !m.content || !parseToolCallBlocks(m.content).length) {
      out.push(m)
      continue
    }
    const blocks = parseToolCallBlocks(m.content)
    let cursor = 0
    let seg = 0
    for (const block of blocks) {
      const idx = m.content.indexOf(block.raw, cursor)
      if (idx === -1) continue
      const before = m.content.slice(cursor, idx).trim()
      if (before) {
        out.push({
          ...m,
          id: seg === 0 ? m.id : `${m.id}-t${seg}`,
          content: before,
          pending: false,
        })
        seg += 1
      }
      out.push({
        role: 'tool',
        toolPhase: 'call',
        toolName: block.name,
        args: block.args || '{}',
        summary: summarizeToolCall(block.name, block.args || '{}'),
        content: '',
        status: 'done',
        ts: m.ts,
        id: `${m.id}-tc${seg}`,
      })
      seg += 1
      cursor = idx + block.raw.length
    }
    const after = m.content.slice(cursor).trim()
    if (after) {
      out.push({
        ...m,
        id: seg === 0 ? m.id : `${m.id}-t${seg}`,
        content: after,
        pending: false,
      })
    }
  }
  return out
}

/** Mark running tool-call rows done. Optionally append a result row when payload exists. */
function markRunningToolsDone(prev, { resultByCallId = null } = {}) {
  const out = []
  for (const m of prev) {
    if (m.role === 'tool' && m.toolPhase === 'call' && m.status === 'running') {
      out.push({ ...m, status: 'done' })
      const payload = resultByCallId?.[m.id]
      if (payload != null && payload !== '') {
        out.push({
          role: 'tool',
          toolPhase: 'result',
          toolName: m.toolName,
          content: typeof payload === 'string' ? payload : '',
          result: typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2),
          status: 'done',
          callId: m.id,
          ts: new Date().toISOString(),
          id: `tr-${m.id}`,
        })
      }
    } else {
      out.push(m)
    }
  }
  return out
}

function isContentfulAssistant(m) {
  return m?.role === 'assistant'
    && (Boolean((m.content || '').trim()) || Boolean((m.thinking || '').trim()))
}

/**
 * LibreChat often buffers assistant text until a step finishes, while Atlys
 * MCP progress emits tool chips in real time. When tools land first, move the
 * *first* delayed narration bubble back before that orphan tool run.
 *
 * Do NOT relocate later bubbles — that piles "report ready" (and mid-step
 * narration) in front of every tool.
 */
function relocateAssistantBeforeTrailingTools(transcript, assistantId) {
  const idx = transcript.findIndex(m => m.id === assistantId)
  if (idx <= 0) return transcript

  let insertAt = idx
  let j = idx - 1
  while (j >= 0) {
    const m = transcript[j]
    if (m.role === 'tool') {
      insertAt = j
      j -= 1
      continue
    }
    // Skip empty working placeholders sandwiched in the tool run.
    if (
      m.role === 'assistant'
      && !(m.content || '').trim()
      && !(m.thinking || '').trim()
    ) {
      j -= 1
      continue
    }
    break
  }
  if (insertAt === idx) return transcript

  // If narration already sits before these tools, keep this bubble after them.
  for (let k = insertAt - 1; k >= 0; k -= 1) {
    const m = transcript[k]
    if (m.role === 'user' || m.id === 'welcome') break
    if (isContentfulAssistant(m) && m.id !== assistantId) return transcript
  }

  const row = transcript[idx]
  const without = transcript.filter((_, i) => i !== idx)
  return [...without.slice(0, insertAt), row, ...without.slice(insertAt)]
}

/**
 * Repair persisted turns where over-eager relocate left:
 *   user → [assistants…] → [tools…]
 * instead of:
 *   user → first assistant → [tools…] → remaining assistants
 */
function repairCollapsedAssistantToolOrder(messages) {
  if (!messages?.length) return messages
  const out = []
  let i = 0
  while (i < messages.length) {
    const head = messages[i]
    out.push(head)
    i += 1
    if (head.role !== 'user' && head.id !== 'welcome') continue

    const segment = []
    while (i < messages.length && messages[i].role !== 'user') {
      segment.push(messages[i])
      i += 1
    }
    out.push(...reorderOrphanToolSegment(segment))
  }
  return out
}

function isIncompleteToolFp(fp) {
  return !fp || fp.endsWith('::') || fp.endsWith('::{}') || fp.endsWith('::null')
}

/**
 * Find where the final report starts inside a buffered assistant bubble.
 * LibreChat often concatenates mid-turn lines without newlines
 * ("…for context.Here are the numbers"), so markers must match mid-string.
 */
function findAnswerCut(content) {
  if (!content) return -1
  const markers = [
    /Here's the answer\b/i,
    /Here is the answer\b/i,
    /Here are the (?:numbers|results|figures|findings)\b/i,
    /Here's what I found\b/i,
    /Here is what I found\b/i,
    /\*\*Key takeaways\b/i,
    /#{1,3}\s+[A-Z][^\n]{8,}/,
    /^\|.+\|/m,
  ]
  let cut = -1
  for (const re of markers) {
    const m = re.exec(content)
    if (m && (cut < 0 || m.index < cut)) cut = m.index
  }
  return cut
}

/**
 * When LibreChat dumps preamble + final answer into one assistant bubble,
 * split on a clear answer marker so tools sit between narration and the
 * report:  preamble → tools → answer.
 */
function splitAssistantAroundTools(assistant, tools) {
  if (!tools?.length) return [assistant]
  const content = assistant.content || ''
  const cut = findAnswerCut(content)
  if (cut < 0) {
    // No marker. If this already looks like a final report, prefer tools → answer
    // over answer → tools (the broken relocate shape).
    const looksFinal = content.length > 400 || (content.includes('|') && /\|.+\|/.test(content))
    if (looksFinal) return [...tools, { ...assistant, pending: false }]
    return [assistant, ...tools]
  }
  const before = content.slice(0, cut).trim()
  const after = content.slice(cut).trim()
  if (!before || !after) {
    if (!before && after) return [...tools, { ...assistant, content: after, pending: false }]
    return [assistant, ...tools]
  }
  return [
    { ...assistant, content: before, pending: false },
    ...tools,
    {
      ...assistant,
      id: `${assistant.id}-answer`,
      content: after,
      thinking: undefined,
      pending: false,
      statusText: undefined,
    },
  ]
}

function toolRowFingerprint(m) {
  return m.fingerprint || toolCallFingerprint(m.toolName || m.name, m.args || '{}')
}

/**
 * Drop LibreChat empty-arg stubs that arrive *after* a real call of the same
 * tool (e.g. trailing `aggregate {}`). Keep leading empty-arg calls that are
 * distinct work (`db_schema {}` listing tables before `db_schema {table}`).
 */
function stripRedundantIncompleteTools(tools) {
  const seenComplete = new Set()
  const out = []
  for (const t of tools) {
    const bare = bareToolName(t.toolName || t.name)
    const fp = toolRowFingerprint(t)
    if (!isIncompleteToolFp(fp)) {
      seenComplete.add(bare)
      out.push(t)
      continue
    }
    if (seenComplete.has(bare)) continue
    out.push(t)
  }
  return out
}

function dedupeToolRows(tools) {
  const seen = new Set()
  const out = []
  for (const m of stripRedundantIncompleteTools(tools)) {
    const fp = toolRowFingerprint(m)
    // Include empty-arg calls (db_schema::{} etc.) — those are real, and stream
    // replays often duplicate them.
    const key = fp || `${bareToolName(m.toolName || m.name)}::${m.id}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(m)
  }
  return out
}

const DISCOVERY_TOOLS = new Set(['db_schema', 'get_context'])
const QUERY_TOOLS = new Set(['aggregate', 'sample_rows', 'table_stats'])

/** Split tools into discovery → query → write phases for interleaving narration. */
function partitionToolPhases(tools) {
  const discovery = []
  const query = []
  const write = []
  for (const t of tools) {
    const bare = bareToolName(t.toolName || t.name)
    if (DISCOVERY_TOOLS.has(bare)) discovery.push(t)
    else if (QUERY_TOOLS.has(bare)) query.push(t)
    else write.push(t)
  }
  return [discovery, query, write].filter(phase => phase.length > 0)
}

/**
 * True when, after dropping tool rows, assistants don't interleave with tools
 * (tools are one block, possibly with assistants only before and/or after).
 * Already-interleaved turns (assistant↔tool↔assistant↔tool) are left alone.
 */
function isCollapsedToolShape(segment, tools) {
  if (!tools.length) return false
  const toolIds = new Set(tools.map(t => t.id))
  const nonTools = segment.filter(m => m.role !== 'tool' || !toolIds.has(m.id))
  // Recreate: find positions of kept tools in original segment
  const keptIdx = []
  for (let i = 0; i < segment.length; i += 1) {
    if (segment[i].role === 'tool' && toolIds.has(segment[i].id)) keptIdx.push(i)
  }
  if (!keptIdx.length) return false
  const first = keptIdx[0]
  const last = keptIdx[keptIdx.length - 1]
  // Contiguous in the *filtered* sense: every index between first/last that is a
  // kept tool or a dropped tool/empty assistant is OK; a contentful assistant
  // between kept tools means true interleaving.
  for (let i = first; i <= last; i += 1) {
    const m = segment[i]
    if (m.role === 'tool') continue
    if (m.role === 'assistant' && !isContentfulAssistant(m)) continue
    if (isContentfulAssistant(m)) return false
  }
  // Also treat leading-tools / trailing-tools / tools-then-assistant as collapsed
  // even when dropped stubs sat after the assistant (those are no longer kept).
  void nonTools
  return true
}

function reorderOrphanToolSegment(segment) {
  if (segment.length < 2) return segment

  const tools = dedupeToolRows(segment.filter(m => m.role === 'tool'))
  const contentful = segment.filter(isContentfulAssistant)
  const empties = segment.filter(m => m.role === 'assistant' && !isContentfulAssistant(m))
  const rawToolCount = segment.filter(m => m.role === 'tool').length

  if (!isCollapsedToolShape(segment, tools)) {
    // Interleaved turn — only strip redundant stubs / exact dupes.
    if (tools.length === rawToolCount) return segment
    const keep = new Set(tools.map(t => t.id))
    return segment.filter(m => m.role !== 'tool' || keep.has(m.id))
  }
  if (!tools.length) {
    return segment.filter(m => m.role !== 'tool')
  }
  if (contentful.length < 1) {
    return [...tools, ...empties]
  }

  const toolIdSet = new Set(tools.map(t => t.id))
  const firstToolIdx = segment.findIndex(m => m.role === 'tool' && toolIdSet.has(m.id))
  const lastToolIdx = (() => {
    for (let i = segment.length - 1; i >= 0; i -= 1) {
      if (segment[i].role === 'tool' && toolIdSet.has(segment[i].id)) return i
    }
    return -1
  })()
  const asstBefore = contentful.some(a => segment.findIndex(m => m.id === a.id) < firstToolIdx)
  const asstAfter = contentful.some(a => segment.findIndex(m => m.id === a.id) > lastToolIdx)

  // Already sequenced as preamble → tools → answer: only stub-clean in place.
  if (asstBefore && asstAfter) {
    const keep = toolIdSet
    return segment.filter(m => m.role !== 'tool' || keep.has(m.id))
  }

  // Single narration bubble (common when LibreChat buffers the whole turn).
  // Prefer: preamble → tools → answer when we can see a clear answer marker.
  if (contentful.length === 1) {
    return [...splitAssistantAroundTools(contentful[0], tools), ...empties]
  }

  const [first, ...rest] = contentful
  // All assistants piled on one side of the tools (over-eager relocate).
  // Re-interleave by discovery/query/write phases when every assistant was before tools.
  if (asstBefore && !asstAfter) {
    const phases = partitionToolPhases(tools)
    const out = [first]
    for (let i = 0; i < phases.length; i += 1) {
      out.push(...phases[i])
      if (i < rest.length) out.push(rest[i])
    }
    if (rest.length > phases.length) out.push(...rest.slice(phases.length))
    out.push(...empties)
    return out
  }

  // Tools first, then multiple assistants — keep tools together, then narrations.
  return [...tools, ...contentful, ...empties]
}

export default function ChatPanel({ onRefresh, onPreview }) {
  const [conversationId, setConversationId] = useState(() => resolveActiveChatId())
  const [messages, setMessages]             = useState([WELCOME_MSG])
  const [input, setInput]                   = useState('')
  const [loading, setLoading]               = useState(false)
  const [booting, setBooting]               = useState(true)
  const [showUpload, setShowUpload]         = useState(false)
  const [conversations, setConversations]   = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)

  const listRef           = useRef(null)
  const inputRef          = useRef(null)
  const messagesRef       = useRef(messages)
  const conversationIdRef = useRef(conversationId)
  const loadingRef        = useRef(false)
  const autoContinueRef   = useRef(0)   // counts consecutive auto-continues
  const abortRef          = useRef(null)
  const maxToolCallsRef   = useRef(DEFAULT_MAX_TOOL_CALLS)
  const toolSeriesCountRef = useRef(0)
  const stopRequestedRef  = useRef(false)
  const stickToBottomRef  = useRef(true)
  const pollTimerRef      = useRef(null)
  const [showJumpDown, setShowJumpDown] = useState(false)
  const [contextWindow, setContextWindow] = useState(DEFAULT_CONTEXT_WINDOW)

  useEffect(() => { messagesRef.current = messages }, [messages])
  useEffect(() => { conversationIdRef.current = conversationId }, [conversationId])
  useEffect(() => { loadingRef.current = loading }, [loading])

  useEffect(() => {
    let cancelled = false
    getAgentStatus()
      .then((s) => {
        if (cancelled) return
        const n = Number(s?.max_tool_calls_per_series)
        if (Number.isFinite(n) && n >= 1) maxToolCallsRef.current = Math.floor(n)
        const ctx = Number(s?.context_window)
        if (Number.isFinite(ctx) && ctx >= 1000) setContextWindow(Math.floor(ctx))
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const isNearBottom = useCallback(() => {
    const el = listRef.current
    if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_PX
  }, [])

  /** Scroll to bottom only while the user is following the stream (or force=true). */
  const scrollBottom = useCallback((force = false) => {
    const el = listRef.current
    if (!el) return
    if (!force && !stickToBottomRef.current) return
    el.scrollTop = el.scrollHeight
  }, [])

  useEffect(() => {
    scrollBottom()
  }, [messages, scrollBottom])

  // After boot / chat switch, list mounts only once booting=false — scroll then.
  useEffect(() => {
    if (booting) return
    stickToBottomRef.current = true
    setShowJumpDown(false)
    requestAnimationFrame(() => scrollBottom(true))
  }, [booting, conversationId, scrollBottom])

  const onListScroll = useCallback(() => {
    const near = isNearBottom()
    stickToBottomRef.current = near
    setShowJumpDown(!near)
  }, [isNearBottom])

  const jumpToLatest = useCallback(() => {
    stickToBottomRef.current = true
    setShowJumpDown(false)
    scrollBottom(true)
  }, [scrollBottom])

  const chatStats = useMemo(() => {
    const usable = messages.filter(m => m.id !== 'welcome')
    const userTurns = usable.filter(m => m.role === 'user').length
    const toolCalls = usable.filter(m => m.role === 'tool' && m.toolPhase !== 'result').length
    const tokens = estimateChatTokens(messages)
    const pct = contextWindow > 0
      ? Math.min(100, (tokens / contextWindow) * 100)
      : 0
    return { userTurns, toolCalls, tokens, pct, msgCount: usable.length }
  }, [messages, contextWindow])

  /** For each message index: doc paths already shown by earlier save_document tools. */
  const shownDocsBeforeIndex = useMemo(() => {
    const out = []
    const seen = new Set()
    for (const m of messages) {
      out.push(seen.size ? new Set(seen) : EMPTY_DOC_PATHS)
      const path = savedDocPathFromToolMsg(m)
      if (path) seen.add(path)
    }
    return out
  }, [messages])

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const rows = await listConversations()
      setConversations(rows)
    } catch {
      /* keep prior list */
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const persistMessages = useCallback(async (id, msgs, { status } = {}) => {
    // Drop welcome + empty pending assistant; keep completed / partial content.
    const toSave = msgs.filter(m => {
      if (m.id === 'welcome') return false
      if (m.pending && !(m.content || '').trim() && !(m.thinking || '').trim()) return false
      return true
    })
    if (!toSave.length) return
    try {
      await saveConversationMessages(id, toSave, status ? { status } : {})
      await refreshHistory()
    } catch (err) {
      console.warn('Failed to persist chat:', err)
    }
  }, [refreshHistory])

  const hydrateMessages = useCallback((raw) => {
    const restored = (raw || []).map(m => {
      if (m.role === 'tool' && m.toolPhase === 'call' && !m.summary) {
        return { ...m, summary: summarizeToolCall(m.toolName, m.args || '{}') }
      }
      return m
    })
    return repairCollapsedAssistantToolOrder(expandLegacyToolFences(restored))
  }, [])

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current != null) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const startPolling = useCallback((id) => {
    stopPolling()
    setLoading(true)
    loadingRef.current = true
    const tick = async () => {
      if (conversationIdRef.current !== id) return
      try {
        const data = await getConversationMessages(id)
        if (conversationIdRef.current !== id) return
        if (!data.missing) {
          let repaired = hydrateMessages(data.messages)
          if (data.status === 'running') {
            const busy = repaired.some(m =>
              (m.role === 'tool' && m.status === 'running')
              || (m.role === 'assistant' && m.pending),
            )
            if (!busy) {
              repaired = [
                ...repaired,
                {
                  role: 'assistant',
                  content: '',
                  statusText: 'Working…',
                  pending: true,
                  ts: new Date().toISOString(),
                  id: `poll-pending-${id}`,
                },
              ]
            }
          }
          setMessages(withWelcome(repaired))
          messagesRef.current = withWelcome(repaired)
        }
        if (data.status !== 'running') {
          stopPolling()
          setLoading(false)
          loadingRef.current = false
          refreshHistory()
          if (onRefresh) onRefresh()
          inputRef.current?.focus()
        }
      } catch {
        /* keep polling — transient blips during reload */
      }
    }
    tick()
    pollTimerRef.current = setInterval(tick, 1200)
  }, [hydrateMessages, onRefresh, refreshHistory, stopPolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  const loadConversation = useCallback(async (id, { pushUrl = false } = {}) => {
    stopPolling()
    setConversationId(id)
    conversationIdRef.current = id
    setStoredActiveChat(id)
    writeChatIdToUrl(id, { replace: !pushUrl })
    setInput('')
    setShowUpload(false)
    setBooting(true)
    stickToBottomRef.current = true
    setShowJumpDown(false)
    try {
      const data = await getConversationMessages(id)
      if (data.missing) {
        setMessages([WELCOME_MSG])
        setLoading(false)
        loadingRef.current = false
      } else {
        const repaired = hydrateMessages(data.messages)
        setMessages(withWelcome(repaired))
        messagesRef.current = withWelcome(repaired)
        // Persist repaired order so refresh stays correct (only when idle).
        if (data.status !== 'running') {
          const restored = data.messages || []
          if (repaired.length === restored.length
            ? repaired.some((m, idx) => m.id !== restored[idx]?.id)
            : true) {
            persistMessages(id, withWelcome(repaired))
          }
          setLoading(false)
          loadingRef.current = false
        } else {
          // Agent still working in the background — follow store updates.
          startPolling(id)
        }
      }
    } catch {
      setMessages([WELCOME_MSG])
      setLoading(false)
      loadingRef.current = false
    } finally {
      setBooting(false)
    }
  }, [hydrateMessages, persistMessages, startPolling, stopPolling])

  const stopGenerating = useCallback(() => {
    stopRequestedRef.current = true
    autoContinueRef.current = MAX_AUTO_CONTINUE // prevent silent auto-continue after stop
    stopPolling()
    const cid = conversationIdRef.current
    try {
      abortRef.current?.abort()
    } catch {
      /* ignore */
    }
    stopConversation(cid).catch(() => {})
  }, [stopPolling])

  const startNewChat = useCallback(async () => {
    stopGenerating()
    const id = newConversationId()
    try {
      await createConversation(id)
    } catch {
      /* file is created lazily on first save anyway */
    }
    setLoading(false)
    loadingRef.current = false
    toolSeriesCountRef.current = 0
    stopRequestedRef.current = false
    autoContinueRef.current = 0
    setConversationId(id)
    conversationIdRef.current = id
    setStoredActiveChat(id)
    writeChatIdToUrl(id, { replace: false })
    stickToBottomRef.current = true
    setShowJumpDown(false)
    setMessages([WELCOME_MSG])
    setInput('')
    setShowUpload(false)
    setBooting(false)
    inputRef.current?.focus()
  }, [stopGenerating])

  // Bootstrap: restore active chat + history list
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const id = resolveActiveChatId()
      if (!cancelled) await loadConversation(id)
      if (!cancelled) await refreshHistory()
    })()
    return () => { cancelled = true }
  }, [loadConversation, refreshHistory])

  // Browser back/forward: switch chat from ?chat=
  useEffect(() => {
    const onPop = () => {
      if (loadingRef.current) stopGenerating()
      const id = resolveActiveChatId()
      if (id !== conversationIdRef.current) {
        loadConversation(id)
      }
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [loadConversation, stopGenerating])

  /**
   * Core send logic — takes user message text, appends user & assistant turns,
   * streams from the API, and decides whether to trigger auto-continue or refresh.
   *
   * Tool calls are separate `role: 'tool'` rows. Transcript updates are applied
   * synchronously (not via queued setState updaters) so post-tool answer text
   * cannot be lost to React batching / stale assistantId closures.
   */
  const sendMessage = useCallback(async (text, extraMessages = [], isAutoContinue = false) => {
    if (!text.trim() && !extraMessages.length && !isAutoContinue) return
    if (loadingRef.current && !isAutoContinue) return

    if (!isAutoContinue) {
      autoContinueRef.current = 0
      toolSeriesCountRef.current = 0
      stopRequestedRef.current = false
      // New user turn → follow the stream again.
      stickToBottomRef.current = true
      setShowJumpDown(false)
    }

    const cid = conversationIdRef.current
    const now = () => new Date().toISOString()
    const ac = new AbortController()
    abortRef.current = ac
    const maxTools = maxToolCallsRef.current || DEFAULT_MAX_TOOL_CALLS

    const userMsg = (text.trim() || extraMessages.length) ? {
      role: 'user',
      content: text,
      ts: now(),
      id: `u-${Date.now()}`,
    } : null

    let assistantId = `a-${Date.now()}`
    const pendingAssistant = {
      role: 'assistant',
      content: '',
      statusText: 'Working…',
      ts: now(),
      id: assistantId,
      pending: true,
    }

    const base = messagesRef.current
    // Live transcript — mutated synchronously as SSE events arrive.
    let transcript = [
      ...base,
      ...extraMessages,
      ...(userMsg ? [userMsg] : []),
      pendingAssistant,
    ]
    if (!isAutoContinue) {
      // Ensure the new turn is visible before tokens arrive.
      requestAnimationFrame(() => scrollBottom(true))
    }
    // Always publish the *latest* transcript (via messagesRef). Never close over
    // a stale snap — the old rAF helper dropped bursts and looked like a freeze.
    let rafId = null
    let publishQueued = false
    let lastFlushMs = 0
    const publish = ({ immediate = false } = {}) => {
      messagesRef.current = transcript.map(m => ({ ...m }))
      const apply = () => {
        publishQueued = false
        rafId = null
        lastFlushMs = performance.now()
        setMessages(messagesRef.current)
      }
      if (immediate) {
        if (rafId != null) {
          cancelAnimationFrame(rafId)
          rafId = null
        }
        publishQueued = false
        flushSync(apply)
        return
      }
      // Force a real paint at least every ~80ms while tokens stream.
      if (performance.now() - lastFlushMs > 80) {
        if (rafId != null) {
          cancelAnimationFrame(rafId)
          rafId = null
        }
        publishQueued = false
        flushSync(apply)
        return
      }
      if (publishQueued) return
      publishQueued = true
      rafId = requestAnimationFrame(apply)
    }
    publish({ immediate: true })
    setInput('')
    setLoading(true)

    // Persist the user turn before streaming so a reload mid-run still has history.
    // The server marks status=running and keeps updating the transcript in the background.
    if (!isAutoContinue) {
      await persistMessages(cid, transcript)
    }

    // Build model history. Tool rows become short assistant notes so a silent
    // auto-continue still sees what was called (Agents API may not replay tools
    // from conversationId alone when we also send a messages array).
    const apiHistory = [...base, ...extraMessages, ...(userMsg ? [userMsg] : [])]
      .filter(m => m.id !== 'welcome')
      .flatMap(m => {
        if (m.role === 'tool' && m.toolPhase === 'call') {
          const args = (m.args || '{}').trim() || '{}'
          return [{
            role: 'assistant',
            content: `[tool_call] ${m.toolName || 'tool'} ${args}`,
          }]
        }
        if (m.role === 'tool') return []
        const content = stripToolCallFences(m.content || '') || m.content || ''
        if (!(m.role === 'user' || m.role === 'assistant') || !content) return []
        return [{ role: m.role, content }]
      })
    // Silent auto-continue needs a user turn for the Agents API.
    if (isAutoContinue && !userMsg) {
      apiHistory.push({
        role: 'user',
        content: 'Continue from the tool results and answer my last question.',
      })
    }

    let finalAssistantText = ''
    let sawNativeTools = false
    let textAfterLastTool = ''
    let needNewAssistant = false
    // Fingerprints already rendered this turn (name + normalized args).
    const seenToolFingerprints = new Set()

    const finalizeAssistant = (id) => {
      transcript = transcript
        .map(m => (m.id === id ? { ...m, pending: false, statusText: undefined } : m))
        .filter(m => !(m.id === id && !(m.content || '').trim() && !(m.thinking || '').trim()))
    }

    /** Keep a trailing pending assistant bubble so the UI shows "working". */
    const ensureWorkingPlaceholder = (statusText = 'Working…') => {
      const cur = transcript.find(m => m.id === assistantId)
      const isEmptyPending = cur
        && cur.role === 'assistant'
        && cur.pending
        && !(cur.content || '').trim()
      if (isEmptyPending) {
        transcript = transcript.map(m =>
          m.id === assistantId ? { ...m, statusText, pending: true } : m
        )
        return
      }
      // Drop any other empty pending assistants, then append a fresh one.
      transcript = transcript.filter(m => !(
        m.role === 'assistant'
        && m.pending
        && !(m.content || '').trim()
        && !(m.thinking || '').trim()
      ))
      assistantId = `a-${Date.now()}`
      transcript = [
        ...transcript,
        {
          role: 'assistant',
          content: '',
          statusText,
          ts: now(),
          id: assistantId,
          pending: true,
        },
      ]
      needNewAssistant = false
    }

    const setAssistantStatus = (text) => {
      ensureWorkingPlaceholder(text)
    }

    let terminalNoteWritten = false
    const finishStopped = async (reason) => {
      if (terminalNoteWritten) {
        setLoading(false)
        return
      }
      terminalNoteWritten = true
      transcript = markRunningToolsDone(transcript)
      finalizeAssistant(assistantId)
      transcript = [
        ...transcript.filter(m => !(
          m.role === 'assistant'
          && m.pending
          && !(m.content || '').trim()
          && !(m.thinking || '').trim()
        )),
        {
          role: 'assistant',
          content: reason,
          ts: now(),
          id: `stop-${Date.now()}`,
        },
      ]
      publish({ immediate: true })
      await persistMessages(cid, transcript, { status: 'idle' })
      setLoading(false)
      autoContinueRef.current = 0
      inputRef.current?.focus()
    }

    try {
      await chatStream(
        apiHistory,
        null,
        async (_full, meta) => {
          if (ac.signal.aborted || stopRequestedRef.current) {
            setLoading(false)
            return
          }

          const finalId = meta?.conversationId || cid
          if (finalId !== cid) {
            setConversationId(finalId)
            conversationIdRef.current = finalId
            setStoredActiveChat(finalId)
            writeChatIdToUrl(finalId, { replace: true })
          }

          transcript = markRunningToolsDone(transcript)
          finalizeAssistant(assistantId)
          transcript = repairCollapsedAssistantToolOrder(
            expandLegacyToolFences(transcript),
          )
          publish({ immediate: true })

          await persistMessages(finalId, transcript, { status: 'idle' })
          setLoading(false)

          // Auto-continue ONLY for legacy ```tool_call``` fences in assistant text.
          // Native MCP tools already ran in-process — silently re-firing the turn
          // was re-invoking the same tools 5–10× and flooding the UI.
          const decision = sawNativeTools
            ? 'idle'
            : classifyTurn(finalAssistantText)

          if (decision === 'continue') {
            if (stopRequestedRef.current) {
              inputRef.current?.focus()
              return
            }
            if (autoContinueRef.current >= MAX_AUTO_CONTINUE) {
              transcript = [...transcript, {
                role: 'assistant',
                content: '⚠️ The pipeline took more steps than expected. Please type a message to continue.',
                ts: now(),
                id: `warn-${Date.now()}`,
              }]
              publish()
              inputRef.current?.focus()
              return
            }
            autoContinueRef.current += 1
            await new Promise(r => setTimeout(r, 600))
            if (ac.signal.aborted || stopRequestedRef.current) return
            sendMessage('', [], true)
          } else {
            autoContinueRef.current = 0
            if (
              sawNativeTools
              && !textAfterLastTool.trim()
              && !finalAssistantText.trim()
            ) {
              // Tools finished but the model never streamed a reply — ask the user
              // instead of silently re-running the same tool series.
              const hasHint = transcript.some(m => String(m.id || '').startsWith('hint-'))
              if (!hasHint) {
                transcript = [...transcript, {
                  role: 'assistant',
                  content: 'Tools finished, but no reply was streamed. Type **continue** if you want me to keep going.',
                  ts: now(),
                  id: `hint-${Date.now()}`,
                }]
                publish({ immediate: true })
                await persistMessages(finalId, transcript, { status: 'idle' })
              }
            }
            inputRef.current?.focus()
            if (onRefresh) onRefresh()
          }
        },
        {
          conversationId: cid,
          signal: ac.signal,
          extendSeries: Boolean(isAutoContinue),
          onEvent: (ev) => {
            if (ac.signal.aborted || stopRequestedRef.current) return

            if (ev.type === 'tool_limit') {
              const limit = ev.limit || maxTools
              const used = ev.used != null ? ev.used : limit
              stopRequestedRef.current = true
              try { ac.abort() } catch { /* ignore */ }
              stopConversation(cid).catch(() => {})
              finishStopped(
                `⚠️ Tool-call limit reached (${used}/${limit} in this series). `
                + 'Reply with **continue** (or any new message) to allow another round of tools.',
              )
              return
            }

            if (ev.type === 'status') {
              // Keep a working indicator whenever we're still waiting on upstream.
              const cur = transcript.find(m => m.id === assistantId)
              const hasContent = Boolean((cur?.content || '').trim() || (cur?.thinking || '').trim())
              if (!hasContent) {
                const secs = ev.waitedSec != null ? Math.floor(ev.waitedSec) : null
                const anyToolRunning = transcript.some(
                  m => m.role === 'tool' && m.status === 'running',
                )
                let label
                if (anyToolRunning) {
                  label = 'Running tools…'
                } else if (sawNativeTools) {
                  label = secs != null
                    ? `Generating reply… (${secs}s)`
                    : 'Generating reply…'
                } else if (ev.phase === 'connected') {
                  label = 'Connected — waiting for the agent…'
                } else {
                  label = secs != null
                    ? `Waiting for the agent… (${secs}s)`
                    : 'Waiting for the agent…'
                }
                setAssistantStatus(label)
                publish({ immediate: true })
              }
              return
            }

            if (ev.type === 'tool_call') {
              const args = ev.arguments || '{}'
              const fp = toolCallFingerprint(ev.name, args)
              // Drop stream replays and identical re-emits for this turn.
              if (fp && seenToolFingerprints.has(fp)) {
                return
              }
              if (fp && !isIncompleteToolFp(fp)) {
                seenToolFingerprints.add(fp)
              }

              if (ev.source === 'atlys') {
                toolSeriesCountRef.current += 1
              }

              sawNativeTools = true
              textAfterLastTool = ''
              // Finalize any prior answer bubble, then show the tool + a working row.
              finalizeAssistant(assistantId)
              const used = ev.used != null ? ev.used : toolSeriesCountRef.current
              const limit = ev.limit || maxTools
              transcript = [
                ...transcript,
                {
                  role: 'tool',
                  toolPhase: 'call',
                  toolName: ev.name,
                  args,
                  summary: summarizeToolCall(ev.name, args),
                  content: '',
                  status: 'running',
                  ts: now(),
                  id: `tc-${ev.id || Date.now()}`,
                  source: ev.source || 'stream',
                  fingerprint: fp,
                },
              ]
              ensureWorkingPlaceholder(
                used && limit
                  ? `Running tools… (${used}/${limit})`
                  : 'Running tools…',
              )
              publish({ immediate: true })

              if (ev.source === 'atlys' && toolSeriesCountRef.current >= maxTools) {
                ensureWorkingPlaceholder(
                  `Tool limit ${maxTools}/${maxTools} — finishing this call…`,
                )
                publish({ immediate: true })
              }
              return
            }

            if (ev.type === 'tool_discard') {
              // LibreChat stub whose args completed to an Atlys-already-shown call.
              const idKey = ev.id ? `tc-${ev.id}` : null
              if (!idKey) return
              transcript = transcript.filter(m => m.id !== idKey)
              publish({ immediate: true })
              return
            }

            if (ev.type === 'tool_done') {
              const idKey = ev.id ? `tc-${ev.id}` : null
              const bare = bareToolName(ev.name)
              let matched = false
              transcript = transcript.map(m => {
                if (matched || m.role !== 'tool' || m.toolPhase !== 'call' || m.status !== 'running') {
                  return m
                }
                const sameId = idKey && m.id === idKey
                const sameName = bareToolName(m.toolName) === bare
                if (!sameId && !sameName) return m
                matched = true
                return { ...m, status: 'done', ok: ev.ok !== false }
              })
              if (matched) {
                const stillRunning = transcript.some(
                  m => m.role === 'tool' && m.status === 'running',
                )
                ensureWorkingPlaceholder(
                  stillRunning ? 'Running tools…' : 'Generating reply…',
                )
                publish({ immediate: true })
              }
              return
            }

            if (ev.type === 'tool_args') {
              const idKey = ev.id ? `tc-${ev.id}` : null
              const target = transcript.find(m => (
                m.role === 'tool'
                && m.toolPhase === 'call'
                && m.status === 'running'
                && (m.id === idKey || (ev.id && String(m.id).includes(String(ev.id))))
              ))
              if (!target) return

              const newFp = toolCallFingerprint(target.toolName, ev.arguments)
              // Args resolved to a fingerprint we already rendered (Atlys side-channel).
              if (!isIncompleteToolFp(newFp) && (
                seenToolFingerprints.has(newFp)
                || transcript.some(m => m.id !== target.id && m.fingerprint === newFp)
              )) {
                transcript = transcript.filter(m => m.id !== target.id)
                publish({ immediate: true })
                return
              }
              if (!isIncompleteToolFp(newFp)) seenToolFingerprints.add(newFp)

              transcript = transcript.map(m => (
                m.id === target.id
                  ? {
                    ...m,
                    args: ev.arguments,
                    summary: summarizeToolCall(m.toolName, ev.arguments),
                    fingerprint: newFp || m.fingerprint,
                  }
                  : m
              ))
              publish()
              return
            }

            if (ev.type === 'thinking') {
              // Reuse the working placeholder when present; otherwise open a new bubble.
              const cur = transcript.find(m => m.id === assistantId)
              const wasEmpty = cur
                && !(cur.content || '').trim()
                && !(cur.thinking || '').trim()
              const canReuse = cur?.role === 'assistant' && cur.pending
              if (!canReuse || needNewAssistant) {
                needNewAssistant = false
                transcript = markRunningToolsDone(transcript)
                // Remove empty working placeholders before starting the real reply.
                transcript = transcript.filter(m => !(
                  m.role === 'assistant'
                  && m.pending
                  && !(m.content || '').trim()
                  && !(m.thinking || '').trim()
                ))
                assistantId = `a-${Date.now()}`
                transcript = [
                  ...transcript,
                  {
                    role: 'assistant',
                    content: '',
                    thinking: ev.text,
                    ts: now(),
                    id: assistantId,
                    pending: true,
                  },
                ]
                transcript = relocateAssistantBeforeTrailingTools(transcript, assistantId)
              } else {
                transcript = transcript.map(m =>
                  m.id === assistantId
                    ? {
                      ...m,
                      thinking: (m.thinking || '') + ev.text,
                      statusText: undefined,
                      pending: true,
                    }
                    : m
                )
                if (wasEmpty) {
                  transcript = relocateAssistantBeforeTrailingTools(transcript, assistantId)
                }
              }
              publish({ immediate: true })
              return
            }

            if (ev.type === 'text') {
              finalAssistantText += ev.text
              if (sawNativeTools) textAfterLastTool += ev.text

              const cur = transcript.find(m => m.id === assistantId)
              const wasEmpty = cur
                && !(cur.content || '').trim()
                && !(cur.thinking || '').trim()
              const canReuse = cur?.role === 'assistant' && cur.pending
              if (!canReuse || needNewAssistant) {
                needNewAssistant = false
                transcript = markRunningToolsDone(transcript)
                transcript = transcript.filter(m => !(
                  m.role === 'assistant'
                  && m.pending
                  && !(m.content || '').trim()
                  && !(m.thinking || '').trim()
                ))
                assistantId = `a-${Date.now()}`
                transcript = [
                  ...transcript,
                  {
                    role: 'assistant',
                    content: ev.text,
                    ts: now(),
                    id: assistantId,
                    pending: true,
                  },
                ]
                transcript = relocateAssistantBeforeTrailingTools(transcript, assistantId)
                publish({ immediate: true })
              } else {
                transcript = transcript.map(m =>
                  m.id === assistantId
                    ? {
                      ...m,
                      content: (m.content || '') + ev.text,
                      statusText: undefined,
                      pending: true,
                    }
                    : m
                )
                if (wasEmpty) {
                  transcript = relocateAssistantBeforeTrailingTools(transcript, assistantId)
                  publish({ immediate: true })
                } else {
                  publish()
                }
              }
            }
          },
        },
      )
    } catch (err) {
      const userStopped = stopRequestedRef.current
      const aborted = ac.signal.aborted || err?.name === 'AbortError'
      if (userStopped) {
        if (conversationIdRef.current !== cid) {
          setLoading(false)
          return
        }
        await finishStopped('⏹ Generation stopped.')
        autoContinueRef.current = 0
        return
      }
      // Tab reload / navigation tears down the fetch with "Error in input stream".
      // The agent keeps running server-side — poll the store instead of persisting
      // a permanent error bubble (server owns the transcript for background runs).
      if (isStreamDisconnectError(err) || aborted) {
        if (conversationIdRef.current !== cid) {
          setLoading(false)
          return
        }
        startPolling(cid)
        autoContinueRef.current = 0
        return
      }
      transcript = markRunningToolsDone(transcript).map(m =>
        m.id === assistantId
          ? { ...m, content: m.content || `Error: ${err.message}`, pending: false }
          : m
      )
      publish()
      persistMessages(cid, transcript, { status: 'idle' })
      setLoading(false)
      autoContinueRef.current = 0
    } finally {
      if (abortRef.current === ac) abortRef.current = null
    }
  }, [persistMessages, onRefresh, scrollBottom, startPolling])

  const onKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!loading) sendMessage(input)
    }
  }, [input, loading, sendMessage])

  const onApprove = useCallback((runId) => {
    sendMessage(`approve ${runId}`)
  }, [sendMessage])

  const onReject = useCallback((runId) => {
    sendMessage(`reject ${runId}`)
  }, [sendMessage])

  const onSpecUploaded = useCallback((feature) => {
    setShowUpload(false)
    const text = `I've uploaded the "${feature}" spec. Please interrogate it.`
    sendMessage(text)
  }, [sendMessage])

  const onSelectChat = useCallback((id) => {
    if (id === conversationIdRef.current) return
    if (loadingRef.current) stopGenerating()
    loadConversation(id, { pushUrl: true })
  }, [loadConversation, stopGenerating])

  return (
    <div className="panel panel-left chat-panel">
      <ChatHistory
        conversations={conversations}
        activeId={conversationId}
        loading={historyLoading}
        disabled={false}
        onSelect={onSelectChat}
        onNewChat={startNewChat}
      />

      <div className="chat-main">
        {booting ? (
          <div className="messages-list chat-booting">Loading chat…</div>
        ) : (
          <div className="messages-list-wrap">
            <div
              className="messages-list"
              ref={listRef}
              onScroll={onListScroll}
            >
              {messages.map((msg, i) => (
                <ChatMessage
                  key={msg.id}
                  msg={msg}
                  onApprove={onApprove}
                  onReject={onReject}
                  onPreview={onPreview}
                  shownDocPaths={shownDocsBeforeIndex[i]}
                />
              ))}
            </div>
            {showJumpDown && (
              <button
                type="button"
                className="jump-latest-btn"
                onClick={jumpToLatest}
                title="Jump to latest"
                aria-label="Jump to latest messages"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                  <path d="M12 5v14M5 12l7 7 7-7" />
                </svg>
                Latest
              </button>
            )}
          </div>
        )}

        {showUpload && (
          <FileUpload
            onUploaded={onSpecUploaded}
            onClose={() => setShowUpload(false)}
          />
        )}

        <div className="chat-input-area">
          {!booting && (
            <div className="chat-stats" title="Approximate context usage from chat text (chars÷4). Not billed usage.">
              <div className="chat-stats-usage">
                <div className="chat-stats-bar" aria-hidden="true">
                  <div
                    className={`chat-stats-bar-fill${chatStats.pct >= 85 ? ' warn' : ''}${chatStats.pct >= 95 ? ' danger' : ''}`}
                    style={{ width: `${Math.max(chatStats.pct, chatStats.tokens > 0 ? 2 : 0)}%` }}
                  />
                </div>
                <span className="chat-stats-tokens">
                  ~{fmtCompact(chatStats.tokens)} / {fmtCompact(contextWindow)} tokens
                </span>
              </div>
              <span className="chat-stats-meta">
                {chatStats.userTurns} turn{chatStats.userTurns === 1 ? '' : 's'}
                {chatStats.toolCalls > 0 ? ` · ${chatStats.toolCalls} tool${chatStats.toolCalls === 1 ? '' : 's'}` : ''}
                {chatStats.msgCount > 0 ? ` · ${chatStats.msgCount} msgs` : ''}
              </span>
            </div>
          )}
          <div className="input-row">
            <button
              className="attach-btn"
              onClick={() => setShowUpload(v => !v)}
              title="Upload spec.md + events.ndjson"
              aria-label="Upload spec files"
              disabled={booting}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>

            <textarea
              ref={inputRef}
              id="chat-input"
              className="chat-textarea"
              placeholder={loading ? 'Generating… (Stop to cancel)' : 'Type a message… (Enter to send)'}
              value={input}
              onChange={e => { setInput(e.target.value); autoResize(e.target) }}
              onKeyDown={onKeyDown}
              rows={1}
              disabled={booting}
            />

            {loading ? (
              <button
                type="button"
                className="send-btn stop-btn"
                onClick={stopGenerating}
                title="Stop generating"
                aria-label="Stop generating"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <rect x="6" y="6" width="12" height="12" rx="1.5" />
                </svg>
              </button>
            ) : (
              <button
                type="button"
                className="send-btn"
                onClick={() => sendMessage(input)}
                disabled={booting || !input.trim()}
                title="Send"
                aria-label="Send message"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
