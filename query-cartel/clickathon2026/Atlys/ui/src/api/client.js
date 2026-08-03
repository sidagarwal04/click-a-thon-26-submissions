// API client — all calls to FastAPI's REST + proxy endpoints
// Base URL is '' (relative) in both dev (Vite proxy → :8000) and prod (FastAPI serves the build)

const BASE = ''

const ACTIVE_CHAT_KEY = 'atlys.activeChat'

// ── Chat identity helpers ─────────────────────────────────────────────────────

export function newConversationId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export function readChatIdFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get('chat')
  } catch {
    return null
  }
}

export function writeChatIdToUrl(id, { replace = true } = {}) {
  const url = new URL(window.location.href)
  if (id) url.searchParams.set('chat', id)
  else url.searchParams.delete('chat')
  const next = `${url.pathname}${url.search}${url.hash}`
  if (replace) window.history.replaceState(null, '', next)
  else window.history.pushState(null, '', next)
}

export function getStoredActiveChat() {
  try {
    return localStorage.getItem(ACTIVE_CHAT_KEY)
  } catch {
    return null
  }
}

export function setStoredActiveChat(id) {
  try {
    if (id) localStorage.setItem(ACTIVE_CHAT_KEY, id)
    else localStorage.removeItem(ACTIVE_CHAT_KEY)
  } catch {
    /* ignore quota / private mode */
  }
}

/** Resolve active chat: URL → localStorage → mint new id (and sync URL/storage). */
export function resolveActiveChatId() {
  const fromUrl = readChatIdFromUrl()
  if (fromUrl) {
    setStoredActiveChat(fromUrl)
    return fromUrl
  }
  const stored = getStoredActiveChat()
  if (stored) {
    writeChatIdToUrl(stored, { replace: true })
    return stored
  }
  const id = newConversationId()
  setStoredActiveChat(id)
  writeChatIdToUrl(id, { replace: true })
  return id
}

// ── Chat proxy (→ LibreChat Agents API) ──────────────────────────────────────

/** Strip LibreChat MCP pluginKey suffix: `db_schema_mcp_atlys-orchestrator` → `db_schema`. */
export function bareToolName(name) {
  return String(name || 'tool').replace(/_mcp_[A-Za-z0-9_-]+$/, '')
}

/** Canonical JSON for tool-args so stream replays / key-order diffs match. */
export function stableToolArgs(args) {
  const raw = args == null ? '' : args
  let value = raw
  if (typeof raw === 'string') {
    const s = raw.trim()
    if (!s) return ''
    try { value = JSON.parse(s) } catch { return s }
  }
  const normalize = (v) => {
    if (Array.isArray(v)) return v.map(normalize)
    if (v && typeof v === 'object') {
      const out = {}
      for (const k of Object.keys(v).sort()) out[k] = normalize(v[k])
      return out
    }
    return v
  }
  try {
    return JSON.stringify(normalize(value))
  } catch {
    return String(raw)
  }
}

/** Fingerprint for deduping MCP side-channel vs LibreChat stream replays. */
export function toolCallFingerprint(name, args) {
  return `${bareToolName(name)}::${stableToolArgs(args)}`
}

/**
 * Split model content that embeds <think>…</think> (or <thinking>) blocks.
 * Handles an unclosed open tag (still streaming).
 */
