import ConfidenceBadge from '../common/ConfidenceBadge'
import Tooltip from '../common/Tooltip'
import { fmtDateTime } from '../../utils'
import { KIND_TIP } from './tips'

/** Evidence-row display: kind → label color mapping for readability. */
const KIND_LABEL = {
  funnel: 'funnel',
  funnel_timing: 'funnel timing',
  overview: 'overview',
  segment: 'segment',
  timing: 'timing',
  cross_funnel: 'cross-funnel',
  mv_funnel: 'mv funnel',
}

export default function InsightCard({ insight, langfuseBaseUrl, langfuseProjectId }) {
  const evidence = (() => {
    try {
      return typeof insight.evidence === 'string'
        ? JSON.parse(insight.evidence)
        : insight.evidence || []
    } catch { return [] }
  })()

  // Build direct Langfuse trace URL.
  const traceUrl = insight.trace_id
    ? langfuseProjectId
      ? `${langfuseBaseUrl.replace(/\/$/, '')}/project/${langfuseProjectId}/traces/${insight.trace_id}`
      : `${langfuseBaseUrl.replace(/\/$/, '')}/traces?search=${insight.trace_id}`
    : null

  return (
    <div className="insight-card">
      <div className="insight-header">
        <span className="insight-title">{insight.title || insight.spec}</span>
        <ConfidenceBadge value={insight.confidence} />
      </div>

      {insight.spec && (
        <div className="insight-tags">
          <Tooltip content={`Feature spec this insight was derived from: ${insight.spec}`}>
            <span className="insight-spec-tag">spec: {insight.spec}</span>
          </Tooltip>
        </div>
      )}

      {insight.summary && (
        <p className="insight-summary">{insight.summary}</p>
      )}

      {/* Evidence */}
      {evidence.length > 0 && (
        <div className="insight-evidence">
          <div className="insight-evidence-head">
            <span>Evidence</span>
            <Tooltip content="Queries the analytics agent ran (P1–P6 playbook) — the numbers behind the summary.">
              <span className="insight-evidence-count">{evidence.length} quer{evidence.length !== 1 ? 'ies' : 'y'}</span>
            </Tooltip>
          </div>
          <div className="insight-evidence-list">
            {evidence.slice(0, 6).map((ev, i) => {
              const kind = KIND_LABEL[ev.kind] || ev.kind || 'query'
              const hasRows = Array.isArray(ev.rows) && ev.rows.length > 0
              return (
                <div key={i} className="insight-evidence-row">
                  <Tooltip content={KIND_TIP[ev.kind] || 'A query the analytics agent ran to back this insight.'} position="right">
                    <span className={`insight-evidence-kind kind-${ev.kind || 'other'}`}>{kind}</span>
                  </Tooltip>
                  <span className="insight-evidence-label">{ev.label}</span>
                  {hasRows && (
                    <Tooltip content="Rows returned by this query.">
                      <span className="insight-evidence-rows">{ev.rows.length} rows</span>
                    </Tooltip>
                  )}
                  {ev.error && (
                    <Tooltip content={ev.error} position="bottom">
                      <span className="insight-evidence-error">failed</span>
                    </Tooltip>
                  )}
                </div>
              )
            })}
            {evidence.length > 6 && (
              <div className="insight-evidence-more">+{evidence.length - 6} more…</div>
            )}
          </div>
        </div>
      )}

      <div className="insight-meta">
        {insight.trace_id && traceUrl && (
          <a
            href={traceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="trace-link"
            title="Open trace in Langfuse"
          >
            Trace: {insight.trace_id.slice(0, 8)}…
          </a>
        )}
        {insight.created_at && (
          <Tooltip content="When this insight was generated.">
            <span className="insight-time">
              {fmtDateTime(insight.created_at)}
            </span>
          </Tooltip>
        )}
      </div>
    </div>
  )
}
