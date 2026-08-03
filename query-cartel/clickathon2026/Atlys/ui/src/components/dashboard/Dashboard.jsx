import { useState, useEffect, useCallback, useRef } from 'react'
import InsightCard from './InsightCard'
import SchemaTimeline from './SchemaTimeline'
import ContextPanel from './ContextPanel'
import InspectTab from './InspectTab'
import { getInsights, getChangelog, getContext, getContextVersions } from '../../api/client'

/** Richer hover copy for each tab button (what you'll find inside). */
const TAB_TIP = {
  Insights: 'PM-ready insight cards: what the pipeline concluded about each feature, with confidence scores, evidence, and trace links.',
  Schema: 'The schema timeline: every table / column the pipeline created, with rationale and DDL diffs.',
  Context: 'The versioned feature context the agents reason from — with diff to the previous snapshot.',
  Inspect: 'The full run chain: events, tool calls, traces and the approval queue — follow what the agents actually did.',
}

/**
 * Tabs in priority order. Each carries a one-line description shown under the
 * tab bar, so a judge/PM immediately understands what a tab is *for*.
 */
const TABS = [
  { id: 'Insights', icon: 'insight', desc: 'PM-ready insight cards with confidence scores and evidence' },
  { id: 'Schema',   icon: 'schema',  desc: 'Every schema change the pipeline made, with rationale and diffs' },
  { id: 'Context',  icon: 'context', desc: 'The versioned feature context the agents reason from' },
  { id: 'Inspect',  icon: 'inspect', desc: 'The full run chain — events, tool calls, traces, approvals' },
]

const ACTIVE_TAB = TABS[0]

/**
 * Dashboard (docs/inspect-tab-plan.md Wave A + D, cleanup pass).
 *
 * Refresh UX:
 *  - stale-while-revalidate: previous data stays visible while refetching
 *  - refresh button pulses while a fetch is in flight (no "Updated…" chips)
 *  - abort + sequence guard: a slow old fetch cannot clobber newer data
 *  - Context version pin: chat-triggered refresh does NOT reset the pinned
 *    version — it refetches the pinned snapshot.
 */
