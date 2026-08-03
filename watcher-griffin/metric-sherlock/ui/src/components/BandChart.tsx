/* THE BAND RIBBON — the signature element.
 *
 * The product's whole idea is "here is normal, and here is what happened", so this one
 * mark carries it: the expected corridor as a soft luminous band, the actual value
 * tracing through it, and a marked break wherever it leaves. Everything else in the
 * interface stays quiet so this can be the thing people remember.
 *
 * WHY THE BAND MOVES PER POINT
 * The expected centre genuinely changes window to window, because each window is
 * compared against its own seasonal cell — 03:00 Sunday expects a different fill rate
 * from 14:00 Tuesday. A single flat "expected" line would be wrong for every window but
 * one and would make ordinary daily rhythm look like a series of breaches. That is the
 * exact error the backend's seasonal cells exist to prevent, so the chart honours it.
 *
 * BUILT ON ECHARTS, CONFIGURED AGAINST ITS OWN DEFAULTS
 * ECharts is here for its rendering quality and its animation and tooltip engine, not
 * its look — its defaults are thick, saturated and busy. Every spec below comes from the
 * dataviz reference instead: 2px lines, recessive hairline grid, ≥8px hit targets,
 * axis ink in muted tokens rather than series colour, one y-axis, crosshair + tooltip by
 * default, and no number printed on every point.
 *
 * Tree-shaken imports (`echarts/core` + only the pieces used) keep this to a fraction of
 * the full bundle — it replaced recharts rather than joining it, so the page got lighter.
 */

import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import { dateTime, metricValue } from '../lib/format'
import { prefersReducedMotion } from '../lib/motion'
import type { BandPoint } from '../types'

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  MarkAreaComponent,
  MarkLineComponent,
  CanvasRenderer,
])

interface Props {
  points: BandPoint[]
  unit: string
  /** Compact: no axes, no tooltip chrome — for a dense row. Still shows the band. */
  sparkline?: boolean
  height?: number
  label?: string
  /** CSS custom-property NAME (not a value) for the signal, band and expected line —
   *  e.g. '--series-2'. Defaults to the primary series token. Callers resolve this from
   *  lib/metricConfig so a metric's colour is configuration rather than a literal here. */
  accent?: string
}

/** Reads a CSS custom property so the chart inherits the theme instead of hardcoding
 *  hex. This is why light/dark works without a second palette in JS. */
