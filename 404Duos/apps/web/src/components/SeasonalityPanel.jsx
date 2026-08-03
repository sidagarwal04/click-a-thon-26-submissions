export default function SeasonalityPanel({ seasonality }) {
  if (!seasonality) return null
  const status = seasonality.status || 'skipped'
  const title =
    status === 'ruled_out_as_seasonality'
      ? 'Seasonality trap — not an incident'
      : status === 'residual_remains'
        ? 'Seasonality checked — residual remains'
        : 'Seasonality check'

  return (
    <section className={`seasonality-panel status-${status}`}>
      <div className="seasonality-title">{title}</div>
      <p className="muted" style={{ margin: '0.35rem 0 0.65rem' }}>
        {seasonality.detail}
      </p>
      <div className="seasonality-stats mono">
        <span>
          Naive trailing 7d:{' '}
          <span className={seasonality.flatDeltaPct < 0 ? 'neg' : 'pos'}>
            {Number(seasonality.flatDeltaPct) > 0 ? '+' : ''}
            {Number(seasonality.flatDeltaPct).toFixed(1)}%
          </span>
        </span>
        <span>
          vs same weekday/hour × 4w:{' '}
          <span className={seasonality.seasonalDeltaPct < 0 ? 'neg' : 'pos'}>
            {Number(seasonality.seasonalDeltaPct) > 0 ? '+' : ''}
            {Number(seasonality.seasonalDeltaPct).toFixed(1)}%
          </span>
        </span>
      </div>
    </section>
  )
}
