export default function TraceTimeline({ trace = [] }) {
  if (!trace.length) {
    return <p className="muted">No trace steps yet.</p>
  }

  const total = trace.reduce((sum, step) => sum + (step.durationMs || 0), 0)

  return (
    <div className="trace">
      <div className="trace-total muted mono">
        Total {total > 0 ? `${(total / 1000).toFixed(2)}s` : '…'}
      </div>
      <ol className="trace-list">
        {trace.map((step, index) => (
          <li key={`${step.step}-${index}`} className="trace-item fade-in" style={{ animationDelay: `${index * 60}ms` }}>
            <div className="trace-step mono">{step.step}</div>
            <div className="trace-detail">{step.detail}</div>
            <div className="trace-ms mono">
              {step.durationMs > 0 ? `${step.durationMs} ms` : '…'}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
