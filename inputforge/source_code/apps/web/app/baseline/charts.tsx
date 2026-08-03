"use client";

import { useState, type PointerEvent } from "react";
import { formatMetric, formatUtc, metricLabel } from "./format";
import { ALARM, INK, PANEL, RULE } from "./theme";
import type { ChartPoint, MetricKey } from "./types";

interface HoverState {
  index: number;
  left: number;
  top: number;
}

function pathFor(
  vals: number[],
  w: number,
  h: number,
  min: number,
  max: number,
  left = 0,
  top = 0,
): string {
  if (!vals.length) return "";
  return vals
    .map(
      (value, index) =>
        `${index ? "L" : "M"}${(left +
          (index / Math.max(vals.length - 1, 1)) * w).toFixed(1)},${(
          top +
          h -
          ((value - min) / (max - min || 1)) * h
        ).toFixed(1)}`,
    )
    .join(" ");
}

function hoverFromPointer(
  event: PointerEvent<SVGSVGElement>,
  pointCount: number,
  plot?: { left: number; width: number; viewWidth: number },
): HoverState {
  const bounds = event.currentTarget.getBoundingClientRect();
  const position = Math.max(0, Math.min(bounds.width, event.clientX - bounds.left));
  const x = (position / Math.max(bounds.width, 1)) * (plot?.viewWidth ?? bounds.width);
  const relativeX = plot
    ? Math.max(0, Math.min(plot.width, x - plot.left))
    : position;
  return {
    index: Math.round(
      (relativeX / Math.max(plot?.width ?? bounds.width, 1)) *
        Math.max(pointCount - 1, 0),
    ),
    left: Math.min(event.clientX + 14, window.innerWidth - 224),
    top: Math.max(8, event.clientY - 104),
  };
}

function formatAxisTime(value: string): string {
  const formatted = new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    hourCycle: "h23",
  }).format(new Date(value));
  return `${formatted} UTC`;
}

function HoverTooltip({ point, metric, left, top, compact = false }: { point: ChartPoint; metric: MetricKey; left: number; top: number; compact?: boolean }) {
  return (
    <div role="tooltip" style={{ position: "fixed", left, top, zIndex: 100, width: 196, pointerEvents: "none", border: `1px solid ${RULE}`, borderRadius: 7, background: PANEL, padding: compact ? "8px 10px" : "10px 12px", boxShadow: "0 8px 24px rgba(23,22,18,0.14)", color: INK }}>
      <div style={{ fontFamily: "var(--font-ibm-plex-mono), monospace", fontSize: 9.5, letterSpacing: "0.06em", color: "#8A857A", marginBottom: 6 }}>{formatUtc(point.time)}</div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 12.5, lineHeight: 1.45 }}>
        <span>{metricLabel(metric)}</span>
        <strong style={{ fontFamily: "var(--font-ibm-plex-mono), monospace", fontWeight: 500 }}>{formatMetric(metric, point.actual)}</strong>
      </div>
      {!compact && point.expected != null && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 11.5, lineHeight: 1.5, color: "#6B675C", marginTop: 3 }}>
          <span>Seasonal baseline</span>
          <span style={{ fontFamily: "var(--font-ibm-plex-mono), monospace" }}>{formatMetric(metric, point.expected)}</span>
        </div>
      )}
      {point.anomalous && <div style={{ marginTop: 6, fontFamily: "var(--font-ibm-plex-mono), monospace", fontSize: 9.5, letterSpacing: "0.07em", textTransform: "uppercase", color: ALARM }}>Detector flagged this hour</div>}
    </div>
  );
}

