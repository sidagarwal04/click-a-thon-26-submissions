/* Revenue waterfall: which factor moved the money.
 *
 * WHAT IT PROVES
 * Revenue is the sum of four independent levers, and this shows which one actually
 * moved it. "Revenue is down" is not actionable; "revenue is down and fill rate
 * accounts for 91% of it" routes straight to the demand team.
 *
 * WHY THE BARS ADD UP EXACTLY
 * The identity is exact, not approximate:
 *
 *     Requests × (fills/requests) × (impressions/fills) × (revenue/impressions) ≡ revenue
 *
 * Every intermediate term cancels, so in log space the four factor log-ratios sum to
 * log(revenue_now / revenue_expected) with a residual of zero. The chart therefore
 * shows the residual explicitly — if it is not ~0 something is genuinely missing from
 * the decomposition, and the reader should be told rather than shown four bars that
 * quietly do not reconcile.
 *
 * (The earlier three-factor version omitted show rate, which meant any render movement
 * was silently absorbed into the other factors and attributed to the wrong owner.)
 */

import { rate } from '../lib/format'
import type { FactorBreakdown } from '../types'

interface Props {
  factors: FactorBreakdown[]
  primaryFactor: string | null
  residual?: number | null
  identityCloses?: boolean | null
}

const FACTOR_LABELS: Record<string, string> = {
  requests: 'Ad requests',
  fill_rate: 'Fill rate',
  render_rate: 'Show rate',
  ecpm: 'eCPM',
}

const FACTOR_OWNERS: Record<string, string> = {
  requests: 'growth',
  fill_rate: 'demand',
  render_rate: 'engineering',
  ecpm: 'pricing',
}

export default function WaterfallChart({ factors, primaryFactor, residual, identityCloses }: Props) {
  if (!factors || factors.length === 0) {
    return (
      <p className="muted-note">
        No factor decomposition is available — this incident's root metric is not revenue.
      </p>
    )
  }

  const max = Math.max(...factors.map((f) => Math.abs(f.share)), 0.0001)

  return (
    <div>
      <p className="chart-legend">
        Revenue = Requests × Fill rate × Show rate × eCPM ÷ 1000. This identity is{' '}
        <strong>exact</strong> — every intermediate term cancels — so these four shares
        account for the whole move with nothing left over.
      </p>

      <div className="waterfall">
        {factors.map((f) => {
          const isPrimary = f.factor === primaryFactor
          const negative = f.share < 0
          const label = FACTOR_LABELS[f.factor] ?? f.factor
          return (
            <div key={f.factor} className={`wf-row${isPrimary ? ' wf-row-primary' : ''}`}>
              <div className="wf-label">
                {label}
                <span className="wf-owner">{FACTOR_OWNERS[f.factor] ?? ''}</span>
                {isPrimary && <span className="badge badge-driver">driver</span>}
              </div>

              {/* Zero-centred: bars grow left for a fall and right for a rise, so the
                  direction of each lever is readable without decoding a sign. */}
              <div className="wf-track" aria-hidden="true">
                <div className="wf-axis" />
                <div
                  className="wf-bar"
                  style={{
                    width: `${(Math.abs(f.share) / max) * 48}%`,
                    [negative ? 'right' : 'left']: '50%',
                    background: negative ? 'var(--status-critical)' : 'var(--status-good)',
                  }}
                />
              </div>

              <div className="wf-numbers tabular">
                <span className="wf-share" style={{ color: negative ? 'var(--status-critical)' : 'var(--status-good)' }}>
                  {negative ? '−' : '+'}
                  {rate(Math.abs(f.share), 0)}
                </span>
                <span className="wf-values">
                  {f.now.toFixed(4)} vs {f.baseline.toFixed(4)}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {residual !== null && residual !== undefined && (
        <p className={identityCloses === false ? 'warn-note' : 'source-note'}>
          {identityCloses === false ? (
            <>
              <strong>Identity did not close</strong> (residual {residual.toExponential(2)}). A
              factor is unaccounted for, so treat these shares as incomplete rather than as a
              full explanation.
            </>
          ) : (
            <>residual {residual.toExponential(2)} — the decomposition closes, so nothing is unattributed</>
          )}
        </p>
      )}
    </div>
  )
}
