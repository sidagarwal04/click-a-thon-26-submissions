import { dimensionLabel, formatMetricValue, metricLabel } from './config.js'

export default function DimensionTable({
  meta,
  dimension,
  rows = [],
  metrics = [],
  compareEnabled,
  onFilterValue,
}) {
  const primary = metrics[0]

  return (
    <section className="panel dash-table">
      <div className="panel-header">
        <h2 className="panel-title">{dimensionLabel(meta, dimension)}</h2>
        <span className="muted" style={{ fontSize: '0.78rem' }}>
          Top {rows.length} by {metricLabel(meta, primary)}
        </span>
      </div>
      <div className="panel-body" style={{ padding: 0 }}>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Value</th>
                {metrics.map((m) => (
                  <th key={m} className="num">
                    {metricLabel(meta, m)}
                  </th>
                ))}
                {compareEnabled
                  ? metrics.map((m) => (
                      <th key={`${m}-d`} className="num">
                        {metricLabel(meta, m)} Δ%
                      </th>
                    ))
                  : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.value}>
                  <td>
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => onFilterValue?.(dimension, row.value)}
                      title={`Filter to ${row.value}`}
                    >
                      {row.value}
                    </button>
                  </td>
                  {metrics.map((m) => (
                    <td key={m} className="num mono">
                      {formatMetricValue(m, row[m])}
                    </td>
                  ))}
                  {compareEnabled
                    ? metrics.map((m) => {
                        const pct = Number(row[`${m}_delta_pct`]) || 0
                        return (
                          <td
                            key={`${m}-d`}
                            className={`num mono ${pct < 0 ? 'neg' : pct > 0 ? 'pos' : ''}`}
                          >
                            {pct > 0 ? '+' : ''}
                            {pct.toFixed(1)}%
                          </td>
                        )
                      })
                    : null}
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={metrics.length + 1} className="muted" style={{ padding: '1rem' }}>
                    No rows for this dimension.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
