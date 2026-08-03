/* Chooses which funnel stage the chart below is showing.
 *
 * THE STATUS DOTS ARE THE POINT
 * The page this sits on used to render all six stages at once, which meant a reader could
 * see at a glance which stage was red without touching anything. Collapsing to one chart
 * would have thrown that away and made the answer depend on clicking. So each option
 * carries its own status colour, and the selected metric defaults to the one the engine
 * marked as the driver — the screen still answers "where did the money move" with nothing
 * clicked, and the other five statuses are still readable in one sweep of the eye.
 *
 * Colour is never the only carrier: the status word rides along in the accessible name, per
 * the rule in lib/status.ts.
 *
 * Two controls, one rendered at a time (see useMediaQuery for why this is not CSS): a
 * segmented group on desktop following the tablist pattern already used by CoverageGrid,
 * and a native <select> on narrow screens, where six pills would wrap into a block taller
 * than the chart they control.
 */

import { memo } from 'react'

import { useMediaQuery } from '../hooks/useMediaQuery'

export interface MetricOption {
  key: string
  label: string
  /** CSS colour for the status dot. */
  statusColor: string
  /** Status word — "Normal", "Watch", "Breach", "No band". */
  statusLabel: string
}

interface Props {
  items: MetricOption[]
  selected: string
  onSelect: (key: string) => void
  /** id of the chart panel these control. */
  panelId: string
}

/** Matches the existing @media (max-width: 620px) breakpoint in index.css. */
const COMPACT = '(max-width: 620px)'

function MetricSelector({ items, selected, onSelect, panelId }: Props) {
  const compact = useMediaQuery(COMPACT)

  if (compact) {
    const current = items.find((i) => i.key === selected)
    return (
      <div className="mts-picker mts-picker-compact">
        <span
          className="mts-dot"
          style={{ background: current?.statusColor ?? 'var(--text-muted)' }}
          aria-hidden="true"
        />
        <label className="sr-only" htmlFor="mts-select">
          Funnel stage to chart
        </label>
        <select
          id="mts-select"
          className="mts-select"
          value={selected}
          aria-controls={panelId}
          onChange={(e) => onSelect(e.target.value)}
        >
          {items.map((i) => (
            <option key={i.key} value={i.key}>
              {i.label} — {i.statusLabel}
            </option>
          ))}
        </select>
      </div>
    )
  }

  return (
    <div className="mts-picker" role="tablist" aria-label="Funnel stage to chart">
      {items.map((i) => {
        const active = i.key === selected
        return (
          <button
            key={i.key}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls={panelId}
            className={`pill mts-tab${active ? ' pill-active' : ''}`}
            onClick={() => onSelect(i.key)}
          >
            <span className="mts-dot" style={{ background: i.statusColor }} aria-hidden="true" />
            {i.label}
            <span className="sr-only"> — {i.statusLabel}</span>
          </button>
        )
      })}
    </div>
  )
}

export default memo(MetricSelector)
