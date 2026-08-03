import type { SegmentEvidence } from '../types'

/** Renders one recursion level's ranked segments. Every row shows the exact
 * source_step query that produced it -- "no bluffing, only real traces." */
export function DrilldownLevel({ title, segments }: { title: string; segments: SegmentEvidence[] }) {
  if (!segments.length) {
    return (
      <div style={{ marginBottom: '0.75rem' }}>
        <h4 style={{ margin: '0 0 0.25rem' }}>{title}</h4>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No segments ranked at this level.</p>
      </div>
    )
  }
  return (
    <div style={{ marginBottom: '0.75rem' }}>
      <h4 style={{ margin: '0 0 0.25rem' }}>{title}</h4>
      {segments.map((s, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: '1rem',
            padding: '0.35rem 0',
            borderBottom: '1px solid var(--gridline)',
            fontSize: '0.88rem',
          }}
        >
          <span>
            {s.dimension} = <strong>{s.value}</strong>
          </span>
          <span className="tabular" style={{ textAlign: 'right' }}>
            {s.metric_now.toLocaleString(undefined, { maximumFractionDigits: 4 })} vs baseline{' '}
            {s.metric_baseline.toLocaleString(undefined, { maximumFractionDigits: 4 })} (share {(s.share_of_deviation * 100).toFixed(1)}%)
            <br />
            <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{s.source_step}</span>
          </span>
        </div>
      ))}
    </div>
  )
}
