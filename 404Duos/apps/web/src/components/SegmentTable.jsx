import { formatMetric, formatSignedPct } from '../utils/format.js'

export default function SegmentTable({ segments = [] }) {
  if (!segments.length) {
    return <p className="muted">No dominant segments after baseline adjustment.</p>
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Dimension</th>
            <th>Segment</th>
            <th>Metric</th>
            <th>Change</th>
            <th>Contribution</th>
          </tr>
        </thead>
        <tbody>
          {segments.map((row) => (
            <tr key={`${row.dimension}-${row.value}`}>
              <td>{formatMetric(row.dimension)}</td>
              <td>{row.value}</td>
              <td>{formatMetric(row.metric)}</td>
              <td className={row.deltaPct < 0 ? 'neg mono' : 'pos mono'}>
                {formatSignedPct(row.deltaPct)}
              </td>
              <td>
                <div className="contrib">
                  <div
                    className="contrib-bar"
                    style={{ width: `${Math.min(100, Math.abs(row.contributionPct))}%` }}
                  />
                  <span className="mono">{row.contributionPct.toFixed(1)}%</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
