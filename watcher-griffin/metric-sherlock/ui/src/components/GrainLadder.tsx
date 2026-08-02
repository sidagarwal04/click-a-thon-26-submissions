/* Status across every monitored time frame.
 *
 * WHY THIS NOW LEADS WITH A SENTENCE
 * The previous version rendered all fourteen grains as always-visible chips, each carrying
 * six simultaneous encodings (label, border, fill, text colour, opacity, tooltip). Six
 * metric rows meant 84 chips and 84 tooltip sentences on the home screen — the single
 * densest thing on the page, for information most readers only need summarised.
 *
 * The summary answers the actual question in words: is this a momentary spike or a slow
 * erosion? That is what the ladder is diagnostically FOR:
 *
 *     red at 5m only          -> a blip, probably not actionable
 *     red only at 2w and 3w   -> slow erosion no short window would catch
 *     red from 1h to 15d      -> a sustained incident
 *
 * The chips remain, underneath, because "all fourteen were checked" is a claim a reader
 * should be able to verify rather than take on trust.
 *
 * FOUR STATES, NOT TWO. `not_judgeable` renders distinctly from `good`. On this dataset the
 * monthly grain has no usable baseline (35 days contains one complete month) and per-app
 * CTR has none at any grain (~1 click/day). Painting those green would convert a
 * documented gap into a false all-clear.
 */

import { statusStyle } from '../lib/status'
import type { GrainCell } from '../types'

interface Props {
  cells: GrainCell[]
}

const GRAIN_WORDS: Record<string, string> = {
  '5m': '5 minutes',
  '15m': '15 minutes',
  '1h': '1 hour',
  '5h': '5 hours',
  '10h': '10 hours',
  '15h': '15 hours',
  '1d': '1 day',
  '5d': '5 days',
  '10d': '10 days',
  '15d': '15 days',
  '1w': '1 week',
  '2w': '2 weeks',
  '3w': '3 weeks',
  '1mo': '1 month',
  drift: 'slow drift',
}

/** Grains in ascending window length — the order the sentence reasons over. */
const ORDER = [
  '5m', '15m', '1h', '5h', '10h', '15h', '1d', '5d', '1w', '10d', '2w', '15d', '3w', '1mo',
]

function summarise(cells: GrainCell[]): { text: string; tone: 'quiet' | 'notable' } {
  const affected = cells.filter((c) => c.status === 'red' || c.status === 'amber')
  const judged = cells.filter((c) => c.status !== 'not_judgeable')

  if (affected.length === 0) {
    return {
      text: `Within its normal range at all ${judged.length} time frames checked.`,
      tone: 'quiet',
    }
  }

  const idx = affected
    .map((c) => ORDER.indexOf(c.grain))
    .filter((i) => i >= 0)
    .sort((a, b) => a - b)
  const first = GRAIN_WORDS[ORDER[idx[0]]] ?? ORDER[idx[0]]
  const last = GRAIN_WORDS[ORDER[idx[idx.length - 1]]] ?? ORDER[idx[idx.length - 1]]

  if (affected.length === 1) {
    return { text: `Out of range at ${first} only — a short-lived move.`, tone: 'notable' }
  }
  // A contiguous run reads as one sustained event; scattered grains do not.
  const contiguous = idx[idx.length - 1] - idx[0] === idx.length - 1
  if (contiguous) {
    return {
      text: `Out of range from ${first} through ${last} — sustained, not a blip.`,
      tone: 'notable',
    }
  }
  return {
    text: `Out of range at ${affected.length} of ${judged.length} time frames, between ${first} and ${last}.`,
    tone: 'notable',
  }
}

export default function GrainLadder({ cells }: Props) {
  if (!cells || cells.length === 0) return null
  const summary = summarise(cells)
  const skipped = cells.filter((c) => c.status === 'not_judgeable').length

  return (
    <div className="ladder">
      <p className={`ladder-summary${summary.tone === 'notable' ? ' ladder-summary-notable' : ''}`}>
        {summary.text}
        {skipped > 0 && (
          <span className="ladder-skipped">
            {' '}
            {skipped} could not be judged for lack of comparable history.
          </span>
        )}
      </p>

      <div className="ladder-chips" role="group" aria-label="Status at each monitored time frame">
        {cells.map((c) => {
          const st = statusStyle(c.status)
          const words = GRAIN_WORDS[c.grain] ?? c.grain
          const filled = c.status === 'red' || c.status === 'amber'
          return (
            <span
              key={c.grain}
              className={`ladder-chip${filled ? ' ladder-chip-on' : ''}${c.status === 'not_judgeable' ? ' ladder-chip-off' : ''}`}
              style={{
                borderColor: filled ? st.color : 'var(--border)',
                background: filled ? st.color : 'transparent',
                color: filled ? '#fff' : 'var(--text-muted)',
              }}
              title={`${words}: ${st.label} — ${c.reason}`}
            >
              {c.grain}
            </span>
          )
        })}
      </div>
    </div>
  )
}
