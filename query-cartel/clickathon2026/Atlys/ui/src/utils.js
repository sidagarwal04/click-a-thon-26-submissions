import { useCallback, useRef } from 'react'

/** Parse run_id out of assistant message content if present */
export function extractRunId(text) {
  const m = text.match(/run[_\s]?id[:\s]+([a-f0-9-]{36})/i)
  return m ? m[1] : null
}

/** Format a UTC ISO timestamp for display (time; date if not today). */
export function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const today = new Date()
  const sameDay =
    d.getFullYear() === today.getFullYear()
    && d.getMonth() === today.getMonth()
    && d.getDate() === today.getDate()
  if (sameDay) return time
  const date = d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  return `${date} ${time}`
}

/** Format a UTC ISO timestamp as date+time */
export function fmtDateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/** Rough token estimate (chars/4). Matches common UI heuristics when usage isn't streamed. */
export function estimateTokensFromText(text) {
  if (!text) return 0
  return Math.ceil(String(text).length / 4)
}

/** Sum approximate tokens across chat transcript rows (excludes welcome). */
export function estimateChatTokens(messages) {
  if (!messages?.length) return 0
  let chars = 0
  for (const m of messages) {
    if (m.id === 'welcome') continue
    chars += (m.content || '').length
    chars += (m.thinking || '').length
    chars += (m.args || '').length
    if (typeof m.result === 'string') chars += m.result.length
    else if (m.result != null) {
      try { chars += JSON.stringify(m.result).length } catch { /* ignore */ }
    }
  }
  return Math.ceil(chars / 4)
}

/** Compact number for UI: 12400 → "12.4k". */
export function fmtCompact(n) {
  if (n == null || Number.isNaN(n)) return '0'
  const abs = Math.abs(n)
  if (abs < 1000) return String(Math.round(n))
  if (abs < 1_000_000) {
    const v = n / 1000
    return `${v >= 100 ? Math.round(v) : v.toFixed(1).replace(/\.0$/, '')}k`
  }
  const v = n / 1_000_000
  return `${v >= 100 ? Math.round(v) : v.toFixed(1).replace(/\.0$/, '')}M`
}

/** Auto-grow a textarea to fit its content */
export function autoResize(el) {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 140) + 'px'
}

/** Hook: scroll a ref element to the bottom */
export function useScrollBottom(dep) {
  const ref = useRef(null)
  const scroll = useCallback(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [])
  return [ref, scroll]
}
