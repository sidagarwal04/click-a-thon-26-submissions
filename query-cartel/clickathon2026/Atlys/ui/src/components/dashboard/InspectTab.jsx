import { useCallback, useEffect, useRef, useState } from 'react'
import Tooltip from '../common/Tooltip'
import { fmtDateTime } from '../../utils'
import { EVENT_TIP, RUN_COLUMN_TIP, STATE_TIP, TOOL_COLUMN_TIP } from './tips'
import { getRuns, getRun, getToolCalls, getPendingRuns } from '../../api/client'

/**
 * Small fetch helper: data + refresh metadata, with optional polling.
 * Keeps previous data visible while refetching (stale-while-revalidate).
 */
function useInspectFetch(fetcher, { pollMs = null, deps = [] } = {}) {
  const [data, setData] = useState(null)
  const [meta, setMeta] = useState({ state: 'idle', at: null, error: null })
  const seqRef = useRef(0)

  // Unmount guard: bump the sequence so any in-flight load's setState is
  // dropped (review pass fix).
  useEffect(() => () => { seqRef.current += 1 }, [])

  const load = useCallback(async () => {
    const seq = ++seqRef.current
    setMeta(m => ({ ...m, state: 'refreshing' }))
    try {
      const result = await fetcher()
      if (seq !== seqRef.current) return
      setData(result)
      setMeta({ state: 'fresh', at: Date.now(), error: null })
    } catch (e) {
      if (seq !== seqRef.current) return
      setMeta(m => ({ ...m, state: 'error', error: e }))
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!pollMs) return
    const id = setInterval(load, pollMs)
    return () => clearInterval(id)
  }, [load, pollMs])

  return { data, meta, reload: load }
}

const STATE_CLASS = {
  proposed: 'run-state proposed',
  running: 'run-state running',
  approved: 'run-state approved',
  rejected: 'run-state rejected',
  failed: 'run-state failed',
  aborted: 'run-state aborted',
  unknown: 'run-state unknown',
}

function RunStateBadge({ state }) {
  return (
    <Tooltip content={STATE_TIP[state] || 'Lifecycle state of this run.'}>
      <span className={STATE_CLASS[state] || 'run-state unknown'}>{state || 'unknown'}</span>
    </Tooltip>
  )
}

function traceUrl(traceId, langfuseBaseUrl, langfuseProjectId) {
  if (!traceId) return null
  const base = (langfuseBaseUrl || '').replace(/\/$/, '')
  return langfuseProjectId
    ? `${base}/project/${langfuseProjectId}/traces/${traceId}`
    : `${base}/traces?search=${traceId}`
}

function TraceLink({ traceId, langfuseBaseUrl, langfuseProjectId, label }) {
  const url = traceUrl(traceId, langfuseBaseUrl, langfuseProjectId)
  if (!url) return <span className="inspect-trace-none">—</span>
  return (
    <a className="trace-link" href={url} target="_blank" rel="noopener noreferrer" title="Open trace in Langfuse">
      {label || `Trace ${traceId.slice(0, 8)}`}
    </a>
  )
}

const EMPTY_LIST = []

function SectionHeader({ title, meta, onRefresh, count }) {
  return (
    <div className="inspect-section-header">
      <h4 className="inspect-section-title">
        {title}
        {count != null && <span className="inspect-section-count">{count}</span>}
      </h4>
      <div className="inspect-section-actions">
        <button
          className={`inspect-refresh-btn${meta.state === 'refreshing' ? ' pulsing' : ''}`}
          onClick={onRefresh}
          title={`Refresh ${title}`}
          aria-label={`Refresh ${title}`}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
          </svg>
        </button>
      </div>
    </div>
  )
}

function EmptyHint({ text }) {
  return (
    <div className="empty-state">
      <svg className="empty-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4M12 8h.01" />
      </svg>
      <span>{text}</span>
    </div>
  )
}

/**
 * Inspect tab (docs/inspect-tab-plan.md Wave A): Runs, event chain, tool calls,
 * pending runs — the judge/PM's follow-the-chain view of the pipeline.
 */
