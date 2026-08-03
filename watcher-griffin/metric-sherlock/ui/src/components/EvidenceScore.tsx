/* The evidence score, with its formula and its full breakdown.
 *
 * READ THE CAVEAT RENDERED BELOW — IT IS NOT DECORATION
 * This is the one number in the whole interface that is a weighted blend rather than a
 * direct query result. Every other figure on screen traces to a logged ClickHouse
 * query. This one is an index we defined.
 *
 * So the component never shows the number alone. It always shows, in the same view:
 *   - the published formula that produced it,
 *   - every component with its raw input, points earned and points available,
 *   - the arithmetic check (components sum vs displayed score),
 *   - and an explicit statement that it measures corroboration, not probability.
 *
 * That is what keeps it defensible: a reader can re-add the points by hand and can see
 * exactly which checks carried it. The words "confident" and "% likely" are avoided
 * deliberately — the score does not support a claim about likelihood of correctness.
 *
 * Note also that it can go DOWN: a chronically-breaching slice scores negative on
 * corroboration, because a slice that is out of band most of the time has a mis-set
 * baseline rather than an incident.
 */

import Provenance from './Provenance'
import { scoreColor } from '../lib/status'
import type { EvidenceScoreDetail, Fact } from '../types'

interface Props {
  detail: EvidenceScoreDetail | null
  compact?: boolean
  /** The `evidence.score` Fact, so the most-questioned number on the page carries its own
   *  single query rather than only its formula. Optional: the component still renders
   *  without provenance, which is what keeps it usable on any page that lacks it. */
  fact?: Fact | null
  facts?: Record<string, Fact>
  incidentId?: string
}

export default function EvidenceScore({
  detail, compact = false, fact, facts, incidentId,
}: Props) {
  if (!detail) {
    return (
      <p className="muted-note">
        No evidence score was recorded for this incident.
      </p>
    )
  }

  const color = scoreColor(detail.score)
  const sumMatches = Math.abs(detail.components_sum - detail.score) <= 1.0

  if (compact) {
    return (
      <span className="score-inline tabular" title={detail.formula}>
        <span className="score-inline-bar" aria-hidden="true">
          <span
            className="score-inline-fill"
            style={{ width: `${detail.score}%`, background: color }}
          />
        </span>
        <span style={{ color, fontWeight: 700 }}>{detail.score}</span>
      </span>
    )
  }

  return (
    <div>
      <div className="score-head">
        <div>
          <div className="score-number tabular" style={{ color }}>
            {/* The single query for the confidence figure, at the figure. This is the
                number a reader is most likely to challenge, so it is the one that most
                needs to answer "run this and see" rather than "trust the weights". */}
            <Provenance fact={fact} facts={facts} incidentId={incidentId ?? ''}>
              {detail.score}
            </Provenance>
            <span className="score-denom">/ 100</span>
          </div>
          <div className="score-label" style={{ color }}>
            {detail.label} evidence
          </div>
        </div>
        <div className="score-bar" aria-hidden="true">
          <div className="score-fill" style={{ width: `${detail.score}%`, background: color }} />
        </div>
      </div>

      <div className="score-components">
        {detail.components.map((c) => {
          const pctOfMax = c.max_points ? (Math.max(0, c.points) / c.max_points) * 100 : 0
          const negative = c.points < 0
          return (
            <div key={c.name} className="score-comp">
              <div className="score-comp-head">
                <span className="score-comp-name">{c.name}</span>
                <span
                  className="score-comp-points tabular"
                  style={{ color: negative ? 'var(--status-critical)' : undefined }}
                >
                  {negative ? '−' : ''}
                  {Math.abs(c.points)} / {c.max_points}
                </span>
              </div>
              <div className="score-comp-track" aria-hidden="true">
                <div
                  className="score-comp-fill"
                  style={{
                    width: `${Math.min(100, pctOfMax)}%`,
                    background: negative ? 'var(--status-critical)' : color,
                  }}
                />
              </div>
              <div className="score-comp-raw tabular">{c.raw}</div>
              <div className="score-comp-reason">{c.reason}</div>
              {c.source && (
                <div className="source-note">
                  from <code>{c.source}</code>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="score-formula">
        <div>
          <strong>How this is calculated:</strong> {detail.formula}
        </div>
        <div className="tabular" style={{ marginTop: '0.3rem' }}>
          components sum to {detail.components_sum} → displayed as {detail.score}
          {sumMatches ? ' ✓' : ' — MISMATCH, do not trust this score'}
        </div>
        <div className="warn-note" style={{ marginTop: '0.4rem' }}>
          {detail.caveat}
        </div>
      </div>
    </div>
  )
}
