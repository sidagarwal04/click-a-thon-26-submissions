'use client'

import {useRef, useState} from 'react'
import type {ConcurrencyPoint} from '@/lib/types'
import {istDate, istDateTime, istTime} from '@/lib/time'
import type {Grain} from '@/lib/grain'
import styles from './ConcurrencyChart.module.css'

export interface ChartSeries {
  label: string
  color: string
  points: ConcurrencyPoint[]
  /** Reference lines + peak marker are only drawn when this is the sole series on the chart
   *  (Sessions or Users mode): in Compare mode two sets would clutter more than they inform. */
  avg?: number
  p95?: number
  peakMinute?: string
}

interface Props {
  series: ChartSeries[]
  /** Only affects how an axis tick is written: a day-grain tick rendered as a time reads
   *  "12:00 am" on every one of them. The points themselves are bucketed before they get here. */
  grain: Grain
}

const W = 1000
const H = 360
const PAD = {l: 52, r: 12, t: 26, b: 26}
const PLOT_W = W - PAD.l - PAD.r
const PLOT_H = H - PAD.t - PAD.b

function xAt(i: number, n: number): number {
  return PAD.l + (i / Math.max(1, n - 1)) * PLOT_W
}
function yAt(v: number, max: number): number {
  return H - PAD.b - (max ? (v / max) * PLOT_H : 0)
}
function pathFor(points: ConcurrencyPoint[], n: number, max: number): string {
  if (!points.length) return ''
  return points.map((p, i) => `${i ? 'L' : 'M'}${xAt(i, n).toFixed(1)} ${yAt(p[1], max).toFixed(1)}`).join(' ')
}

/**
 * Hand-rolled SVG line/area chart. No charting dependency: the shape of this data (a dense,
 * WITH-FILL-densified per-minute series) is simple enough that a chart library buys nothing
 * but bundle size. Renders one filled glow area for a single series (Sessions or Users mode),
 * or plain overlaid strokes for two series (Compare mode) so neither line is visually favored.
 *
 * Beyond the raw curve: avg/p95 reference lines and a peak marker (single-series only), a live
 * pulsing dot on the most recent minute (so the chart reads as "still moving", not a snapshot),
 * and a hover crosshair with a tooltip that reads BOTH series at once: the exact minute-by-
 * minute divergence Compare mode exists to show, not just the implied gap between two shapes.
 */
