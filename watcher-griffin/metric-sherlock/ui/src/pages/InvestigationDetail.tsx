import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getInvestigation } from '../api/client'
import { Chat } from '../components/Chat'
import { DrilldownLevel } from '../components/DrilldownLevel'
import { RuledOutList } from '../components/RuledOutList'
import type { InvestigationDetailResponse } from '../types'

function statusColor(isAnomalous: boolean, zscore: number): string {
  if (isAnomalous) return 'var(--status-critical)'
  if (Math.abs(zscore) > 1.5) return 'var(--status-warning)'
  return 'var(--status-good)'
}

export function InvestigationDetail() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<InvestigationDetailResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    getInvestigation(id)
      .then(setData)
      .catch((e) => setError(e.message))
  }, [id])

  if (error) return <p style={{ color: 'var(--status-critical)' }}>{error}</p>
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>Loading…</p>

  const ev = data.evidence
  const pct = ev.pct_change !== null ? `${ev.pct_change >= 0 ? '+' : ''}${(ev.pct_change * 100).toFixed(1)}%` : 'n/a (no baseline history)'

  return (
    <div>
      <p>
        <Link to="/">&larr; Back to dashboard</Link>
      </p>

      <div
        style={{
          display: 'inline-block',
          padding: '0.6rem 1rem',
          borderRadius: 8,
          background: statusColor(ev.is_anomalous, ev.zscore),
          color: '#fff',
          fontWeight: 600,
          marginBottom: '0.75rem',
        }}
      >
        {ev.metric}: {ev.current_value.toLocaleString(undefined, { maximumFractionDigits: 4 })} (baseline{' '}
        {ev.baseline_mean.toLocaleString(undefined, { maximumFractionDigits: 4 })}, {pct}, z={ev.zscore.toFixed(2)})
        {data.triggered_by === 'scanner' && <span style={{ marginLeft: '0.6rem', fontWeight: 400, fontSize: '0.8rem' }}>auto-triggered by monitor</span>}
      </div>
      {ev.insufficient_baseline && (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Fewer than 2 trailing-week baseline samples were available -- not enough history to judge this window, so it's never flagged anomalous.
        </p>
      )}

      <div className="card">
        {data.narration_available ? <p style={{ fontSize: '1.02rem' }}>{data.narration}</p> : (
          <p style={{ fontStyle: 'italic', color: 'var(--text-muted)' }}>
            Narration unavailable ({data.narration_provider}): {data.narration_error}
          </p>
        )}
        {data.langfuse_trace_url && (
          <p>
            <a href={data.langfuse_trace_url} target="_blank" rel="noreferrer">
              Open Langfuse trace
            </a>
          </p>
        )}
      </div>

      {ev.factor_breakdown.length > 0 && (
        <div className="card">
          <h3 style={{ margin: '0 0 0.4rem' }}>Revenue decomposition</h3>
          {ev.factor_breakdown.map((f) => (
            <div key={f.factor} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.88rem', padding: '0.3rem 0', borderBottom: '1px solid var(--gridline)' }}>
              <span>
                {f.factor}
                {f.factor === ev.primary_factor && ' (primary)'}
              </span>
              <span className="tabular">
                {f.now.toFixed(4)} vs {f.baseline.toFixed(4)} (share {(f.share * 100).toFixed(1)}%)
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h3 style={{ margin: '0 0 0.4rem' }}>Drill-down ({ev.drilldown_levels.length} level{ev.drilldown_levels.length === 1 ? '' : 's'})</h3>
        {ev.drilldown_levels.map((level, i) => (
          <DrilldownLevel key={i} title={i === 0 ? 'Top contributing segments' : `Drill-down level ${i}`} segments={level} />
        ))}
      </div>

      <div className="card">
        <RuledOutList items={ev.ruled_out} />
      </div>

      <div className="card">
        <Chat subject="investigation" subjectId={data.id} initialTurns={data.chat} />
      </div>

      <details className="card">
        <summary style={{ cursor: 'pointer' }}>Raw evidence trace ({ev.queries.length} queries)</summary>
        <div style={{ maxHeight: 320, overflowY: 'auto', marginTop: '0.5rem' }}>
          {ev.queries.map((q, i) => (
            <div key={i} style={{ fontSize: '0.78rem', padding: '0.3rem 0', borderBottom: '1px solid var(--gridline)' }}>
              <div style={{ color: 'var(--text-muted)' }}>
                {q.step} — {q.row_count} row(s), {q.latency_ms.toFixed(1)}ms{q.error ? ` — ERROR: ${q.error}` : ''}
              </div>
              <code style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{q.sql}</code>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}