export default function InspectTab({ langfuseBaseUrl, langfuseProjectId, refreshToken = 0 }) {
  const [selectedRunId, setSelectedRunId] = useState(null)

  const runs = useInspectFetch(() => getRuns(50), { pollMs: 10000, deps: [] })
  const toolCalls = useInspectFetch(() => getToolCalls({ limit: 100 }), { deps: [] })
  const pendingRuns = useInspectFetch(() => getPendingRuns(), { pollMs: 10000, deps: [] })

  // When a new run appears (chat finished), auto-select the newest run's chain.
  // Stable empty ref so the effect below doesn't churn every render.
  const runsData = runs.data ?? EMPTY_LIST
  useEffect(() => {
    if (!runsData.length) return
    if (!selectedRunId || !runsData.some(r => r.run_id === selectedRunId)) {
      setSelectedRunId(runsData[0].run_id)
    }
  }, [runsData, selectedRunId])

  const chain = useInspectFetch(
    () => (selectedRunId ? getRun(selectedRunId) : Promise.resolve({ run: null, chain: [] })),
    { pollMs: 10000, deps: [selectedRunId] },
  )

  // External refresh (chat finished / dashboard refresh button)
  useEffect(() => {
    if (refreshToken > 0) {
      runs.reload()
      toolCalls.reload()
      pendingRuns.reload()
    }
  }, [refreshToken]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedRun = runsData.find(r => r.run_id === selectedRunId) || runsData[0] || null
  const chainData = chain.data || { run: null, chain: [] }
  const selectedState = chainData.run?.state || selectedRun?.state || null

  return (
    <div className="inspect-wrap">
      {/* ── Runs ── */}
      <section className="inspect-section">
        <SectionHeader title="Runs" meta={runs.meta} onRefresh={runs.reload} count={runsData.length} />
        {runsData.length === 0 ? (
          <EmptyHint text="No runs yet — run a spec to see its chain" />
        ) : (
          <div className="inspect-table-wrap">
            <table className="inspect-table">
              <thead>
                <tr>
                  <th><Tooltip content={RUN_COLUMN_TIP.run} position="bottom" focusable={false}>Run</Tooltip></th>
                  <th><Tooltip content={RUN_COLUMN_TIP.feature} position="bottom" focusable={false}>Feature</Tooltip></th>
                  <th><Tooltip content={RUN_COLUMN_TIP.state} position="bottom" focusable={false}>State</Tooltip></th>
                  <th><Tooltip content={RUN_COLUMN_TIP.events} position="bottom" focusable={false}>Events</Tooltip></th>
                  <th><Tooltip content={RUN_COLUMN_TIP.duration} position="bottom" focusable={false}>Duration</Tooltip></th>
                  <th><Tooltip content={RUN_COLUMN_TIP.trace} position="bottom" focusable={false}>Trace</Tooltip></th>
                  <th><Tooltip content={RUN_COLUMN_TIP.created} position="bottom" focusable={false}>Created</Tooltip></th>
                </tr>
              </thead>
              <tbody>
                {runsData.map(r => (
                  <tr
                    key={r.run_id}
                    className={r.run_id === selectedRunId ? 'selected' : ''}
                    onClick={() => setSelectedRunId(r.run_id)}
                  >
                    <td className="inspect-mono">{r.run_id.slice(0, 8)}</td>
                    <td>{r.spec_dir || '—'}</td>
                    <td><RunStateBadge state={r.state} /></td>
                    <td className="inspect-num">{r.event_count ?? 0}</td>
                    <td className="inspect-num">
                      {r.duration_ms != null ? `${(r.duration_ms / 1000).toFixed(1)}s` : '—'}
                    </td>
                    <td>
                      <TraceLink traceId={r.trace_id} langfuseBaseUrl={langfuseBaseUrl} langfuseProjectId={langfuseProjectId} />
                    </td>
                    <td className="inspect-muted">{fmtDateTime(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Event chain ── */}
      <section className="inspect-section">
        <SectionHeader
          title={`Event chain${selectedRun ? ` — ${selectedRun.spec_dir || selectedRun.run_id.slice(0, 8)}` : ''}`}
          meta={chain.meta}
          onRefresh={chain.reload}
          count={chainData.chain?.length ?? 0}
        />
        {selectedState === 'running' && (
          <div className="inspect-live-banner">⏳ Run in progress — polling every 10s</div>
        )}
        {!chainData.chain || chainData.chain.length === 0 ? (
          <EmptyHint text="Select a run to see its event chain" />
        ) : (
          <div className="event-chain">
            {chainData.chain.map((ev, i) => (
              <EventChainRow
                key={ev.event_id || i}
                ev={ev}
                index={i}
                total={chainData.chain.length}
                langfuseBaseUrl={langfuseBaseUrl}
                langfuseProjectId={langfuseProjectId}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── Tool calls ── */}
      <section className="inspect-section">
        <SectionHeader title="Tool calls" meta={toolCalls.meta} onRefresh={toolCalls.reload} count={toolCalls.data?.length ?? 0} />
        {!toolCalls.data || toolCalls.data.length === 0 ? (
          <EmptyHint text="No tool calls yet" />
        ) : (
          <div className="inspect-table-wrap">
            <table className="inspect-table inspect-table-compact">
              <thead>
                <tr>
                  <th><Tooltip content={TOOL_COLUMN_TIP.tool} position="bottom" focusable={false}>Tool</Tooltip></th>
                  <th><Tooltip content={TOOL_COLUMN_TIP.arguments} position="bottom" focusable={false}>Arguments</Tooltip></th>
                  <th><Tooltip content={TOOL_COLUMN_TIP.trace} position="bottom" focusable={false}>Trace</Tooltip></th>
                  <th><Tooltip content={TOOL_COLUMN_TIP.time} position="bottom" focusable={false}>Time</Tooltip></th>
                </tr>
              </thead>
              <tbody>
                {toolCalls.data.map(tc => (
                  <tr key={tc.event_id}>
                    <td>
                      <Tooltip content="MCP tool invoked by the chat agent." position="bottom" focusable={false}>
                        <span className="inspect-tool-name">{tc.tool}</span>
                      </Tooltip>
                    </td>
                    <td className="inspect-args-cell">
                      <Tooltip content={fullArgs(tc.arguments)} position="bottom" wide focusable={false}>
                        <code className="inspect-args">{summarizeArgs(tc.arguments)}</code>
                      </Tooltip>
                    </td>
                    <td>
                      <TraceLink traceId={tc.trace_id} langfuseBaseUrl={langfuseBaseUrl} langfuseProjectId={langfuseProjectId} />
                    </td>
                    <td className="inspect-muted">{fmtDateTime(tc.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Pending runs ── */}
      <section className="inspect-section">
        <SectionHeader title="Approval queue" meta={pendingRuns.meta} onRefresh={pendingRuns.reload} count={pendingRuns.data?.length ?? 0} />
        {!pendingRuns.data || pendingRuns.data.length === 0 ? (
          <EmptyHint text="No pending approvals" />
        ) : (
          <div className="pending-runs-list">
            {pendingRuns.data.map(p => (
              <div className="pending-run-row" key={p.run_id}>
                <span className="inspect-mono">{p.run_id.slice(0, 8)}</span>
                <RunStateBadge state={p.state} />
                <span className="inspect-muted">{p.spec_dir || '—'}</span>
                <span className="inspect-muted">{fmtDateTime(p.created_at)}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

/** Full args blob for the tooltip (capped so huge payloads stay readable). */
function fullArgs(args, max = 600) {
  let text
  try {
    text = typeof args === 'string' ? args : JSON.stringify(args, null, 2)
  } catch {
    text = String(args)
  }
  if (!text) return 'No arguments'
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

/** Truncate a JSON args blob for the tool-calls table (plan §A6). */
function summarizeArgs(args, max = 120) {
  let text
  try {
    text = typeof args === 'string' ? args : JSON.stringify(args)
  } catch {
    text = String(args)
  }
  if (!text) return '—'
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

function EventChainRow({ ev, index, total, langfuseBaseUrl, langfuseProjectId }) {
  const [open, setOpen] = useState(false)
  const [full, setFull] = useState(false)
  const summary = payloadSummary(ev.payload)
  const raw = formatPayload(ev.payload)
  const truncated = raw.length > 2000
  const shown = full ? raw : raw.slice(0, 2000)

  return (
    <div className={`event-chain-row${open ? ' open' : ''}`}>
      <button className="event-chain-head" onClick={() => setOpen(v => !v)} aria-expanded={open}>
        <span className="event-chain-marker">
          {open
            ? <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="6 9 12 15 18 9" /></svg>
            : <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="9 6 15 12 9 18" /></svg>}
        </span>
        <Tooltip content={EVENT_TIP[ev.event_type] || ev.event_type} position="bottom" focusable={false}>
          <span className="event-type-badge">{ev.event_type}</span>
        </Tooltip>
        <span className="event-chain-meta">
          <Tooltip content="Which agent produced this event." focusable={false}>
            <span className="inspect-mono">{ev.actor}</span>
          </Tooltip>
          <Tooltip content="Version of this event's aggregate." focusable={false}>
            <span className="inspect-muted">v{ev.version}</span>
          </Tooltip>
          <Tooltip content="Position within this run's chain." focusable={false}>
            <span className="inspect-muted">{index + 1}/{total}</span>
          </Tooltip>
        </span>
        <span className="event-chain-summary">{summary}</span>
      </button>
      {open && (
        <div className="event-chain-body">
          <div className="event-chain-facts">
            <span className="inspect-muted">event_id</span>
            <Tooltip content={ev.event_id}><code className="inspect-mono">{ev.event_id.slice(0, 12)}…</code></Tooltip>
            <span className="inspect-muted">aggregate</span>
            <Tooltip content={ev.aggregate_id}><code className="inspect-mono">{ev.aggregate_id}</code></Tooltip>
            <TraceLink traceId={ev.trace_id} langfuseBaseUrl={langfuseBaseUrl} langfuseProjectId={langfuseProjectId} />
          </div>
          <pre className="event-chain-payload">
            {shown}
            {truncated && !full && (
              <button className="inspect-show-more" onClick={() => setFull(true)}>Show full payload ({raw.length.toLocaleString()} chars)</button>
            )}
          </pre>
        </div>
      )}
    </div>
  )
}

function payloadSummary(payload) {
  if (!payload || typeof payload !== 'object') return ''
  if (payload.schema_card?.table) return `table=${payload.schema_card.table}`
  if (payload.tool) return `tool=${payload.tool}`
  if (payload.spec_dir) return `spec=${payload.spec_dir}`
  if (payload.feature) return `feature=${payload.feature}`
  if (payload.run_id) return `run=${payload.run_id.slice(0, 8)}`
  const keys = Object.keys(payload)
  return keys.length ? keys.slice(0, 3).join(', ') : ''
}

function formatPayload(payload) {
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return String(payload)
  }
}