export function splitThinkTags(chunk, state = { mode: 'text', buf: '' }) {
  let mode = state.mode || 'text'
  let textOut = ''
  let thinkOut = ''
  let i = 0
  const s = state.buf ? state.buf + chunk : chunk
  // Keep a tiny carry buffer for tags split across chunks.
  const carry = { mode, buf: '' }

  const openRe = /^<(think|thinking)(?:\s[^>]*)?>/i

  while (i < s.length) {
    if (mode === 'text') {
      const lt = s.indexOf('<', i)
      if (lt === -1) {
        textOut += s.slice(i)
        i = s.length
        break
      }
      textOut += s.slice(i, lt)
      const rest = s.slice(lt)
      // Incomplete tag at end of buffer — carry it.
      if (rest.length < 20 && !rest.includes('>')) {
        carry.buf = rest
        break
      }
      const m = openRe.exec(rest)
      if (m) {
        mode = 'think'
        i = lt + m[0].length
        continue
      }
      textOut += '<'
      i = lt + 1
      continue
    }

    // mode === 'think' — find a close tag anywhere ahead
    const lower = s.toLowerCase()
    const idxThink = lower.indexOf('</think>', i)
    const idxThinking = lower.indexOf('</thinking>', i)
    let closeIdx = -1
    let closeLen = 0
    if (idxThink !== -1 && (idxThinking === -1 || idxThink <= idxThinking)) {
      closeIdx = idxThink
      closeLen = '</think>'.length
    } else if (idxThinking !== -1) {
      closeIdx = idxThinking
      closeLen = '</thinking>'.length
    }
    if (closeIdx !== -1) {
      thinkOut += s.slice(i, closeIdx)
      i = closeIdx + closeLen
      mode = 'text'
      continue
    }
    // Still in think — if buffer ends with partial close tag, carry it.
    const tail = s.slice(i)
    const partial = tail.match(/<\/(?:thi(?:n(?:k(?:i(?:n(?:g)?)?)?)?)?)?$/i)
    if (partial && partial.index != null && partial.index === tail.length - partial[0].length) {
      thinkOut += tail.slice(0, partial.index)
      carry.buf = partial[0]
      break
    }
    thinkOut += tail
    i = s.length
  }

  carry.mode = mode
  return { text: textOut, thinking: thinkOut, state: carry }
}

/**
 * Stream a chat turn. Calls POST /api/proxy/chat and yields SSE events.
 *
 * Prefer the event callback so tool calls stay out of assistant text:
 *   onEvent({ type: 'text', text })
 *   onEvent({ type: 'thinking', text })
 *   onEvent({ type: 'tool_call', id, name, arguments })
 *   onEvent({ type: 'tool_args', id, arguments })
 *   onEvent({ type: 'tool_discard', id, name })  // stream stub matched Atlys fingerprint
 *   onDone(fullText, { conversationId })
 *
 * @param {Array} messages
 * @param {function} onChunkOrEvent
 * @param {function} onDone
 * @param {{ conversationId?: string, token?: string|null, onEvent?: function, signal?: AbortSignal }} [opts]
 */