export default function ConcurrencyChart({series, grain}: Props) {
  const nf = new Intl.NumberFormat('en-IN')
  const svgRef = useRef<SVGSVGElement>(null)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const withPoints = series.filter((s) => s.points.length > 0)
  const max = Math.max(1, ...withPoints.flatMap((s) => s.points.map((p) => p[1])))
  const longest = withPoints.reduce((a, s) => (s.points.length > a.length ? s.points : a), [] as ConcurrencyPoint[])
  const n = longest.length

  const hi = hoverIndex != null && hoverIndex < n ? hoverIndex : null
  const hoverX = hi != null && n > 1 ? xAt(hi, n) : null
  const tooltipLeftPct = hoverX != null ? Math.min(96, Math.max(4, (hoverX / W) * 100)) : null

  function handleMove(e: React.MouseEvent<SVGRectElement>) {
    const svg = svgRef.current
    if (!svg || n < 2) return
    const rect = svg.getBoundingClientRect()
    const frac = (e.clientX - rect.left) / rect.width
    const viewBoxX = frac * W
    const i = Math.round(((viewBoxX - PAD.l) / PLOT_W) * (n - 1))
    setHoverIndex(Math.min(n - 1, Math.max(0, i)))
  }

  return (
    <div className={styles.wrap}>
      <svg
        ref={svgRef}
        className={styles.svg}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        onMouseLeave={() => setHoverIndex(null)}
      >
        <defs>
          {series.map((s) => (
            <linearGradient id={`grad-${s.label}`} key={s.label} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.32"/>
              <stop offset="100%" stopColor={s.color} stopOpacity="0"/>
            </linearGradient>
          ))}
        </defs>

        {/* horizontal oscilloscope grid, labelled with the value not the pixel */}
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const v = Math.round(max * frac)
          const yPos = H - PAD.b - frac * PLOT_H
          return (
            <g key={frac}>
              <line className={styles.grid} x1={PAD.l} x2={W - PAD.r} y1={yPos} y2={yPos}/>
              <text className={styles.axisLabel} x={4} y={yPos + 3}>
                {nf.format(v)}
              </text>
            </g>
          )
        })}

        {withPoints.length === 1 &&
          withPoints.map((s) => {
            const d = pathFor(s.points, n, max)
            const base = `${d} L${PAD.l + PLOT_W} ${H - PAD.b} L${PAD.l} ${H - PAD.b} Z`
            return (
              <g key={s.label}>
                <path d={base} fill={`url(#grad-${s.label})`}/>
                <path d={d} fill="none" stroke={s.color} strokeWidth={1.8} className={styles.glow}/>
              </g>
            )
          })}

        {withPoints.length > 1 &&
          withPoints.map((s) => (
            <path
              key={s.label}
              d={pathFor(s.points, n, max)}
              fill="none"
              stroke={s.color}
              strokeWidth={1.6}
              className={styles.glow}
            />
          ))}

        {/* Reference lines + peak marker: single-series only. Average is the steady-state read;
            p95 is what capacity planning actually budgets against, since a bare peak can be one
            outlier minute. */}
        {withPoints.length === 1 &&
          withPoints.map((s) => {
            const peakIdx = s.peakMinute ? s.points.findIndex((p) => p[0] === s.peakMinute) : -1
            return (
              <g key={`ref-${s.label}`}>
                {s.avg != null && (
                  <g>
                    <line className={styles.refLine} x1={PAD.l} x2={W - PAD.r} y1={yAt(s.avg, max)} y2={yAt(s.avg, max)}/>
                    <text className={styles.refLabel} x={W - PAD.r - 4} y={yAt(s.avg, max) - 4} textAnchor="end">
                      avg {nf.format(Math.round(s.avg))}
                    </text>
                  </g>
                )}
                {s.p95 != null && (
                  <g>
                    <line
                      className={styles.refLineP95}
                      x1={PAD.l}
                      x2={W - PAD.r}
                      y1={yAt(s.p95, max)}
                      y2={yAt(s.p95, max)}
                    />
                    <text className={styles.refLabel} x={W - PAD.r - 4} y={yAt(s.p95, max) - 4} textAnchor="end">
                      p95 {nf.format(Math.round(s.p95))}
                    </text>
                  </g>
                )}
                {peakIdx >= 0 &&
                  (() => {
                    const px = xAt(peakIdx, n)
                    const py = yAt(s.points[peakIdx]?.[1] ?? 0, max)
                    return (
                      <g>
                        <line className={styles.peakGuide} x1={px} x2={px} y1={PAD.t} y2={py}/>
                        <circle cx={px} cy={py} r={3.5} className={styles.peakDot} style={{color: s.color}}/>
                        <text className={styles.refLabel} x={px} y={PAD.t - 8} textAnchor="middle">
                          peak
                        </text>
                      </g>
                    )
                  })()}
              </g>
            )
          })}

        {/* Live end-of-line marker: the most recent minute in the window, pulsing like the
            header's live indicator, so the chart reads as still updating, not a static snapshot. */}
        {withPoints.map((s) => {
          const i = s.points.length - 1
          if (i < 0) return null
          return (
            <circle
              key={`live-${s.label}`}
              cx={xAt(i, n)}
              cy={yAt(s.points[i]?.[1] ?? 0, max)}
              r={4}
              className={styles.livePoint}
              style={{color: s.color}}
            />
          )
        })}

        {/* Hover crosshair + per-series dots, synced across both curves in Compare mode so the
            exact divergence at one minute is readable, not just implied by the overlaid shapes. */}
        {hi != null && hoverX != null && (
          <g>
            <line className={styles.crosshair} x1={hoverX} x2={hoverX} y1={PAD.t} y2={H - PAD.b}/>
            {withPoints.map((s) => {
              const p = s.points[hi]
              if (!p) return null
              return (
                <circle
                  key={`hover-${s.label}`}
                  cx={hoverX}
                  cy={yAt(p[1], max)}
                  r={4}
                  fill={s.color}
                  className={styles.hoverDot}
                />
              )
            })}
          </g>
        )}

        {n > 0 &&
          [0, 0.25, 0.5, 0.75, 1].map((frac) => {
            const idx = Math.round(frac * (n - 1))
            const label = longest[idx]?.[0]
            if (!label) return null
            return (
              <text
                key={frac}
                className={styles.axisLabel}
                x={xAt(idx, n)}
                y={H - 6}
                textAnchor={frac === 0 ? 'start' : frac === 1 ? 'end' : 'middle'}
              >
                {grain === 'day' ? istDate(label) : istTime(label)}
              </text>
            )
          })}

        {/* Transparent hit-target for hover, painted last so it sits above the visuals. */}
        <rect
          x={PAD.l}
          y={PAD.t}
          width={PLOT_W}
          height={PLOT_H}
          fill="transparent"
          onMouseMove={handleMove}
        />
      </svg>

      {hi != null && tooltipLeftPct != null && (
        <div className={styles.tooltip} style={{left: `${tooltipLeftPct}%`}}>
          <div className={styles.tooltipTime}>{istDateTime(longest[hi]?.[0])}</div>
          {withPoints.map((s) => (
            <div key={s.label} className={styles.tooltipRow}>
              <span className={styles.swatch} style={{background: s.color}}/>
              {s.label}: <b>{nf.format(s.points[hi]?.[1] ?? 0)}</b>
            </div>
          ))}
        </div>
      )}

      {series.length > 1 && (
        <div className={styles.legend}>
          {series.map((s) => (
            <span key={s.label} className={styles.legendItem}>
              <span className={styles.swatch} style={{background: s.color}}/>
              {s.label}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
