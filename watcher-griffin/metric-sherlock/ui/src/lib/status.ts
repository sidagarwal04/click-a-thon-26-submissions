/* The single source of truth for status colour and wording.
 *
 * The old UI had this ladder copy-pasted in three files — MetricTile.tsx,
 * EventFeed.tsx and InvestigationDetail.tsx — each with a magic `Math.abs(zscore) > 1.5`
 * that corresponded to nothing in the backend's configuration, and with divergent
 * outputs (one produced labels, two produced only colours). Three copies of a threshold
 * is three chances for the UI to disagree with the engine about whether something is
 * wrong.
 *
 * Status now comes from the backend's own `severity` / `status` verdict, which is
 * produced by the same engine/bands.evaluate() the detector uses. The UI never
 * re-derives it from a raw score.
 */

export type Status = 'good' | 'amber' | 'red' | 'not_judgeable' | 'unknown'

export interface StatusStyle {
  /** CSS colour token. */
  color: string
  /** Word shown next to the dot. Colour is never the only carrier of meaning —
   *  the old UI used an 8px coloured dot alone in the event feed, which is
   *  invisible to a colour-blind reader and to a printed screenshot. */
  label: string
  /** Longer wording for tooltips / aria-labels. */
  description: string
}

const STYLES: Record<Status, StatusStyle> = {
  good: {
    color: 'var(--status-good)',
    label: 'Normal',
    description: 'Within its expected band for this time of day and day of week',
  },
  amber: {
    color: 'var(--status-warning)',
    label: 'Watch',
    description: 'Outside its expected band, but below the serious threshold',
  },
  red: {
    color: 'var(--status-critical)',
    label: 'Breach',
    description: 'Well outside its expected band',
  },
  not_judgeable: {
    // Deliberately NOT green and NOT grey-as-an-afterthought. "We cannot judge this"
    // is a distinct third state, and collapsing it into green would turn an admitted
    // gap — the 1mo grain has no usable baseline on 35 days of data, per-app CTR has
    // none at any grain — into a false all-clear.
    color: 'var(--baseline-axis)',
    label: 'No band',
    description:
      'Not enough comparable history, or too little volume, for a band to mean anything here. ' +
      'Deliberately not reported as healthy.',
  },
  unknown: {
    color: 'var(--text-muted)',
    label: 'Not evaluated',
    description: 'This combination was not evaluated in the latest sweep',
  },
}

export function statusStyle(status: string | null | undefined): StatusStyle {
  return STYLES[(status as Status) ?? 'unknown'] ?? STYLES.unknown
}

/** Maps a backend `severity` ('red' | 'amber' | '') to a Status. */
export function severityToStatus(severity: string | null | undefined, breached?: boolean): Status {
  if (severity === 'red') return 'red'
  if (severity === 'amber') return 'amber'
  if (breached) return 'red'
  return 'good'
}

/** Direction arrow. Both directions are real findings: an above-band CTR is click
 *  fraud, an above-band request count is bot traffic, an above-band eCPM is a
 *  misconfigured floor. So "up" is never rendered as reassuring. */
export function directionArrow(direction: string | null | undefined): string {
  if (direction === 'above') return '▲'
  if (direction === 'below') return '▼'
  return '—'
}

export function directionWord(direction: string | null | undefined): string {
  if (direction === 'above') return 'above band'
  if (direction === 'below') return 'below band'
  return 'within band'
}

/** Colour for an owner badge. Owners are teams, not severities, so these come from
 *  the categorical series palette rather than the status palette — using status
 *  colours here would imply that "pricing" is worse than "demand". */
const OWNER_COLORS: Record<string, string> = {
  demand: 'var(--series-1)',
  engineering: 'var(--series-2)',
  pricing: 'var(--series-4)',
  growth: 'var(--series-3)',
  creative: 'var(--series-2)',
  external: 'var(--text-secondary)',
  unassigned: 'var(--text-muted)',
}

export function ownerColor(owner: string | null | undefined): string {
  return OWNER_COLORS[owner ?? 'unassigned'] ?? OWNER_COLORS.unassigned
}

/** What each owner is expected to do about it — the business-logic bridge between a
 *  detected metric move and an action. */
export const OWNER_ACTION: Record<string, string> = {
  demand: 'Check demand partners, campaign budgets and floors',
  engineering: 'Check the SDK, render path and recent releases',
  pricing: 'Check floors, auction config and demand mix',
  growth: 'Check traffic sources, app releases and store presence',
  creative: 'Check creative fatigue and traffic quality',
  external: 'Outside the platform — confirm against local events or connectivity',
  unassigned: 'No owner could be derived for this metric',
}

/** Evidence-score label → colour. Uses the status palette because it IS a
 *  quality-of-evidence judgement. */
export function scoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'var(--text-muted)'
  if (score >= 75) return 'var(--status-good)'
  if (score >= 50) return 'var(--status-warning)'
  if (score >= 25) return 'var(--status-serious)'
  return 'var(--status-critical)'
}
