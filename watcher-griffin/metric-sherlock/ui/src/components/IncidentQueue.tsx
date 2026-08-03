/* The work queue: what moved, newest first.
 *
 * ORDERED BY TIME, LED BY MOVEMENT
 * This was ranked by dollars per day and said so. The argument for that ranking was real --
 * a 6-sigma move in a slice earning cents is arithmetically striking and commercially
 * irrelevant -- but it made the queue a cost report, and the question this system exists to
 * answer is "what moved, and where". So the row now leads with the movement itself: how far
 * the root metric went from its seasonal centre, in the unit that metric actually moves in,
 * with the band-widths beside it. The exposure estimate is still here, demoted to the meta
 * line, because it is still the honest answer to "does this matter commercially" -- it is no
 * longer the answer to "what happened".
 *
 * Ordering is chronological. Dollars still decide what is GATED (a large deviation on a
 * commercially immaterial slice is not an incident) -- they no longer decide what is read
 * first.
 *
 * TRIMMED FROM SEVENTEEN FIELDS TO SIX
 * An audit counted 17 fields per row in the previous version, including the grain rendered
 * twice and a signature code (`S4`) that means nothing to anyone who has not read the
 * source. A queue is scanned, not studied: a row answers only "what moved, how far, what,
 * who, how sure, when" -- and the mechanism sentence is trimmed to its first clause.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { bandWidths, dateTime, scopeValue, usdCompact } from '../lib/format'
import { formatMove } from '../lib/metricConfig'
import { stagger } from '../lib/motion'
import { scoreColor, statusStyle } from '../lib/status'
import type { IncidentRow } from '../types'
import OwnerBadge from './OwnerBadge'

interface Props {
  incidents: IncidentRow[]
}

function rowStatus(inc: IncidentRow): string {
  if (inc.gated_by_impact) return 'not_judgeable'
  if (inc.signature === 'S0') return 'amber'
  return 'red'
}

/** Plain-language subject, so a reader does not have to decode `fill_rate` +
 *  `os_family=Android`. */
const METRIC_WORDS: Record<string, string> = {
  fill_rate: 'Fill rate',
  render_rate: 'Show rate',
  ctr: 'Click-through rate',
  ecpm: 'eCPM',
  rpr: 'Revenue per request',
  revenue: 'Revenue',
  requests: 'Ad requests',
  fills: 'Fills',
  impressions: 'Impressions',
  clicks: 'Clicks',
}

function Row({ inc, index }: { inc: IncidentRow; index: number }) {
  const navigate = useNavigate()
  const st = statusStyle(rowStatus(inc))
  const open = () => navigate(`/incidents/${inc.incident_id}`)
  const metric = METRIC_WORDS[inc.root_metric] ?? inc.root_metric
  const direction = inc.direction === 'above' ? 'is unusually high' : 'is below normal'
  // First clause only. A queue row that wraps to six lines stops being scannable.
  const gist = (inc.mechanism || '').split(/(?<=\.)\s/)[0] || ''
  // How far it went, in the unit this metric moves in — percentage points for a rate,
  // percent for everything else. Null when the join found no root breach to measure.
  const move = formatMove(inc.root_metric, inc.root_value, inc.root_center)
  const arrow = inc.direction === 'above' ? '↑' : '↓'
  const band = inc.root_deviation_score != null ? bandWidths(inc.root_deviation_score) : null

  return (
    <article
      className="q-row reveal-item"
      style={stagger(index)}
      role="button"
      tabIndex={0}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          open()
        }
      }}
      aria-label={`${metric} ${direction} on ${scopeValue(inc.root_scope_value)}${move ? `, moved ${move}` : ''}${band ? `, ${band}` : ''}, owned by ${inc.owner}`}
    >
      <div className="q-move">
        <span className="q-move-value tabular" style={{ color: st.color }}>
          {move ? (
            <>
              <span className="q-move-arrow" aria-hidden="true">{arrow}</span>
              {move.replace(/^[+−]/, '')}
            </>
          ) : (
            '—'
          )}
        </span>
        <span className="q-move-band tabular">{band ?? 'no band'}</span>
      </div>

      <div className="q-body">
        <h3 className="q-title">
          {metric} {direction} for <strong>{scopeValue(inc.root_scope_value)}</strong>
        </h3>
        {gist && <p className="q-gist">{gist}</p>}
      </div>

      <div className="q-meta">
        <OwnerBadge owner={inc.owner} />
        {/* Absolute, not "10d ago". The data clock sits weeks behind the wall clock, so a
            relative age is ambiguous about which of the two it counts from. */}
        <span className="q-age tabular">{dateTime(inc.opened_at)}</span>
        <span className="q-exposure tabular" title="Estimated exposure per day — what this is worth commercially, not how far it moved">
          {usdCompact(Math.abs(inc.impact_usd_per_day))}/day
        </span>
        <span
          className="q-conf"
          title={`Evidence score ${inc.evidence_score} of 100 — see the incident for the full breakdown`}
        >
          <span className="q-conf-track" aria-hidden="true">
            <span
              className="q-conf-fill"
              style={{
                width: `${inc.evidence_score}%`,
                background: scoreColor(inc.evidence_score),
              }}
            />
          </span>
          <span className="q-conf-num tabular">{inc.evidence_score}</span>
        </span>
      </div>

      <span className="q-chev" aria-hidden="true">
        →
      </span>
    </article>
  )
}

export default function IncidentQueue({ incidents }: Props) {
  const [showGated, setShowGated] = useState(false)
  const alertable = incidents.filter((i) => !i.gated_by_impact)
  const gated = incidents.filter((i) => i.gated_by_impact)

  if (incidents.length === 0) {
    return (
      <p className="muted-note">
        Nothing recorded. Either nothing has left its normal range, or the monitor has not run
        yet — the sweep panel above tells those apart.
      </p>
    )
  }

  return (
    <div>
      {alertable.length === 0 ? (
        <p className="all-clear">
          <span className="all-clear-dot" aria-hidden="true" />
          Nothing outside its normal range.
          {gated.length > 0 && ` ${gated.length} smaller findings recorded below the raising threshold.`}
        </p>
      ) : (
        <div className="q-list">
          {alertable.map((inc, i) => (
            <Row key={inc.incident_id} inc={inc} index={i} />
          ))}
        </div>
      )}

      {gated.length > 0 && (
        <div className="q-gated">
          <button
            type="button"
            className="ghost-button"
            onClick={() => setShowGated((v) => !v)}
            aria-expanded={showGated}
          >
            {showGated ? 'Hide' : 'Show'} {gated.length} smaller finding
            {gated.length === 1 ? '' : 's'} — movements on slices too small to raise
          </button>
          {showGated && (
            <div className="q-list q-list-muted">
              {gated.map((inc, i) => (
                <Row key={inc.incident_id} inc={inc} index={i} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
