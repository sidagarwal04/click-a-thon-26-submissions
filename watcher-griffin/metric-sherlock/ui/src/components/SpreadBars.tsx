/* Spread bars: how widely the deviation reached across each independent dimension.
 *
 * WHAT IT PROVES — this is the localisation argument itself
 * A root cause claim is really two claims: it happened HERE, and it did NOT happen
 * everywhere. The second half is what rules out the alternatives, and it is the half
 * a text diagnosis usually skips.
 *
 *     app        33 / 170  (19%)  ▓▓░░░░░░░░  concentrated
 *     ad_format   5 /   5 (100%)  ▓▓▓▓▓▓▓▓▓▓  spread — cause is upstream
 *
 * Read together those two bars say: the fill drop is not any one app's fault (only 19%
 * of apps moved) and it is not any one format's fault (all of them moved), so the
 * cause sits above both — which is exactly how the engine concluded "Android demand".
 *
 * A HIGH bar is not bad and a LOW bar is not good. A long bar means "the cause is
 * upstream of this dimension", a short bar means "concentrated in this dimension".
 * The legend says so, because the intuition from most dashboards is the opposite.
 */

import type { RuledOutBlock } from '../types'

interface Props {
  ruledOut: RuledOutBlock[] | null
}

interface Row {
  dimension: string
  breached: number
  evaluated: number
  breadth: number
  concentration: number
  topValue: string
  reason: string
  sourceSteps: string[]
}

function toRows(ruledOut: RuledOutBlock[] | null): Row[] {
  if (!ruledOut) return []
  return ruledOut
    .filter((r) => r.check.startsWith('dimension:'))
    .map((r) => {
      const n = r.numbers ?? {}
      return {
        dimension: r.check.slice('dimension:'.length),
        breached: Number(n.breached ?? 0),
        evaluated: Number(n.evaluated ?? 0),
        breadth: Number(n.breadth ?? 0),
        concentration: Number(n.concentration ?? 0),
        topValue: String(n.top_value ?? ''),
        reason: r.reason,
        sourceSteps: r.source_steps ?? [],
      }
    })
    .filter((r) => r.evaluated > 0)
    .sort((a, b) => b.breadth - a.breadth)
}

/** Same thresholds the backend's uniformity module uses, so the word next to the bar
 *  matches the word the engine used when it made the decision. */
function verdictOf(breadth: number): { word: string; color: string } {
  if (breadth >= 0.5) return { word: 'spread — cause is upstream', color: 'var(--series-2)' }
  if (breadth <= 0.25) return { word: 'concentrated here', color: 'var(--status-critical)' }
  return { word: 'mixed', color: 'var(--status-warning)' }
}

export default function SpreadBars({ ruledOut }: Props) {
  const rows = toRows(ruledOut)
  if (rows.length === 0) {
    return (
      <p className="muted-note">
        No independent dimensions were evaluated for this incident, so no spread evidence
        is available. The deviation and its segment still stand; the localisation is less
        corroborated.
      </p>
    )
  }

  const flat = rows.filter((r) => r.breached === 0)

  return (
    <div>
      <p className="chart-legend">
        Each bar is the share of that dimension's entities that also breached. A{' '}
        <strong>long</strong> bar means the deviation is spread across that dimension, so the
        cause lies <em>above</em> it. A <strong>short</strong> bar means it is concentrated
        there. This is how the responsible segment is isolated — and how the others are ruled out.
      </p>

      <div className="spread-list">
        {rows.map((r) => {
          const v = verdictOf(r.breadth)
          return (
            <div key={r.dimension} className="spread-row" title={r.reason}>
              <div className="spread-label">{r.dimension}</div>
              <div className="spread-track" aria-hidden="true">
                <div
                  className="spread-fill"
                  style={{ width: `${Math.max(1.5, r.breadth * 100)}%`, background: v.color }}
                />
              </div>
              <div className="spread-numbers tabular">
                {r.breached} / {r.evaluated}
                <span className="spread-pct">{(r.breadth * 100).toFixed(0)}%</span>
              </div>
              <div className="spread-verdict" style={{ color: v.color }}>
                {v.word}
              </div>
            </div>
          )
        })}
      </div>

      {flat.length > 0 && (
        <p className="muted-note">
          Completely unaffected, and therefore ruled out:{' '}
          <strong>{flat.map((f) => f.dimension).join(', ')}</strong> — every evaluated entity
          in {flat.length === 1 ? 'that dimension' : 'those dimensions'} stayed inside its band.
        </p>
      )}

      {rows.some((r) => r.concentration >= 0.6 && r.topValue) && (
        <p className="muted-note">
          {rows
            .filter((r) => r.concentration >= 0.6 && r.topValue)
            .map(
              (r) =>
                `Within ${r.dimension}, "${r.topValue}" alone accounts for ${(r.concentration * 100).toFixed(0)}% of the measured impact.`,
            )
            .join(' ')}
        </p>
      )}

      {rows[0]?.sourceSteps?.length > 0 && (
        <p className="source-note">
          measured from the sweep's own queries, e.g. <code>{rows[0].sourceSteps[0]}</code> — the
          same evaluation that produced the detection, not a separate one
        </p>
      )}
    </div>
  )
}