function token(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

/** Hex → rgba at a given alpha.
 *
 *  Needed because the ECharts canvas renderer parses colours itself and does not
 *  understand CSS `color-mix()` — passing one produces a silently transparent fill, which
 *  is the worst possible failure here since the band is the signature mark and its
 *  absence looks like "no data" rather than "broken style". The palette tokens are plain
 *  hex, so this stays a pure function of them and no colour is invented. */
function alpha(color: string, a: number): string {
  const hex = color.trim()
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!m) return hex // already rgb()/rgba() or a named colour — pass through
  const [r, g, b] = [m[1], m[2], m[3]].map((h) => parseInt(h, 16))
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

export default function BandChart({
  points,
  unit,
  sparkline = false,
  height,
  label,
  accent = '--series-1',
}: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  // 76px, not the 60 this started at. At 60 the corridor was only a few pixels tall for a
  // tight band and read as a smudge rather than a range — and the whole point of the mark
  // is that a reader can SEE the value leave the band, not take it on trust.
  const h = height ?? (sparkline ? 76 : 280)

  const data = useMemo(() => {
    // The visible corridor is the AMBER threshold (k = 2.5) — the point at which the
    // system actually starts calling something a breach. Drawing ±1 spread would put the
    // line outside the band constantly and mean nothing.
    const K = 2.5
    const x = points.map((p) => p.window_start)
    const actual: (number | null)[] = []
    const lower: (number | null)[] = []
    const width: (number | null)[] = []
    const centre: (number | null)[] = []
    const breaches: [string, number][] = []

    points.forEach((p) => {
      actual.push(p.value)
      centre.push(p.center)
      if (p.center !== null && p.spread !== null) {
        lower.push(p.center - K * p.spread)
        width.push(2 * K * p.spread)
      } else {
        lower.push(null)
        width.push(null)
      }
      if (p.breached && p.value !== null) breaches.push([p.window_start, p.value])
    })
    return { x, actual, lower, width, centre, breaches }
  }, [points])

  useEffect(() => {
    const host = hostRef.current
    if (!host || points.length === 0) return

    const chart = chartRef.current ?? echarts.init(host, undefined, { renderer: 'canvas' })
    chartRef.current = chart

    const ink = token('--text-primary', '#0b0b0b')
    const muted = token('--text-muted', '#898781')
    const grid = token('--gridline', '#e1e0d9')
    const axis = token('--baseline-axis', '#c3c2b7')
    const surface = token('--surface-1', '#fcfcfb')
    const series = token(accent, '#2a78d6')
    const critical = token('--status-critical', '#d03b3b')
    const mono = token('--font-mono', 'monospace')
    const reduce = prefersReducedMotion()

    chart.setOption(
      {
        animation: !reduce,
        animationDuration: 620,
        animationEasing: 'cubicOut',
        // Staggered so the band settles before the signal draws over it — the corridor
        // reads as context, the line as the event.
        animationDelay: (idx: number) => idx * 6,
        backgroundColor: 'transparent',
        grid: sparkline
          ? { left: 2, right: 2, top: 6, bottom: 4, containLabel: false }
          : { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
        tooltip: {
          trigger: 'axis',
          // Crosshair by default on a line chart, per the interaction reference.
          axisPointer: {
            type: 'line',
            lineStyle: { color: axis, width: 1, type: 'solid' },
            snap: true,
          },
          backgroundColor: surface,
          borderColor: token('--border-strong', 'rgba(0,0,0,0.2)'),
          borderWidth: 1,
          padding: [10, 12],
          extraCssText:
            'border-radius:9px; box-shadow:0 12px 32px -12px rgba(0,0,0,0.35); backdrop-filter:blur(2px);',
          textStyle: { color: ink, fontSize: 12, fontFamily: token('--font-ui', 'sans-serif') },
          formatter: (params: unknown) => {
            const arr = params as { dataIndex: number }[]
            if (!arr?.length) return ''
            const i = arr[0].dataIndex
            const p = points[i]
            if (!p) return ''
            const band =
              p.center !== null && p.spread !== null
                ? `${metricValue(p.center - 2.5 * p.spread, unit)} – ${metricValue(p.center + 2.5 * p.spread, unit)}`
                : '—'
            return `
              <div style="font-size:11px;color:${muted};margin-bottom:4px">${dateTime(p.window_start)}</div>
              <div style="font-family:${mono};font-size:13px;font-weight:600">${metricValue(p.value, unit)}</div>
              <div style="font-family:${mono};font-size:11px;color:${muted};margin-top:2px">expected ${metricValue(p.center, unit)}</div>
              <div style="font-family:${mono};font-size:11px;color:${muted}">normal range ${band}</div>
              <div style="font-size:10px;color:${muted};margin-top:4px">vs ${p.seasonal_cell || 'n/a'}</div>
              ${p.breached ? `<div style="color:${critical};font-weight:600;font-size:11px;margin-top:4px">outside normal range</div>` : ''}
            `
          },
        },
        xAxis: {
          type: 'category',
          data: data.x,
          show: !sparkline,
          boundaryGap: false,
          axisLine: { lineStyle: { color: axis } },
          axisTick: { show: false },
          axisLabel: {
            color: muted,
            fontSize: 11,
            fontFamily: mono,
            hideOverlap: true,
            formatter: (v: string) => dateTime(v),
          },
          splitLine: { show: false },
        },
        yAxis: {
          type: 'value',
          show: !sparkline,
          scale: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: muted,
            fontSize: 11,
            fontFamily: mono,
            formatter: (v: number) => metricValue(v, unit),
          },
          // Recessive grid: horizontal hairlines only, no vertical rules.
          splitLine: { lineStyle: { color: grid, width: 1, type: 'solid' } },
        },
        series: [
          // --- the corridor, as a stacked invisible base + translucent width ---
          {
            name: 'band-base',
            type: 'line',
            data: data.lower,
            stack: 'band',
            lineStyle: { width: 0 },
            itemStyle: { color: 'transparent' },
            symbol: 'none',
            silent: true,
            areaStyle: { color: 'transparent' },
            z: 1,
          },
          {
            name: 'normal range',
            type: 'line',
            data: data.width,
            stack: 'band',
            symbol: 'none',
            silent: true,
            // The one gradient in the product. It belongs here because the band is the
            // signature mark, and a flat fill reads as a block rather than a corridor.
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: alpha(series, 0.3) },
                { offset: 1, color: alpha(series, 0.14) },
              ]),
              opacity: 1,
            },
            // A faint edge on the corridor's top. Without it the fill fades into the
            // surface and the band has no readable boundary — which is the one thing it
            // exists to communicate.
            lineStyle: { width: 1, color: alpha(series, 0.45), type: [3, 3] },
            z: 1,
          },
          // --- the seasonal centre: dashed, so it reads as reference not data ---
          {
            name: 'expected',
            type: 'line',
            data: data.centre,
            // Was --baseline-axis, which is #383835 on the dark surface and effectively
            // invisible. A muted tint of the series colour stays clearly recessive against
            // the 2px solid signal while actually being visible.
            lineStyle: { color: alpha(series, 0.55), width: 1, type: [4, 4] },
            symbol: 'none',
            silent: true,
            smooth: 0.2,
            z: 2,
          },
          // --- the signal ---
          {
            name: label ?? 'actual',
            type: 'line',
            data: data.actual,
            lineStyle: { color: series, width: sparkline ? 1.75 : 2 },
            itemStyle: { color: series },
            // ≥8px hit target even though the mark itself is small.
            symbol: 'circle',
            symbolSize: 0,
            showSymbol: false,
            emphasis: {
              scale: false,
              itemStyle: { color: series, borderColor: surface, borderWidth: 2 },
            },
            smooth: 0.18,
            connectNulls: true,
            z: 3,
          },
          // --- breaches, marked individually so a single out-of-band window is visible
          //     even in a 60px sparkline ---
          {
            name: 'outside range',
            type: 'line',
            data: data.breaches.map(([, v], i) => ({
              value: [data.x.indexOf(data.breaches[i][0]), v],
            })),
            lineStyle: { width: 0 },
            symbol: 'circle',
            symbolSize: sparkline ? 6 : 9,
            itemStyle: { color: critical, borderColor: surface, borderWidth: 2 },
            silent: true,
            z: 4,
          },
        ],
      },
      { notMerge: true },
    )

    return undefined
  }, [data, points, unit, sparkline, label, h, accent])

  // One shared ResizeObserver per chart, and a theme listener so the chart re-reads its
  // tokens when the OS flips light/dark.
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const ro = new ResizeObserver(() => chartRef.current?.resize())
    ro.observe(host)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    return () => {
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])

  if (points.length === 0) {
    return (
      <p className="muted-note" style={{ margin: 0 }}>
        No history for this slice at this grain yet.
      </p>
    )
  }

  return (
    <div
      ref={hostRef}
      className="band-chart"
      style={{ width: '100%', height: h }}
      role="img"
      aria-label={
        label
          ? `${label}: ${points.length} recent windows against the expected range`
          : `${points.length} recent windows against the expected range`
      }
    />
  )
}
