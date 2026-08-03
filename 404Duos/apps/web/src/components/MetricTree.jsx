import StatusPill from './StatusPill.jsx'
import { formatFactorValue, formatSignedPct } from '../utils/format.js'

const STATUS_LABEL = {
  culprit: 'Culprit',
  ruled_out: 'Ruled out',
  neutral: 'Neutral',
}

const STATUS_HINT = {
  culprit: 'Largest driver of the revenue move',
  ruled_out: 'Too small / wrong factor — cleared',
  neutral: 'Moved, but not the primary driver',
}

export default function MetricTree({ decomposition = [], waterfall = [], animate = true }) {
  const hasWaterfall = waterfall.length > 0
  const totalImpact = waterfall.reduce((s, w) => s + Math.abs(Number(w.revenueImpact) || 0), 0)

  return (
    <div className={`metric-tree ${animate ? 'fade-in' : ''}`}>
      <p className="metric-tree-formula muted mono">
        Revenue ≈ Requests × Fill rate × Render rate × eCPM / 1000
      </p>
      <div className="metric-tree-rail" aria-hidden />
      <ul className="metric-tree-list">
        {decomposition.map((node, index) => (
          <li
            key={node.factor}
            className={`metric-node status-${node.status}`}
            style={{ animationDelay: `${index * 70}ms` }}
            title={STATUS_HINT[node.status] || ''}
          >
            <div className="metric-node-top">
              <span className="metric-label">{node.label}</span>
              <StatusPill status={node.status}>{STATUS_LABEL[node.status]}</StatusPill>
            </div>
            <div className="metric-node-stats mono">
              <span>
                {formatFactorValue(node.factor, node.baseline)} →{' '}
                {formatFactorValue(node.factor, node.observed)}
              </span>
              <span className={node.deltaPct < 0 ? 'neg' : 'pos'}>
                {formatSignedPct(node.deltaPct)}
              </span>
            </div>
            {hasWaterfall ? (
              <WaterfallBar
                step={waterfall.find((w) => w.factor === node.factor)}
                totalImpact={totalImpact}
              />
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

function WaterfallBar({ step, totalImpact }) {
  if (!step || !totalImpact) return null
  const impact = Number(step.revenueImpact) || 0
  const width = Math.max(4, (Math.abs(impact) / totalImpact) * 100)
  return (
    <div className="waterfall-row">
      <div className="waterfall-track" aria-hidden>
        <div
          className={`waterfall-fill ${impact < 0 ? 'is-neg' : 'is-pos'}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className={`waterfall-label mono ${impact < 0 ? 'neg' : 'pos'}`}>
        {`${impact < 0 ? '−' : '+'}$${Math.abs(impact).toFixed(2)} · ${Number(step.sharePct || 0).toFixed(0)}% of $ move`}
      </span>
    </div>
  )
}
