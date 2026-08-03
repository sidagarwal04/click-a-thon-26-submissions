import Tooltip from '../common/Tooltip'
import { fmtDateTime } from '../../utils'
import { TIMELINE_SUMMARY_TIP } from './tips'

/** Action → friendly label + accent class for the timeline. */
const ACTION_META = {
  create_table: { label: 'Table created', cls: 'create' },
  add_column:   { label: 'Column added', cls: 'add' },
  create_mv:    { label: 'Materialized view created', cls: 'mv' },
}

export default function SchemaTimeline({ entries = [] }) {
  if (!entries.length) {
    return (
      <div className="empty-state">
        <svg className="empty-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span>No schema changes yet</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Run a spec to see the timeline</span>
      </div>
    )
  }

  const created = entries.filter(e => e.action === 'create_table').length
  const columns = entries.filter(e => e.action === 'add_column').length

  return (
    <div>
      {/* Summary strip */}
      <div className="timeline-summary">
        <Tooltip content={TIMELINE_SUMMARY_TIP.changes}>
          <span className="timeline-summary-item">
            <strong>{entries.length}</strong> change{entries.length !== 1 ? 's' : ''}
          </span>
        </Tooltip>
        <span className="timeline-summary-sep" />
        <Tooltip content={TIMELINE_SUMMARY_TIP.tables}>
          <span className="timeline-summary-item">
            <strong>{created}</strong> table{created !== 1 ? 's' : ''}
          </span>
        </Tooltip>
        <span className="timeline-summary-sep" />
        <Tooltip content={TIMELINE_SUMMARY_TIP.columns}>
          <span className="timeline-summary-item">
            <strong>{columns}</strong> column{columns !== 1 ? 's' : ''}
          </span>
        </Tooltip>
      </div>

      <div className="timeline">
        {entries.map((e, i) => {
          const meta = ACTION_META[e.action] || { label: (e.action || 'change').replace(/_/g, ' '), cls: 'other' }
          return (
            <div className="timeline-item" key={i}>
              <Tooltip content={`Action: ${e.action} — ${meta.label}.`} position="right">
              <div className={`timeline-dot action-${meta.cls}`}>
                {e.action === 'create_table' && (
                  <svg className="timeline-dot-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <line x1="3" y1="9" x2="21" y2="9" />
                    <line x1="3" y1="15" x2="21" y2="15" />
                    <line x1="12" y1="9" x2="12" y2="21" />
                  </svg>
                )}
                {e.action === 'add_column' && (
                  <svg className="timeline-dot-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                )}
                {e.action !== 'create_table' && e.action !== 'add_column' && (
                  <svg className="timeline-dot-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4z" />
                  </svg>
                )}
              </div>
              </Tooltip>
              <div className="timeline-body">
                <div className="timeline-head">
                  <span className={`timeline-action action-${meta.cls}`}>{meta.label}</span>
                  {e.version != null && (
                    <Tooltip content="Schema changelog version — increments each time the schema changes.">
                      <span className="timeline-version">v{e.version}</span>
                    </Tooltip>
                  )}
                  {e.trace_id && (
                    <Tooltip content={`Full trace id: ${e.trace_id}`}>
                      <span className="timeline-trace">trace {e.trace_id.slice(0, 8)}</span>
                    </Tooltip>
                  )}
                  <span className="timeline-time">{fmtDateTime(e.created_at)}</span>
                </div>
                <div className="timeline-object">{e.object}</div>
                {e.rationale && (
                  <div className="timeline-rationale">{e.rationale}</div>
                )}
                {e.diff && (
                  <Tooltip content="The exact DDL / schema change applied." position="bottom" focusable={false}>
                    <details className="timeline-diff">
                      <summary>View diff</summary>
                      <pre className="diff-block">{e.diff}</pre>
                    </details>
                  </Tooltip>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
