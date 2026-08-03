/* Sibling comparison: the seasonality disproof, drawn.
 *
 * WHAT IT PROVES — and why it is a different argument from the spread bars
 * Spread bars ask "did this happen everywhere else too?". This asks "did the OTHER
 * values of this same dimension move?" — and that distinction is what kills the
 * seasonality explanation without relying on the baseline at all.
 *
 * The physical argument: seasonality acts on PEOPLE. People carry every device model
 * and run every OS. So a genuinely seasonal dip has to move all of them together.
 * Android collapsing while iOS stays flat cannot be a calendar effect, whatever the
 * date says.
 *
 * That matters because it is INDEPENDENT of the baseline. The bands are already
 * same-weekday/same-hour matched, so seasonality is controlled for by construction —
 * but that control is only as good as the baseline itself. This check needs no
 * baseline to be persuasive, which makes it the stronger of the two arguments.
 *
 * When the test could not run, this says so rather than quietly omitting the section.
 * An absent disproof is not a disproof.
 */

interface Props {
  seasonality: Record<string, unknown> | null
  rootScopeType: string
  rootScopeValue: string
}

export default function SiblingBars({ seasonality, rootScopeType, rootScopeValue }: Props) {
  if (!seasonality) {
    return (
      <p className="muted-note">
        No seasonality evidence was recorded for this incident.
      </p>
    )
  }

  const tested = Boolean(seasonality.tested)
  const reason = String(seasonality.reason ?? '')

  if (!tested) {
    return (
      <div>
        <p className="chart-legend">
          <strong>Could not be tested independently.</strong>
        </p>
        <p className="muted-note">{reason}</p>
      </div>
    )
  }

  const breached = Number(seasonality.siblings_breached ?? 0)
  const evaluated = Number(seasonality.siblings_evaluated ?? 0)
  const isolated = Boolean(seasonality.isolated)
  const held = Math.max(0, evaluated - breached)
  const color = isolated ? 'var(--status-good)' : 'var(--status-warning)'

  return (
    <div>
      <p className="chart-legend">
        Seasonality moves <em>people</em>, and people carry every device and OS — so a
        seasonal effect has to move a whole population together. If{' '}
        <strong>{rootScopeValue || 'this segment'}</strong> moved while its siblings held, no
        calendar effect can explain it. This argument does not depend on the baseline being
        right, which is why it is worth making separately.
      </p>

      <div className="sibling-compare">
        <div className="sibling-col">
          <div className="sibling-count" style={{ color: 'var(--status-critical)' }}>
            {breached}
          </div>
          <div className="sibling-bar-wrap" aria-hidden="true">
            <div
              className="sibling-bar"
              style={{
                height: `${evaluated ? (breached / evaluated) * 100 : 0}%`,
                background: 'var(--status-critical)',
              }}
            />
          </div>
          <div className="sibling-label">moved</div>
        </div>
        <div className="sibling-col">
          <div className="sibling-count" style={{ color: 'var(--status-good)' }}>
            {held}
          </div>
          <div className="sibling-bar-wrap" aria-hidden="true">
            <div
              className="sibling-bar"
              style={{
                height: `${evaluated ? (held / evaluated) * 100 : 0}%`,
                background: 'var(--status-good)',
              }}
            />
          </div>
          <div className="sibling-label">held flat</div>
        </div>
        <div className="sibling-verdict">
          <div style={{ color, fontWeight: 700, fontSize: '0.95rem' }}>
            {isolated ? 'Seasonality ruled out' : 'Not isolated — treat with caution'}
          </div>
          <p className="muted-note" style={{ marginTop: '0.35rem' }}>
            {reason}
          </p>
          <p className="source-note">
            {breached} of {evaluated} values of <code>{rootScopeType}</code> breached in the same
            window
          </p>
        </div>
      </div>
    </div>
  )
}
