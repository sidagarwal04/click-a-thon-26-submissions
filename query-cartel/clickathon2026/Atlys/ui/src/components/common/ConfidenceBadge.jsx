import Tooltip from './Tooltip'

const CONFIDENCE_TIP = {
  high: 'High confidence — 1,000+ users reached the final funnel step.',
  medium: 'Medium confidence — 200–999 users reached the final funnel step.',
  low: 'Low confidence — under 200 users, or no funnel data to score.',
}

export default function ConfidenceBadge({ value }) {
  const level = (value || 'low').toLowerCase()
  const labels = { high: '● High', medium: '◐ Medium', low: '○ Low' }
  return (
    <Tooltip content={CONFIDENCE_TIP[level] ?? 'Confidence in this insight'} position="bottom">
      <span className={`confidence-badge ${level}`}>
        {labels[level] ?? level}
      </span>
    </Tooltip>
  )
}
