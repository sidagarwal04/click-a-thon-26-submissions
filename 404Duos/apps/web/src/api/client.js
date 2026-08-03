const apiBase = (import.meta.env.VITE_API_URL ?? 'http://localhost:4000').replace(/\/$/, '')

/** In-flight + short TTL cache — React StrictMode remounts effects in dev and would otherwise double-fetch. */
const inflight = new Map()
const responseCache = new Map()
const CACHE_TTL_MS = 30_000

async function fetchJson(path) {
  if (!apiBase) throw new Error('VITE_API_URL is not set')

  const cached = responseCache.get(path)
  if (cached && Date.now() - cached.at < CACHE_TTL_MS) {
    return structuredClone(cached.data)
  }

  if (inflight.has(path)) {
    const data = await inflight.get(path)
    return structuredClone(data)
  }

  const promise = (async () => {
    const res = await fetch(`${apiBase}${path}`)
    if (!res.ok) {
      const body = await res.text()
      throw new Error(`API ${path} failed: ${res.status} ${body.slice(0, 160)}`)
    }
    const data = await res.json()
    responseCache.set(path, { at: Date.now(), data })
    return data
  })()

  inflight.set(path, promise)
  try {
    const data = await promise
    return structuredClone(data)
  } finally {
    inflight.delete(path)
  }
}

/** @param {{ granularity?: 'day' | 'hour' }} [opts] */
export async function listAlerts(opts = {}) {
  const granularity = opts.granularity === 'hour' ? 'hour' : 'day'
  return fetchJson(`/api/alerts?granularity=${encodeURIComponent(granularity)}`)
}

/** @param {string} alertId */
export async function getAlert(alertId) {
  return fetchJson(`/api/alerts/${encodeURIComponent(alertId)}`)
}

/** @param {string} investigationId */
export async function getInvestigation(investigationId) {
  return fetchJson(`/api/investigations/${encodeURIComponent(investigationId)}`)
}

/** Downloadable investigation evidence bundle. */
export async function exportInvestigationBundle(investigationId) {
  if (!apiBase) throw new Error('VITE_API_URL is not set')
  const res = await fetch(
    `${apiBase}/api/investigations/${encodeURIComponent(investigationId)}/export`,
  )
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`Export failed: ${res.status} ${body.slice(0, 180)}`)
  }
  return res.json()
}

/** @param {string} alertId */
export async function getInvestigationByAlert(alertId) {
  return fetchJson(`/api/alerts/${encodeURIComponent(alertId)}/investigation`)
}

export function clearApiCache() {
  inflight.clear()
  responseCache.clear()
}

/**
 * OpenAI-compatible chat against the InsightIQ API.
 * @param {{role: string, content: string}[]} messages
 * @param {{ investigationId?: string, alertId?: string, sessionId?: string }} [context]
 */
export async function sendChatMessage(messages, context = {}) {
  if (!apiBase) throw new Error('VITE_API_URL is not set')

  const seeded = [...messages]
  const contextId = context.investigationId || context.alertId
  if (contextId) {
    const hint = [
      context.investigationId ? `investigation ${context.investigationId}` : null,
      context.alertId ? `alert ${context.alertId}` : null,
    ]
      .filter(Boolean)
      .join(' / ')
    const firstUser = seeded.findIndex((m) => m.role === 'user')
    if (firstUser >= 0 && !seeded[firstUser].content.includes(contextId)) {
      seeded[firstUser] = {
        ...seeded[firstUser],
        content: `${seeded[firstUser].content}\n\n(Context: ${hint})`,
      }
    }
  }

  let sessionId = context.sessionId
  if (!sessionId && typeof window !== 'undefined') {
    sessionId = window.sessionStorage.getItem('insightiq-chat-session')
    if (!sessionId) {
      sessionId = `insightiq-web-${crypto.randomUUID()}`
      window.sessionStorage.setItem('insightiq-chat-session', sessionId)
    }
  }

  const res = await fetch(`${apiBase}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'insightiq-rca',
      messages: seeded,
      stream: false,
      investigationId: context.investigationId || undefined,
      alertId: context.alertId || undefined,
      sessionId: sessionId || undefined,
    }),
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`Chat failed: ${res.status} ${body.slice(0, 180)}`)
  }
  const data = await res.json()
  const text = data?.choices?.[0]?.message?.content
  if (!text) throw new Error('Empty chat response')
  return text
}

export async function getDashboardMeta() {
  return fetchJson('/api/dashboard/meta')
}

export async function queryDashboard(body) {
  if (!apiBase) throw new Error('VITE_API_URL is not set')
  const res = await fetch(`${apiBase}/api/dashboard/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Dashboard query failed: ${res.status} ${text.slice(0, 200)}`)
  }
  return res.json()
}

export async function getDashboardFilterValues({ dimension, start, end }) {
  const qs = new URLSearchParams({ dimension, start, end }).toString()
  const data = await fetchJson(`/api/dashboard/filters?${qs}`)
  return data.values || []
}
