/* One metric, charted large, with its headline figures.
 *
 * DELIBERATELY KNOWS NOTHING ABOUT ANY PARTICULAR METRIC
 * There is no `if (metric === 'revenue')` here and there must never be one. Everything that
 * varies — the title, how a value is written, how a change is written, the accent colour —
 * arrives as a prop, resolved by the caller from lib/metricConfig. That is what makes this
 * usable for a metric that does not exist yet: the backend adds it, the caller resolves its
 * format from its unit, and this renders it unchanged.
 *
 * The evidence that explains the figures — the meaning blurb, the reason, the grain ladder,
 * the source query — comes in as `children`, because it is the CALLER's business what
 * counts as evidence. Keeping it out of here is the difference between a chart component
 * and an ops-console component.
 *
 * WHY BandChart IS KEYED BY METRIC
 * BandChart caches one ECharts instance for its lifetime and disposes it on unmount, and it
 * early-returns a plain paragraph when a metric has no history at all. Reusing a single
 * instance across metric switches would therefore strand a live instance bound to a removed
 * DOM node the first time the reader selected a metric with an empty series. Keying by
 * metric gives each one a clean instance, and has the side benefit that the band's entrance
 * animation replays on every switch, so the corridor visibly redraws rather than snapping.
 */

import { Suspense, lazy, memo } from 'react'
import type { ReactNode } from 'react'

import type { BandPoint } from '../types'

/* ECharts is ~600 kB minified — by far the largest thing in the bundle. Code-split so the
 * headline figure and the work queue paint immediately and the chart fills in a moment
 * later. */
const BandChart = lazy(() => import('./BandChart'))

interface Props {
  /** Identity only — keys the chart instance so switching metrics gets a clean one. */
  metricKey: string
  title: string
  /** Actual, expected and band in one array: each point carries value / center / spread. */
  points: BandPoint[]
  /** '$' | '%' | '' — how the chart's own axis and tooltip write numbers. */
  unit: string
  /** How the headline figures are written. From lib/metricConfig. */
  formatValue: (v: number | null | undefined) => string
  currentValue: number | null
  expectedValue: number | null
  /** Pre-formatted by the caller, so this component never decides pp vs percent. */
  deviation: string | null
  statusColor: string
  statusLabel: string
  /** Whether to colour the deviation figure — true when the status is amber or red. */
  notable?: boolean
  isDriver?: boolean
  /** CSS custom-property NAME for the signal colour. */
  accentToken?: string
  height?: number
  panelId: string
  children?: ReactNode
}

function MetricTrendChart({
  metricKey,
  title,
  points,
  unit,
  formatValue,
  currentValue,
  expectedValue,
  deviation,
  statusColor,
  statusLabel,
  notable = false,
  isDriver = false,
  accentToken,
  height = 280,
  panelId,
  children,
}: Props) {
  return (
    <div
      className="mts-panel"
      id={panelId}
      role="tabpanel"
      aria-label={title}
      // --chart-h keeps the Suspense placeholder exactly as tall as the chart that
      // replaces it, so the panel never jumps when the split chunk lands.
      style={{ ['--row-accent' as string]: statusColor, ['--chart-h' as string]: `${height}px` }}
    >
      <div className="mts-rail" aria-hidden="true" />

      <header className="mts-head">
        <div className="fnl-identity">
          <h3 className="fnl-name">{title}</h3>
          {/* Colour AND word. Never one without the other. */}
          <span className="fnl-status" style={{ color: statusColor }}>
            <span
              className="fnl-status-dot"
              style={{ background: statusColor }}
              aria-hidden="true"
            />
            {statusLabel}
          </span>
          {isDriver && (
            <span
              className="tag tag-driver"
              title="Accounts for the largest share of the revenue move"
            >
              main driver
            </span>
          )}
        </div>

        <div className="mts-figures">
          <span className="fnl-value tabular">{formatValue(currentValue)}</span>
          <span className="fnl-expected tabular">
            expected {formatValue(expectedValue)}
            {deviation && (
              <em className="fnl-change" style={{ color: notable ? statusColor : undefined }}>
                {deviation}
              </em>
            )}
          </span>
        </div>
      </header>

      <div className="mts-chart">
        {/* Reserves the chart's height so nothing shifts when it arrives. */}
        <Suspense fallback={<div className="chart-placeholder" aria-hidden="true" />}>
          <BandChart
            key={metricKey}
            points={points}
            unit={unit}
            label={title}
            height={height}
            accent={accentToken}
          />
        </Suspense>
      </div>

      {children}
    </div>
  )
}

export default memo(MetricTrendChart)