export async function chatStream(messages, onChunkOrEvent, onDone, opts = {}) {
  const {
    conversationId = null,
    token = null,
    onEvent = null,
    signal = null,
    extendSeries = false,
  } =
    typeof opts === 'string' || opts === null
      ? { token: opts }
      : opts

  const emit = onEvent || ((ev) => {
    if (ev.type === 'text' && typeof onChunkOrEvent === 'function') {
      onChunkOrEvent(ev.text)
    }
  })
  const onTextChunk = onEvent ? null : onChunkOrEvent

  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const body = { messages, stream: true, extendSeries: Boolean(extendSeries) }
  if (conversationId) body.conversationId = conversationId

  const resp = await fetch(`${BASE}/api/proxy/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: signal || undefined,
  })

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ message: resp.statusText }))
    throw new Error(err.message || err.detail || `HTTP ${resp.status}`)
  }

  const echoedId = resp.headers.get('X-Conversation-Id') || conversationId

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let accumulated = ''
  const seenToolKeys = new Set()
  const seenToolFingerprints = new Set()
  let openTool = null // { key, name, arguments, index }
  let thinkState = { mode: 'text', buf: '' }

  const emitToolCall = (tool, source = 'stream', extra = {}) => {
    const name = bareToolName(tool.name)
    const arguments_ = tool.arguments || '{}'
    const argsStr = typeof arguments_ === 'string' ? arguments_ : JSON.stringify(arguments_ ?? {})
    const fp = toolCallFingerprint(name, argsStr)
    // Ignore LibreChat replays / duplicate ids for the same name+args.
    // Incomplete stubs (empty args) are keyed once; later fragments use tool_args.
    if (fp.endsWith('::') || fp.endsWith('::{}') || fp.endsWith('::null')) {
      if (seenToolKeys.has(`fp-pending:${tool.key}`)) return false
      seenToolKeys.add(`fp-pending:${tool.key}`)
    } else if (seenToolFingerprints.has(fp)) {
      return false
    } else {
      seenToolFingerprints.add(fp)
    }
    emit({
      type: 'tool_call',
      id: tool.key,
      name,
      arguments: argsStr,
      source,
      ...extra,
    })
    return true
  }

  const emitTextChunk = (raw) => {
    if (!raw) return
    const split = splitThinkTags(raw, thinkState)
    thinkState = split.state
    if (split.thinking) {
      emit({ type: 'thinking', text: split.thinking })
    }
    if (split.text) {
      accumulated += split.text
      emit({ type: 'text', text: split.text })
      if (onTextChunk) onTextChunk(split.text)
    }
  }

  const handleDelta = (delta) => {
    if (!delta || typeof delta !== 'object') return

    // Reasoning / thinking fields used by OpenAI-compatible + GLM-style APIs
    const reasoning =
      delta.reasoning_content
      ?? delta.reasoning
      ?? delta.thinking
      ?? (typeof delta.reasoning_text === 'string' ? delta.reasoning_text : '')
    if (reasoning) {
      emit({ type: 'thinking', text: String(reasoning) })
    }

    if (Array.isArray(delta.tool_calls)) {
      for (const tc of delta.tool_calls) {
        const fn = tc.function || {}
        const idx = typeof tc.index === 'number' ? tc.index : 0
        if (fn.name) {
          // Prefer stable index / existing open tool over a fresh random id each chunk.
          const key = tc.id
            || (openTool && openTool.index === idx ? openTool.key : null)
            || `idx-${idx}-${bareToolName(fn.name)}`
          if (openTool && openTool.key !== key && openTool.name && !seenToolKeys.has(openTool.key)) {
            seenToolKeys.add(openTool.key)
            emitToolCall(openTool)
          }
          if (!openTool || openTool.key !== key) {
            openTool = {
              key,
              name: fn.name,
              arguments: fn.arguments || '',
              index: idx,
            }
            if (!seenToolKeys.has(key)) {
              seenToolKeys.add(key)
              emitToolCall(openTool)
            }
          } else if (fn.arguments) {
            // Same tool id/index — append streamed argument fragments (don't reset).
            openTool.arguments = (openTool.arguments || '') + fn.arguments
            const fp = toolCallFingerprint(openTool.name, openTool.arguments)
            // Completed args match a tool we already showed via Atlys side-channel.
            if (fp && !fp.endsWith('::') && !fp.endsWith('::{}') && !fp.endsWith('::null')
                && seenToolFingerprints.has(fp)) {
              emit({ type: 'tool_discard', id: openTool.key, name: openTool.name })
            } else {
              if (!fp.endsWith('::') && !seenToolFingerprints.has(fp)) {
                seenToolFingerprints.add(fp)
              }
              emit({
                type: 'tool_args',
                id: openTool.key,
                arguments: openTool.arguments,
              })
            }
          }
        } else if (openTool && fn.arguments != null) {
          openTool.arguments += fn.arguments
          const fp = toolCallFingerprint(openTool.name, openTool.arguments)
          if (fp && !fp.endsWith('::') && !fp.endsWith('::{}') && !fp.endsWith('::null')
              && seenToolFingerprints.has(fp)) {
            emit({ type: 'tool_discard', id: openTool.key, name: openTool.name })
          } else {
            if (!fp.endsWith('::') && !seenToolFingerprints.has(fp)) {
              seenToolFingerprints.add(fp)
            }
            emit({
              type: 'tool_args',
              id: openTool.key,
              arguments: openTool.arguments,
            })
          }
        }
      }
    }

    // Some providers put tool calls on delta.function_call (legacy)
    if (delta.function_call?.name) {
      const key = delta.function_call.name
      openTool = {
        key,
        name: delta.function_call.name,
        arguments: delta.function_call.arguments || '',
        index: 0,
      }
      if (!seenToolKeys.has(key)) {
        seenToolKeys.add(key)
        emitToolCall(openTool)
      }
    }

    const text = delta.content ?? ''
    if (text) emitTextChunk(text)
  }

  const processSseLine = (line) => {
    const trimmed = line.trimEnd()
    if (!trimmed || trimmed.startsWith('event:')) return
    // Proxy keepalives / comments — surface as status so the UI isn't blank.
    if (trimmed.startsWith(':')) {
      const m = /waiting=([0-9.]+)/.exec(trimmed)
      emit({
        type: 'status',
        phase: trimmed.includes('connected') ? 'connected' : 'waiting',
        waitedSec: m ? Number(m[1]) : undefined,
      })
      return
    }
    if (!trimmed.startsWith('data:')) return
    const payload = trimmed.startsWith('data: ')
      ? trimmed.slice(6).trim()
      : trimmed.slice(5).trim()
    if (!payload) return
    if (payload === '[DONE]') {
      if (openTool && !seenToolKeys.has(openTool.key)) {
        seenToolKeys.add(openTool.key)
        emitToolCall(openTool)
        openTool = null
      }
      // Fire-and-forget; caller may be async (persist). Don't block the reader.
      Promise.resolve(onDone(accumulated, { conversationId: echoedId })).catch(() => {})
      return 'done'
    }
    try {
      const parsed = JSON.parse(payload)
      // Atlys MCP side-channel (tools while LibreChat is still buffering)
      const prog = parsed?.atlys_progress
      if (prog && typeof prog === 'object') {
        if (prog.type === 'tool_call') {
          const args = prog.arguments
          const argsStr = typeof args === 'string' ? args : JSON.stringify(args ?? {})
          emitToolCall(
            {
              key: prog.id || `mcp-${Date.now()}`,
              name: prog.name,
              arguments: argsStr,
            },
            'atlys',
            { used: prog.used, limit: prog.limit },
          )
        } else if (prog.type === 'tool_done') {
          emit({
            type: 'tool_done',
            id: prog.id,
            name: bareToolName(prog.name),
            ok: prog.ok !== false,
            source: 'atlys',
          })
        } else if (prog.type === 'tool_limit') {
          emit({
            type: 'tool_limit',
            id: prog.id,
            name: bareToolName(prog.name),
            used: prog.used,
            limit: prog.limit,
            source: 'atlys',
          })
        }
        return
      }
      // OpenAI chat.completion.chunk
      const delta = parsed?.choices?.[0]?.delta
      if (delta) {
        handleDelta(delta)
        return
      }
      // Some LibreChat / agent wrappers nest message
      const msgDelta = parsed?.message?.delta || parsed?.delta
      if (msgDelta) {
        handleDelta(msgDelta)
        return
      }
      // Rare: full message content (non-streaming fallback chunk)
      const content = parsed?.choices?.[0]?.message?.content
      if (typeof content === 'string' && content) {
        emitTextChunk(content)
      }
    } catch {
      // Non-JSON SSE events — skip
    }
  }

  // Yield to the browser event loop so React can paint between SSE events
  // when many lines arrive in one TCP chunk.
  const tick = () => new Promise((r) => setTimeout(r, 0))

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // Normalize CRLF; process complete lines immediately so UI paints ASAP.
    buffer = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    let n = 0
    for (const line of lines) {
      if (processSseLine(line) === 'done') return
      n += 1
      // Every few events, let the UI thread paint.
      if (n % 2 === 0) await tick()
    }
  }

  // Flush any trailing SSE line without final newline
  if (buffer.trim()) {
    if (processSseLine(buffer) === 'done') return
  }

  if (openTool && !seenToolKeys.has(openTool.key)) {
    seenToolKeys.add(openTool.key)
    emitToolCall(openTool)
  }
  await onDone(accumulated, { conversationId: echoedId })
}

// ── Conversations (Atlys store) ───────────────────────────────────────────────

export async function listConversations(limit = 50) {
  const resp = await fetch(`${BASE}/api/conversations?limit=${limit}`)
  if (!resp.ok) return []
  return resp.json()
}

export async function getConversationMessages(id) {
  const resp = await fetch(`${BASE}/api/conversations/${id}/messages`)
  if (resp.status === 404) return { id, messages: [], missing: true }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export async function saveConversationMessages(id, messages, { status } = {}) {
  const body = { messages }
  if (status) body.status = status
  const resp = await fetch(`${BASE}/api/conversations/${id}/messages`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `Failed to save chat: HTTP ${resp.status}`)
  }
  return resp.json()
}

export async function createConversation(id = null) {
  const resp = await fetch(`${BASE}/api/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(id ? { id } : {}),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** Cancel a background generation for this conversation. */
export async function stopConversation(id) {
  const resp = await fetch(`${BASE}/api/conversations/${id}/stop`, { method: 'POST' })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** True when the SSE body died because the tab reloaded / navigated away. */
export function isStreamDisconnectError(err) {
  if (!err) return false
  if (err.name === 'AbortError') return true
  const msg = String(err.message || err)
  return /input stream|network error|Failed to fetch|Load failed|BodyStreamBuffer|The user aborted a request/i.test(msg)
}

// ── Agent status ──────────────────────────────────────────────────────────────

export async function getAgentStatus() {
  const resp = await fetch(`${BASE}/api/agent-status`)
  if (!resp.ok) return { provisioned: false }
  return resp.json()
}

// ── Spec upload ───────────────────────────────────────────────────────────────

/**
 * Upload spec.md + events.ndjson pair.
 * @param {File} specFile
 * @param {File} eventsFile
 * @returns {Promise<{feature: string, dir: string}>}
 */
export async function uploadSpec(specFile, eventsFile) {
  const form = new FormData()
  form.append('spec', specFile)
  form.append('events', eventsFile)

  const resp = await fetch(`${BASE}/api/specs`, { method: 'POST', body: form })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `Upload failed: HTTP ${resp.status}`)
  }
  return resp.json()
}

// ── Dashboard reads ───────────────────────────────────────────────────────────

export const getInsights  = () => fetch(`${BASE}/api/insights`).then(r => r.json())
export const getChangelog = (scope = 'schema', limit = 50) =>
  fetch(`${BASE}/api/changelog?scope=${scope}&limit=${limit}`).then(r => r.json())
export const getContext   = (version = null) => {
  const url = version !== null ? `${BASE}/api/context?version=${version}` : `${BASE}/api/context`
  return fetch(url).then(r => r.json())
}
export const getContextVersions = () => fetch(`${BASE}/api/context-versions`).then(r => r.json())

export async function getEventLog(params = {}) {
  // Backward compatible: getEventLog(100) → { limit: 100 }
  if (typeof params === 'number') params = { limit: params }
  const qs = new URLSearchParams()
  if (params.limit != null) qs.set('limit', params.limit)
  if (params.run_id) qs.set('run_id', params.run_id)
  if (params.event_type) qs.set('event_type', params.event_type)
  if (params.actor) qs.set('actor', params.actor)
  if (params.before) qs.set('before', params.before)
  if (params.after) qs.set('after', params.after)
  if (params.count) qs.set('count', 1)
  const resp = await fetch(`${BASE}/api/event-log?${qs.toString()}`)
  const data = await resp.json()
  // Bare-array shape when no filters were passed — normalize to an object.
  return Array.isArray(data) ? { events: data, next_cursor: null, total: null } : data
}

export const getRuns = (limit = 50, state = null) => {
  const qs = new URLSearchParams({ limit })
  if (state) qs.set('state', state)
  return fetch(`${BASE}/api/runs?${qs.toString()}`).then(r => r.json())
}

export const getRun = (runId) =>
  fetch(`${BASE}/api/runs/${encodeURIComponent(runId)}`).then(r => r.json())

export const getToolCalls = (params = {}) => {
  const qs = new URLSearchParams()
  if (params.limit != null) qs.set('limit', params.limit)
  if (params.tool) qs.set('tool', params.tool)
  if (params.run_id) qs.set('run_id', params.run_id)
  return fetch(`${BASE}/api/tool-calls?${qs.toString()}`).then(r => r.json())
}

export const getPendingRuns = () => fetch(`${BASE}/api/pending-runs`).then(r => r.json())

export const getSpecs     = () => fetch(`${BASE}/api/specs`).then(r => r.json())

export async function getDocumentMetadata(path) {
  const resp = await fetch(`${BASE}/api/documents/metadata?path=${encodeURIComponent(path)}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export async function getDocumentContent(path) {
  const resp = await fetch(`${BASE}/api/documents/content?path=${encodeURIComponent(path)}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export function getDocumentDownloadUrl(path) {
  return `${BASE}/api/documents/download?path=${encodeURIComponent(path)}`
}

