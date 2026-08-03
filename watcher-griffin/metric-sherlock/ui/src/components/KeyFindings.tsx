/* The incident in five bullets.
 *
 * NOT A SUMMARY OF THE NARRATION
 * Every bullet is one discrete field off the incident, formatted. None of it comes from
 * splitting `narration` into sentences, which was the obvious way to do this and the wrong
 * one: the narration is a single prose string, and naive sentence-splitting mangles the very
 * things that matter here — "$1,234.56" and "vs. baseline" both contain a full stop — while
 * producing prose fragments rather than facts. Deriving from the fields instead means each
 * bullet is exactly as trustworthy as the number behind it, and the page keeps working when
 * the language model is unavailable.
 *
 * A field that is absent drops its bullet rather than printing a placeholder. A row reading
 * "Mechanism: —" tells the reader nothing except that the page has a gap in it.
 */

import { metricLabel, scopeValue, usd } from '../lib/format'
import type { IncidentDetail } from '../types'

interface Props {
  detail: IncidentDetail
  /** Pre-formatted by the caller, which already derives them for the summary card. Passed
   *  rather than re-derived so the two can never disagree about the same incident. */
  move?: string | null
  band?: string | null
}

export default function KeyFindings({ detail: d, move, band }: Props) {
  const bullets: { key: string; body: React.ReactNode }[] = []

  bullets.push({
    key: 'moved',
    body: (
      <>
        <strong>{metricLabel(d.root_metric)}</strong>{' '}
        {d.direction === 'above' ? 'is unusually high for' : 'is below normal for'}{' '}
        <strong>{scopeValue(d.root_scope_value)}</strong>
        {move && (
          <>
            {' '}
            — moved <strong className="tabular">{move}</strong>
            {band && <> ({band})</>}
          </>
        )}
      </>
    ),
  })

  if (d.impact_usd_per_day) {
    const multi = (d.windows_spanned ?? 1) > 1
    bullets.push({
      key: 'cost',
      body: (
        <>
          Worth <strong className="tabular">{usd(Math.abs(d.impact_usd_per_day))}/day</strong>{' '}
          {d.impact_usd < 0 ? 'gained' : 'exposed'}
          {/* Only worth two figures when they differ. On a single-window incident the
              total and the daily rate are the same number, and printing it twice reads
              as two findings. */}
          {multi ? (
            <>
              {' '}
              — <span className="tabular">{usd(Math.abs(d.impact_usd))}</span> over{' '}
              {d.windows_spanned} consecutive {d.grain} windows
            </>
          ) : (
            <> over the {d.grain} window</>
          )}
        </>
      ),
    })
  }

  /* No mechanism bullet. It is the Root Cause card immediately above this one, at display
     size — repeating the whole paragraph here made the longest "key finding" a copy of the
     thing it was meant to summarise. */

  if (d.evidence_score_detail) {
    bullets.push({
      key: 'evidence',
      body: (
        <>
          Evidence <strong className="tabular">{d.evidence_score_detail.score}/100</strong> —{' '}
          {d.evidence_score_detail.label}
        </>
      ),
    })
  }

  if (d.ruled_out && d.ruled_out.length > 0) {
    bullets.push({
      key: 'ruled',
      body: (
        <>
          <strong>{d.ruled_out.length}</strong> alternative
          {d.ruled_out.length === 1 ? '' : 's'} checked and cleared
        </>
      ),
    })
  }

  if (d.member_event_count) {
    bullets.push({
      key: 'members',
      body: (
        <>
          <strong className="tabular">{d.member_event_count}</strong> underlying band breach
          {d.member_event_count === 1 ? '' : 'es'}
          {d.breached_metrics.length > 1 && <> across {d.breached_metrics.length} metrics</>}
        </>
      ),
    })
  }

  return (
    <ul className="key-findings">
      {bullets.map((b) => (
        <li key={b.key}>{b.body}</li>
      ))}
    </ul>
  )
}
