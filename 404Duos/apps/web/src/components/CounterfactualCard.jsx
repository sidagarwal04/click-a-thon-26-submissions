export default function CounterfactualCard({ counterfactual }) {
  if (!counterfactual?.detail) return null
  return (
    <section className="counterfactual-card fade-in">
      <div className="counterfactual-title">What if (counterfactual)</div>
      <p className="counterfactual-text">{counterfactual.detail}</p>
      <div className="counterfactual-stats mono">
        <div>
          <span className="muted">Observed</span>
          <strong>${Number(counterfactual.observedRevenue || 0).toFixed(2)}</strong>
        </div>
        <div>
          <span className="muted">If culprit held</span>
          <strong>${Number(counterfactual.counterfactualRevenue || 0).toFixed(2)}</strong>
        </div>
        <div>
          <span className="muted">Gap recovered</span>
          <strong className="pos">{Number(counterfactual.recoveredPctOfGap || 0).toFixed(0)}%</strong>
        </div>
      </div>
    </section>
  )
}
