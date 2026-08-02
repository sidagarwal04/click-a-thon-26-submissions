import type { RuledOutEvidence } from '../types'

export function RuledOutList({ items }: { items: RuledOutEvidence[] }) {
  if (!items.length) return null
  return (
    <div>
      <h3 style={{ margin: '0 0 0.4rem' }}>Checked and ruled out</h3>
      {items.map((r, i) => (
        <div key={i} style={{ fontSize: '0.85rem', padding: '0.3rem 0', color: 'var(--text-secondary)' }}>
          <span style={{ color: 'var(--status-good)' }}>&#10003;</span> <strong style={{ color: 'var(--text-primary)' }}>{r.check}</strong> — {r.reason}
        </div>
      ))}
    </div>
  )
}
