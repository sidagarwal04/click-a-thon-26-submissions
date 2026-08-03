import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listAlerts } from '../api/client.js'
import StatusPill from '../components/StatusPill.jsx'
import {
  ALERT_CATEGORIES,
  categoryLabel,
  formatBaselineKind,
  formatMetric,
  formatWindow,
  polishSummary,
} from '../utils/format.js'

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('all')
  const [granularity, setGranularity] = useState('day')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const data = await listAlerts({ granularity })
        if (!cancelled) setAlerts(Array.isArray(data) ? data : [])
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load alerts')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [granularity])

  const counts = useMemo(() => {
    const next = { all: alerts.length }
    for (const cat of ALERT_CATEGORIES) {
      if (cat.id === 'all') continue
      next[cat.id] = alerts.filter((a) => (a.categories || []).includes(cat.id)).length
    }
    return next
  }, [alerts])

  const filtered = useMemo(() => {
    if (category === 'all') return alerts
    return alerts.filter((a) => (a.categories || []).includes(category))
  }, [alerts, category])

  return (
    <div>
      <h1 className="page-title">Alerts</h1>
      <p className="page-subtitle">
        Metric moves worth investigating, grouped by where they showed up (geo, OS, campaign,
        format, publisher). Open one for the diagnosis and the numbers behind it.
      </p>

      <div className="alerts-toolbar">
        <div className="granularity-toggle" role="group" aria-label="Alert granularity">
          <button
            type="button"
            className={`granularity-btn ${granularity === 'day' ? 'is-active' : ''}`}
            aria-pressed={granularity === 'day'}
            onClick={() => setGranularity('day')}
          >
            Daily
          </button>
          <button
            type="button"
            className={`granularity-btn ${granularity === 'hour' ? 'is-active' : ''}`}
            aria-pressed={granularity === 'hour'}
            onClick={() => setGranularity('hour')}
          >
            Hourly
          </button>
        </div>
        <p className="granularity-hint muted">
          {granularity === 'day'
            ? 'One card per advertiser per day — peak hourly anomaly that day.'
            : 'Native hourly buckets from alerts_live.'}
        </p>
      </div>

      <div className="category-tabs" role="tablist" aria-label="Alert categories">
        {ALERT_CATEGORIES.map((cat) => {
          const active = category === cat.id
          const count = counts[cat.id] ?? 0
          return (
            <button
              key={cat.id}
              type="button"
              role="tab"
              aria-selected={active}
              className={`category-tab ${active ? 'is-active' : ''}`}
              onClick={() => setCategory(cat.id)}
              title={cat.hint || cat.label}
            >
              <span>{cat.label}</span>
              <span className="category-count mono">{count}</span>
            </button>
          )
        })}
      </div>

      {category !== 'all' ? (
        <p className="category-filter-hint muted">
          Showing alerts where <strong>{categoryLabel(category)}</strong> is a contributing
          dimension.
        </p>
      ) : null}

      {loading ? <div className="loading">Loading alerts…</div> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {!loading && !error ? (
        <div className="alert-list panel">
          {filtered.length === 0 ? (
            <div className="alert-empty muted">No alerts in this category yet.</div>
          ) : (
            filtered.map((alert) => (
              <Link
                key={`${alert.id}-${alert.granularity || granularity}`}
                to={`/investigations/${alert.investigationId}?view=${granularity}`}
                className="alert-row"
              >
                <div className="alert-main">
                  <div className="alert-title-row">
                    <span className="alert-metric">{formatMetric(alert.metric)}</span>
                    <StatusPill status={alert.severity}>{alert.severity}</StatusPill>
                    <StatusPill status={alert.status}>{alert.status}</StatusPill>
                    <span className="alert-cat-chip">{granularity === 'day' ? 'Daily' : 'Hourly'}</span>
                    {(alert.categories || []).slice(0, 3).map((c) => (
                      <span key={c} className={`alert-cat-chip cat-${c}`}>
                        {categoryLabel(c)}
                      </span>
                    ))}
                  </div>
                  <p className="alert-summary">{polishSummary(alert.summary)}</p>
                  {alert.categoryLabels?.length ? (
                    <div className="alert-segment-tags">
                      {alert.categoryLabels
                        .filter((s) => category === 'all' || s.category === category)
                        .slice(0, 3)
                        .map((s) => (
                          <span key={`${s.dimension}-${s.value}`} className="segment-tag mono">
                            {categoryLabel(s.category)} · {s.value}{' '}
                            <span className={Number(s.deltaPct) < 0 ? 'neg' : 'pos'}>
                              {Number(s.deltaPct) > 0 ? '+' : ''}
                              {Number(s.deltaPct).toFixed(1)}%
                            </span>
                          </span>
                        ))}
                    </div>
                  ) : null}
                  <div className="alert-meta mono muted">
                    {alert.advertiserId ? (
                      <>
                        <span>{alert.advertiserId}</span>
                        <span>·</span>
                      </>
                    ) : null}
                    <span>
                      {formatWindow(alert.windowStart, alert.windowEnd, {
                        withTime: granularity === 'hour',
                      })}
                    </span>
                    <span>·</span>
                    <span title={formatBaselineKind(alert.baselineKind).hint}>
                      {formatBaselineKind(alert.baselineKind).label}
                    </span>
                  </div>
                </div>
                <div className={`alert-delta ${alert.direction === 'down' ? 'neg' : 'pos'}`}>
                  {alert.direction === 'down' ? '↓' : '↑'}{' '}
                  {Math.abs(alert.pctChange).toFixed(1)}%
                </div>
              </Link>
            ))
          )}
        </div>
      ) : null}
    </div>
  )
}