export function Spark({ series, metric, width, height, color }: { series: ChartPoint[]; metric: MetricKey; width: number; height: number; color: string }) {
  const [hover, setHover] = useState<HoverState | null>(null);
  const values = series.map((point) => point.actual);
  if (!values.length) return <div style={{ height }} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.2 || Math.abs(max) * 0.05 || 1;
  const chartMin = min - pad;
  const chartMax = max + pad;
  const chartHeight = height - 2;
  const d = pathFor(values, width, chartHeight, chartMin, chartMax);
  const anomalyIndexes = series
    .map((point, index) => (point.anomalous ? index : -1))
    .filter((index) => index >= 0);
  const anomalyStart = anomalyIndexes.at(0);
  const anomalyEnd = anomalyIndexes.at(-1);
  const hoverPoint = hover == null ? null : series[hover.index] ?? null;
  const hoverX = hover == null ? null : (hover.index / Math.max(values.length - 1, 1)) * width;
  const hoverY = hoverPoint == null ? null : chartHeight - ((hoverPoint.actual - chartMin) / (chartMax - chartMin || 1)) * chartHeight;

  return (
    <>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        aria-label={`${metricLabel(metric)} hourly chart. Hover for values.`}
        style={{ display: "block", cursor: "crosshair" }}
        onPointerMove={(event) => setHover(hoverFromPointer(event, series.length))}
        onPointerLeave={() => setHover(null)}
      >
        {anomalyStart != null && anomalyEnd != null && (
          <rect
            x={(anomalyStart / Math.max(values.length - 1, 1)) * width}
            y={0}
            width={Math.max(
              ((anomalyEnd - anomalyStart) /
                Math.max(values.length - 1, 1)) *
                width,
              2,
            )}
            height={height}
            fill={color}
            opacity={0.09}
          />
        )}
        <path d={d} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" />
        {hoverX != null && hoverY != null && (
          <>
            <line x1={hoverX} x2={hoverX} y1={0} y2={height} stroke={color} strokeWidth={1} opacity={0.35} />
            <circle cx={hoverX} cy={hoverY} r={3.2} fill={PANEL} stroke={color} strokeWidth={1.8} vectorEffect="non-scaling-stroke" />
          </>
        )}
      </svg>
      {hover && hoverPoint && <HoverTooltip point={hoverPoint} metric={metric} left={hover.left} top={hover.top} compact />}
    </>
  );
}

