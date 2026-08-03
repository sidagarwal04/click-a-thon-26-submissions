export default function HypothesesPanel({ hypotheses = [] }) {
  if (!hypotheses.length) return null
  return (
    <section className="hypotheses-panel fade-in">
      <div className="hypotheses-title">Hypotheses</div>
      <ol className="hypotheses-list">
        {hypotheses.map((h) => (
          <li key={`${h.rank}-${h.factor}`} className={h.rank === 1 ? 'is-primary' : ''}>
            <div className="hypotheses-head">
              <strong>
                #{h.rank} {h.label}
              </strong>
              <span className="mono muted">{Number(h.confidencePct || 0).toFixed(0)}% confidence</span>
            </div>
            <p className="muted">{h.why}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
