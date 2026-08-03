/* Impact bars: which entities the dollar exposure actually sits in.
 *
 * WHAT IT PROVES
 * That the headline dollar figure is not a single opaque number. It decomposes:
 * "adv_0007 explains $38 of the $50". An operator can then act on the biggest
 * contributor rather than on the aggregate.
 *
 * WHY THESE SHARES ARE TRUSTWORTHY
 * They are computed from absolute expected-minus-actual dollars per entity, NOT from
 * the engine's `share_of_total_delta`. That share is normalised by the *net signed*
 * delta, so when entities move in opposite directions the denominator collapses and
 * individual shares can exceed 100%. These are normalised by the sum of absolute
 * impacts and are therefore bounded in [0, 1] and additive — which is what an
 * attribution has to be to be worth showing as a bar.
 */

import { useState } from 'react'

import { usd } from '../lib/format'
import { scopeValue } from '../lib/format'
import type { ImpactPart } from '../types'

interface Props {
  breakdown: {
    total_impact_usd: number
    parts: ImpactPart[]
    dimension?: string
    basis_note?: string
  } | null
  limit?: number
}

/** Five, not ten. This sits above the fold now, and the point of the panel is "act on the
 *  biggest contributor" — a reader who needs the sixth can open the rest in one click, and
 *  the truncation is stated rather than silent. */
export default function ImpactBars({ breakdown, limit = 5 }: Props) {
  const [showAll, setShowAll] = useState(false)

  if (!breakdown || !breakdown.parts || breakdown.parts.length === 0) {
    return (
      <p className="muted-note">
        No per-entity decomposition is available for this incident.
      </p>
    )
  }

  const parts = showAll ? breakdown.parts : breakdown.parts.slice(0, limit)
  const rest = breakdown.parts.length - parts.length
  const max = Math.max(...parts.map((p) => Math.abs(p.impact_usd)), 1)
  const total = breakdown.total_impact_usd

  return (
    <div>
      <p className="chart-legend">
        Estimated exposure of <strong>{usd(Math.abs(total))}</strong>
        {breakdown.dimension ? <> across <strong>{breakdown.dimension}</strong></> : null}. Each
        figure is (seasonally expected − actual) priced at that slice's own observed revenue per
        unit, so it can be re-multiplied by hand from the numbers in the evidence.
      </p>
      {breakdown.basis_note && <p className="source-note">{breakdown.basis_note}</p>}

      <div className="impact-list">
        {parts.map((p, i) => {
          // Negative impact means the slice moved the profitable way. Shown, not
          // hidden: an above-band move is diagnostic (click fraud, bot traffic, a
          // misconfigured floor) even though it is not a loss.
          const gained = p.impact_usd < 0
          return (
            <div key={`${p.scope_type}-${p.scope_value}-${p.metric}-${i}`} className="impact-row">
              <div className="impact-label" title={`${p.scope_type} · ${p.basis}`}>
                <span className="impact-scope">{p.scope_type}</span>
                <span className="impact-value">{scopeValue(p.scope_value)}</span>
                <span className="impact-metric">{p.metric}</span>
              </div>
              <div className="impact-track" aria-hidden="true">
                <div
                  className="impact-fill"
                  style={{
                    width: `${Math.max(1.5, (Math.abs(p.impact_usd) / max) * 100)}%`,
                    background: gained ? 'var(--status-good)' : 'var(--series-1)',
                  }}
                />
              </div>
              <div className="impact-amount tabular" style={{ color: gained ? 'var(--status-good)' : undefined }}>
                {gained ? '+' : ''}
                {usd(Math.abs(p.impact_usd))}
                <span className="impact-share">{(p.share_of_impact * 100).toFixed(0)}%</span>
              </div>
            </div>
          )
        })}
      </div>

      {(rest > 0 || showAll) && (
        <button
          type="button"
          className="link-button impact-showall"
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll
            ? `Show top ${limit} only`
            : `View all ${breakdown.parts.length} contributors — ${rest} more, each smaller than the above`}
        </button>
      )}
      <p className="source-note">
        basis: {parts[0]?.basis || 'n/a'} — shares are normalised by the sum of absolute
        impacts, so they are additive and bounded
      </p>
    </div>
  )
}