export function BigChart({ series, metric, accent, width = 760 }: { series: ChartPoint[]; metric: MetricKey; accent: string; width?: number }) {
  const [hover, setHover] = useState<HoverState | null>(null);
  const H = 286;
  const PLOT_LEFT = 66;
  const PLOT_RIGHT = 10;
  const PLOT_TOP = 10;
  const PLOT_BOTTOM = 32;
  const plotWidth = width - PLOT_LEFT - PLOT_RIGHT;
  const plotHeight = H - PLOT_TOP - PLOT_BOTTOM;
  if (!series.length) return <div style={{ height: H, display: "grid", placeItems: "center", color: "#8A857A", fontSize: 13 }}>No hourly series available for this window.</div>;
  const actual = series.map((point) => point.actual);
  const expected = series.map((point) => point.expected ?? point.actual);
  const high = series.map((point) => point.upper ?? point.expected ?? point.actual);
  const low = series.map((point) => point.lower ?? point.expected ?? point.actual);
  const min = Math.min(...actual, ...low);
  const max = Math.max(...actual, ...high);
  const pad = (max - min) * 0.08 || Math.abs(max) * 0.05 || 1;
  const chartMin = min - pad;
  const chartMax = max + pad;
  const y = (value: number) => PLOT_TOP + plotHeight - ((value - chartMin) / (chartMax - chartMin || 1)) * plotHeight;
  const n = series.length;
  const x = (index: number) => PLOT_LEFT + (index / Math.max(n - 1, 1)) * plotWidth;
  const area = high.map((value, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ") + " " + low.slice().reverse().map((value, index) => `L${x(n - 1 - index).toFixed(1)},${y(value).toFixed(1)}`).join(" ") + " Z";
  const anomalyIndexes = series.map((point, index) => point.anomalous ? index : -1).filter((index) => index >= 0);
  const anomalyStart = anomalyIndexes.at(0);
  const anomalyEnd = anomalyIndexes.at(-1);
  const hoverPoint = hover == null ? null : series[hover.index] ?? null;
  const yTicks = [0, 1, 2, 3, 4].map((index) => {
    const value = chartMax - (index / 4) * (chartMax - chartMin);
    return { value, y: y(value) };
  });
  const xTickIndexes = Array.from(
    new Set([0, Math.round((n - 1) / 4), Math.round((n - 1) / 2), Math.round(((n - 1) * 3) / 4), n - 1]),
  );

  return (
    <>
      <svg
        width="100%"
        height={H}
        viewBox={`0 0 ${width} ${H}`}
        preserveAspectRatio="none"
        aria-label={`${metricLabel(metric)} hourly chart. Hover for actual and baseline values.`}
        style={{ display: "block", marginTop: 10, cursor: "crosshair" }}
        onPointerMove={(event) =>
          setHover(
            hoverFromPointer(event, series.length, {
              left: PLOT_LEFT,
              width: plotWidth,
              viewWidth: width,
            }),
          )
        }
        onPointerLeave={() => setHover(null)}
      >
        {yTicks.map((tick) => (
          <g key={tick.y}>
            <line x1={PLOT_LEFT} x2={width - PLOT_RIGHT} y1={tick.y} y2={tick.y} stroke="#EFEADF" strokeWidth={1} />
            <text x={PLOT_LEFT - 9} y={tick.y + 3.5} textAnchor="end" fill="#8A857A" fontFamily="var(--font-ibm-plex-mono), monospace" fontSize="10">
              {formatMetric(metric, tick.value)}
            </text>
          </g>
        ))}
        <line x1={PLOT_LEFT} x2={PLOT_LEFT} y1={PLOT_TOP} y2={PLOT_TOP + plotHeight} stroke="#D7D0C3" strokeWidth={1} />
        <line x1={PLOT_LEFT} x2={width - PLOT_RIGHT} y1={PLOT_TOP + plotHeight} y2={PLOT_TOP + plotHeight} stroke="#D7D0C3" strokeWidth={1} />
        {xTickIndexes.map((index) => (
          <g key={index}>
            <line x1={x(index)} x2={x(index)} y1={PLOT_TOP + plotHeight} y2={PLOT_TOP + plotHeight + 4} stroke="#D7D0C3" strokeWidth={1} />
            <text x={x(index)} y={H - 10} textAnchor={index === 0 ? "start" : index === n - 1 ? "end" : "middle"} fill="#8A857A" fontFamily="var(--font-ibm-plex-mono), monospace" fontSize="10">
              {formatAxisTime(series[index]!.time)}
            </text>
          </g>
        ))}
        {anomalyStart != null && anomalyEnd != null && (
          <>
            <rect x={x(anomalyStart)} y={PLOT_TOP} width={Math.max(x(anomalyEnd) - x(anomalyStart), 3)} height={plotHeight} fill={ALARM} opacity={0.07} />
            <line x1={x(anomalyStart)} x2={x(anomalyStart)} y1={PLOT_TOP} y2={PLOT_TOP + plotHeight} stroke={ALARM} strokeWidth={1} strokeDasharray="4 3" />
          </>
        )}
        <path d={area} fill="#DCE7E4" opacity={0.8} />
        <path d={pathFor(expected, plotWidth, plotHeight, chartMin, chartMax, PLOT_LEFT, PLOT_TOP)} fill="none" stroke={accent} strokeWidth={1.2} strokeDasharray="3 3" opacity={0.7} />
        <path d={pathFor(actual, plotWidth, plotHeight, chartMin, chartMax, PLOT_LEFT, PLOT_TOP)} fill="none" stroke={INK} strokeWidth={2} strokeLinejoin="round" />
        {hover && hoverPoint && (
          <>
            <line x1={x(hover.index)} x2={x(hover.index)} y1={PLOT_TOP} y2={PLOT_TOP + plotHeight} stroke={INK} strokeWidth={1} opacity={0.25} />
            {hoverPoint.expected != null && <circle cx={x(hover.index)} cy={y(hoverPoint.expected)} r={4} fill={PANEL} stroke={accent} strokeWidth={1.8} vectorEffect="non-scaling-stroke" />}
            <circle cx={x(hover.index)} cy={y(hoverPoint.actual)} r={4.5} fill={PANEL} stroke={INK} strokeWidth={2} vectorEffect="non-scaling-stroke" />
          </>
        )}
      </svg>
      {hover && hoverPoint && <HoverTooltip point={hoverPoint} metric={metric} left={hover.left} top={hover.top} />}
    </>
  );
}