export default function Dashboard({ langfuseBaseUrl, langfuseProjectId, refreshTrigger }) {
  const [tab, setTab]                 = useState(ACTIVE_TAB.id)
  const [data, setData]               = useState({})   // tab -> payload
  const [meta, setMeta]               = useState({})   // tab -> {state, error}
  const [versions, setVersions]       = useState([])
  const [selectedVersion, setSelectedVersion] = useState(null)
  const [inspectToken, setInspectToken] = useState(0)
  const abortRef   = useRef({})       // tab -> AbortController
  const seqRef     = useRef(0)        // global fetch sequence — stale-guard
  const selectedVersionRef = useRef(selectedVersion)
  selectedVersionRef.current = selectedVersion
  // dataRef avoids re-creating fetchTab (and thus effect churn) on every data
  // change — polling churn fix (review pass).
  const dataRef = useRef(data)
  dataRef.current = data

  const setTabMeta = useCallback((t, patch) => {
    setMeta(m => ({ ...m, [t]: { ...m[t], ...patch } }))
  }, [])

  const fetchTab = useCallback(async (t, { version = null, force = false } = {}) => {
    abortRef.current[t]?.abort()
    const controller = new AbortController()
    abortRef.current[t] = controller
    const seq = ++seqRef.current

    const haveData = dataRef.current[t] !== undefined && dataRef.current[t] !== null
    if (force || !haveData) {
      setTabMeta(t, { state: haveData ? 'refreshing' : 'loading' })
    }

    try {
      let payload
      if (t === 'Insights') {
        payload = await getInsights()
      } else if (t === 'Schema') {
        payload = await getChangelog('schema', 50)
      } else if (t === 'Context') {
        payload = await getContext(version)
        if (version === null && payload?.version !== undefined && selectedVersionRef.current === null) {
          setSelectedVersion(payload.version)
        }
        const vList = await getContextVersions()
        if (seq === seqRef.current) setVersions(vList)
      }
      if (seq !== seqRef.current) return // stale response — ignore
      setData(d => ({ ...d, [t]: payload }))
      setTabMeta(t, { state: 'fresh', error: null })
    } catch (e) {
      if (seq !== seqRef.current) return
      if (e?.name === 'AbortError') return
      // setTabMeta takes a patch object, NOT an updater fn — passing a
      // function here silently dropped the error state (review pass fix).
      setTabMeta(t, { state: 'error', error: e })
    }
  }, [setTabMeta])

  // Load on tab switch (aborts the previous tab's in-flight fetch)
  useEffect(() => {
    if (tab === 'Inspect') return // InspectTab manages its own fetches
    fetchTab(tab, tab === 'Context' ? { version: selectedVersion } : {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  // Chat finished → refresh active tab; Context keeps its pinned version.
  useEffect(() => {
    if (refreshTrigger <= 0) return
    if (tab === 'Inspect') {
      setInspectToken(v => v + 1)
    } else if (tab === 'Context') {
      fetchTab('Context', { version: selectedVersionRef.current })
    } else {
      fetchTab(tab, { force: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger])

  // Cleanup aborts on unmount — copy the ref map so the cleanup never reads a
  // mutated ref (oxlint react-hooks warning).
  useEffect(() => {
    const aborts = abortRef.current
    return () => {
      Object.values(aborts).forEach(c => c?.abort())
    }
  }, [])

  const handleVersionChange = (version) => {
    setSelectedVersion(version)
    fetchTab('Context', { version })
  }

  const handleRefresh = () => {
    if (tab === 'Inspect') {
      setInspectToken(v => v + 1)
    } else if (tab === 'Context') {
      fetchTab('Context', { version: selectedVersionRef.current, force: true })
    } else {
      fetchTab(tab, { force: true })
    }
  }

  const activeMeta = meta[tab] || { state: 'idle' }
  const activeTab = TABS.find(t => t.id === tab) || ACTIVE_TAB

  return (
    <div className="panel dashboard-panel">
      {/* Tabs */}
      <div className="dash-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`dash-tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
            id={`dash-tab-${t.id.toLowerCase()}`}
            // Native title: the tab bar clips overflow, so a styled tooltip
            // would be cut off — the browser-rendered one never is.
            title={TAB_TIP[t.id]}
          >
            <TabIcon name={t.icon} />
            {t.id}
          </button>
        ))}
        <button
          className={`dash-tab dash-refresh-btn${activeMeta.state === 'refreshing' ? ' pulsing' : ''}`}
          onClick={handleRefresh}
          title="Refresh the current tab's data"
          id="dash-refresh-btn"
          aria-label="Refresh"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
          </svg>
        </button>
      </div>

      {/* Active-tab description strip */}
      <div className="dash-tab-desc">
        <TabIcon name={activeTab.icon} small />
        <span>{activeTab.desc}</span>
      </div>

      {/* Content */}
      <div className={`dash-content${tab === 'Context' ? ' dash-content-flush' : ''}`}>
        {tab === 'Inspect' ? (
          <InspectTab
            langfuseBaseUrl={langfuseBaseUrl}
            langfuseProjectId={langfuseProjectId}
            refreshToken={inspectToken}
          />
        ) : (
          <TabBody
            tab={tab}
            data={data[tab]}
            loading={activeMeta.state === 'loading'}
            langfuseBaseUrl={langfuseBaseUrl}
            langfuseProjectId={langfuseProjectId}
            versions={versions}
            onVersionChange={handleVersionChange}
            refreshError={activeMeta.error}
          />
        )}
      </div>
    </div>
  )
}

function TabIcon({ name, small = false }) {
  const size = small ? 12 : 14
  return (
    <svg className="dash-tab-icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      {name === 'insight' && <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 0 1-2 2h0a2 2 0 0 1-2-2v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />}
      {name === 'schema' && <path d="M3 3h18v18H3zM3 9h18M9 3v18M3 15h18" />}
      {name === 'context' && <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h6" />}
      {name === 'inspect' && <path d="M22 12h-4l-3 9L9 3l-3 9H2" />}
    </svg>
  )
}

function TabBody({ tab, data, loading, langfuseBaseUrl, langfuseProjectId, versions, onVersionChange, refreshError }) {
  const firstLoad = loading && (data === undefined || data === null)
  if (firstLoad) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
        <div className="loading-dots"><span /><span /><span /></div>
      </div>
    )
  }

  return (
    <>
      {refreshError && (
        <div className="dash-refresh-error">
          Couldn't refresh — showing data from the last successful load.
        </div>
      )}
      {tab === 'Insights' && (
        data?.length
          ? data.map((ins, i) => (
              <InsightCard key={i} insight={ins} langfuseBaseUrl={langfuseBaseUrl} langfuseProjectId={langfuseProjectId} />
            ))
          : <EmptyState icon="insight" title="No insights yet" hint="Run a spec to generate an insight card" />
      )}
      {tab === 'Schema' && <SchemaTimeline entries={data || []} />}
      {tab === 'Context' && (
        <ContextPanel
          ctx={data}
          versions={versions}
          onVersionChange={onVersionChange}
          langfuseBaseUrl={langfuseBaseUrl}
          langfuseProjectId={langfuseProjectId}
        />
      )}
    </>
  )
}

function EmptyState({ icon, title, hint }) {
  return (
    <div className="empty-state">
      <svg className="empty-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        {icon === 'insight' && <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 0 1-2 2h0a2 2 0 0 1-2-2v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />}
      </svg>
      <span>{title}</span>
      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{hint}</span>
    </div>
  )
}
