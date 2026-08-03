import { useEffect, useMemo, useState } from 'react'
import { getDashboardMeta, queryDashboard } from '../api/client.js'
import DashboardChart from '../dashboard/DashboardChart.jsx'
import DimensionTable from '../dashboard/DimensionTable.jsx'
import FiltersModal from '../dashboard/FiltersModal.jsx'
import SelectionModal from '../dashboard/SelectionModal.jsx'
import {
  DATE_PRESETS,
  DEFAULT_DIMENSIONS,
  DEFAULT_METRICS,
  FALLBACK_META,
  compareRangeFor,
  dimensionLabel,
  formatMetricValue,
  metricLabel,
  rangeFromPreset,
} from '../dashboard/config.js'

const DISPLAY_MODES = [
  { id: 'both', label: 'Graph + Table' },
  { id: 'graph', label: 'Graph only' },
  { id: 'table', label: 'Table only' },
]

export default function DashboardPage() {
  const [meta, setMeta] = useState(FALLBACK_META)
  const [preset, setPreset] = useState('day')
  const [range, setRange] = useState(() => rangeFromPreset('day'))
  const [granularity, setGranularity] = useState('hour')
  const [metrics, setMetrics] = useState(DEFAULT_METRICS)
  const [dimensions, setDimensions] = useState(DEFAULT_DIMENSIONS)
  const [filters, setFilters] = useState({})
  const [compare, setCompare] = useState(false)
  const [displayMode, setDisplayMode] = useState('both')
  const [rowCount, setRowCount] = useState(10)

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [metricsOpen, setMetricsOpen] = useState(false)
  const [dimsOpen, setDimsOpen] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)

  useEffect(() => {
    getDashboardMeta()
      .then(setMeta)
      .catch(() => setMeta(FALLBACK_META))
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const body = {
          start: range.start,
          end: range.end,
          granularity,
          metrics,
          dimensions,
          filters,
          limit: rowCount,
        }
        if (compare) {
          body.compare = compareRangeFor(range.start, range.end)
        }
        const out = await queryDashboard(body)
        if (!cancelled) setData(out)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Dashboard failed')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [range, granularity, metrics, dimensions, filters, compare, rowCount])

  const activeFilterChips = useMemo(() => {
    const chips = []
    for (const [dim, vals] of Object.entries(filters || {})) {
      for (const v of vals || []) {
        chips.push({ dim, value: v, key: `${dim}:${v}` })
      }
    }
    return chips
  }, [filters])

  function onPresetChange(id) {
    setPreset(id)
    if (id !== 'custom') setRange(rangeFromPreset(id))
  }

  function removeFilter(dim, value) {
    setFilters((prev) => {
      const next = { ...prev }
      next[dim] = (next[dim] || []).filter((v) => v !== value)
      if (!next[dim].length) delete next[dim]
      return next
    })
  }

  function addFilterValue(dim, value) {
    setFilters((prev) => {
      const cur = prev[dim] || []
      if (cur.includes(value)) return prev
      return { ...prev, [dim]: [...cur, value] }
    })
  }

  const showGraph = displayMode !== 'table'
  const showTable = displayMode !== 'graph'

  return (
    <div className="dashboard-page fade-in">
      <div className="dash-title-row">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            Explore metrics with date range, compare, filters, and dimension breakdowns.
          </p>
        </div>
      </div>

      <section className="panel dash-controls">
        <div className="dash-controls-row">
          <div className="dash-date-block">
            <span className="dash-label">Date</span>
            <div className="dash-date-controls">
              <div className="dash-select-wrap dash-select-wide">
                <select
                  className="dash-select"
                  value={preset}
                  onChange={(e) => onPresetChange(e.target.value)}
                  aria-label="Date preset"
                >
                  {DATE_PRESETS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
              <input
                type="date"
                className="dash-input dash-date-input"
                value={range.start.slice(0, 10)}
                onChange={(e) => {
                  setPreset('custom')
                  setRange((r) => ({ ...r, start: `${e.target.value}T00:00:00Z` }))
                }}
                aria-label="Start date"
              />
              <span className="dash-date-arrow" aria-hidden="true">
                →
              </span>
              <input
                type="date"
                className="dash-input dash-date-input"
                value={range.end.slice(0, 10)}
                onChange={(e) => {
                  setPreset('custom')
                  setRange((r) => ({ ...r, end: `${e.target.value}T23:59:59Z` }))
                }}
                aria-label="End date"
              />
            </div>
          </div>

          <label className="dash-check">
            <input
              type="checkbox"
              checked={compare}
              onChange={(e) => setCompare(e.target.checked)}
            />
            Compare prior period
          </label>

          <label className="dash-field">
            <span className="dash-label">Grain</span>
            <div className="dash-select-wrap">
              <select
                className="dash-select"
                value={granularity}
                onChange={(e) => setGranularity(e.target.value)}
              >
                <option value="hour">Hour</option>
                <option value="day">Day</option>
              </select>
            </div>
          </label>

          <div className="dash-controls-spacer" />

          <div className="dash-action-btns">
            <button type="button" className="btn" onClick={() => setFiltersOpen(true)}>
              Filters
            </button>
            <button type="button" className="btn" onClick={() => setDimsOpen(true)}>
              Dimensions
            </button>
            <button type="button" className="btn btn-primary" onClick={() => setMetricsOpen(true)}>
              Metrics
            </button>
          </div>
        </div>

        <div className="dash-controls-row dash-controls-secondary">
          <div className="dash-chip-row">
            {activeFilterChips.length === 0 ? (
              <span className="muted">No filters applied</span>
            ) : (
              activeFilterChips.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  className="filter-chip"
                  onClick={() => removeFilter(c.dim, c.value)}
                >
                  {dimensionLabel(meta, c.dim)}: {c.value} ×
                </button>
              ))
            )}
          </div>

          <label className="dash-field">
            <span className="dash-label">Rows</span>
            <div className="dash-select-wrap dash-select-sm">
              <select
                className="dash-select"
                value={rowCount}
                onChange={(e) => setRowCount(Number(e.target.value))}
              >
                {[10, 25, 50].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          </label>

          <label className="dash-field">
            <span className="dash-label">Layout</span>
            <div className="dash-select-wrap dash-select-md">
              <select
                className="dash-select"
                value={displayMode}
                onChange={(e) => setDisplayMode(e.target.value)}
              >
                {DISPLAY_MODES.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
          </label>
        </div>
      </section>

      {data?.totals ? (
        <div className="dash-kpi-row">
          {metrics.map((m) => {
            const total = data.totals[m]
            const delta = data.deltas?.[m]
            return (
              <div key={m} className="dash-kpi panel">
                <div className="dash-kpi-label">{metricLabel(meta, m)}</div>
                <div className="dash-kpi-value mono">{formatMetricValue(m, total)}</div>
                {compare && delta ? (
                  <div className={`dash-kpi-delta mono ${delta.deltaPct < 0 ? 'neg' : 'pos'}`}>
                    {delta.deltaPct > 0 ? '+' : ''}
                    {delta.deltaPct.toFixed(1)}% vs prior
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      ) : null}

      {loading ? <div className="loading">Loading dashboard…</div> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {!loading && !error && data ? (
        <div className="dash-main stack">
          {showGraph ? (
            <div className="dash-charts-grid">
              {metrics.map((m, i) => (
                <DashboardChart
                  key={m}
                  meta={meta}
                  metricId={m}
                  colorIndex={i}
                  timeseries={data.timeseries}
                  compareTimeseries={data.compareTimeseries}
                  compareEnabled={compare}
                />
              ))}
            </div>
          ) : null}

          {showTable ? (
            <div className="dash-tables">
              {dimensions.map((dim) => (
                <DimensionTable
                  key={dim}
                  meta={meta}
                  dimension={dim}
                  rows={data.tables?.[dim] || []}
                  metrics={metrics}
                  compareEnabled={compare}
                  onFilterValue={addFilterValue}
                />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {metricsOpen ? (
        <SelectionModal
          title="Select metrics"
          items={meta.metrics}
          selected={metrics}
          onChange={setMetrics}
          onClose={() => setMetricsOpen(false)}
        />
      ) : null}
      {dimsOpen ? (
        <SelectionModal
          title="Select dimensions"
          items={meta.dimensions}
          selected={dimensions}
          onChange={setDimensions}
          onClose={() => setDimsOpen(false)}
        />
      ) : null}
      {filtersOpen ? (
        <FiltersModal
          meta={meta}
          filters={filters}
          onChange={setFilters}
          onClose={() => setFiltersOpen(false)}
          start={range.start}
          end={range.end}
        />
      ) : null}
    </div>
  )
}
