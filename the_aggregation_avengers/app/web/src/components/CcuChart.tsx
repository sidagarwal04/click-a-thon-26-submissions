// Minute-grain concurrency line chart.
//
// Hand-rolled SVG: no chart library, so nothing is loaded from a CDN and the
// mark specs are exact rather than whatever a library defaults to.
//
// Form choice: TREND OVER TIME -> line. Two series (sessions, users) means a
// legend is mandatory and both get direct labels, so identity never rests on
// colour alone. 2px strokes, recessive hairline grid, >=8px hover markers.
//
// Interaction is not optional on an SVG chart: a crosshair + tooltip ships by
// default, with the hit target spanning the full plot height rather than the
// 2px line itself.
//
// DRAG TO ZOOM, not double-click to zoom. A drag says WHICH window you want in
// one gesture; a double-click only says "here" and leaves the app to guess a
// span around it, which is guessing on the user's behalf. The gesture is also
// the one CloudWatch, Grafana and Datadog all use, so it needs no teaching.
// Double-click is bound to the inverse -- zoom out -- where having no argument
// is exactly right.
//
// The drag does NOT clip the chart client-side. It emits an absolute time range
// that the app applies as a filter, so the zoomed view is a smaller ClickHouse
// query rather than a crop of the same one: the stat tiles, breakdown and
// hourly panels all follow the selection, and the query-cost strip shows the
// read shrinking. Zooming is filtering here, not a viewport transform.

import { useEffect, useMemo, useRef, useState } from "react";
import type { SeriesPoint } from "../lib/api";
import { axisLabel, fmtInt, hhmm, stamp } from "../lib/api";

const PAD = { top: 16, right: 16, bottom: 28, left: 52 };

/** epoch ms -> "YYYY-MM-DD HH:MM:SS", the shape the label helpers expect. */
const fmtTs = (t: number) => new Date(t).toISOString().slice(0, 19).replace("T", " ");

interface Props {
  data: SeriesPoint[];
  showUsers: boolean;
  height?: number;
  /**
   * The requested window. The axis is drawn over THIS, not over whatever
   * happens to have data -- otherwise a range starting 15 Jul renders an axis
   * starting 21 Jul, and the picker looks like it did not apply.
   */
  domain?: { from?: string; to?: string };
  /** Emitted on drag-release. Both bounds are inclusive minutes from the data. */
  onBrush?: (from: string, to: string) => void;
  /** Double-click. Undoes a zoom; no-op when there is nothing to undo. */
  onResetZoom?: () => void;
  zoomed?: boolean;
}

/** A drag under this many minutes is a mis-click, not a selection. */
const MIN_BRUSH_MINUTES = 2;

/**
 * Nice round tick values covering [0, max].
 *
 * CCU is a count, so ticks must be whole numbers -- and the step must be at
 * least 1. Rounding a fractional step AFTER generating produces duplicates
 * (max = 2 gives 0, 0.5, 1, 1.5, 2 -> 0, 1, 1, 2, 2), which then collide as
 * React keys. Round the step up front and de-duplicate before returning.
 */
function ticks(max: number, count = 4): number[] {
  if (max <= 0) return [0];
  const raw = max / count;
  const mag = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
  const step = Math.max(
    1,
    Math.round([1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10),
  );
  const out: number[] = [];
  for (let v = 0; v <= max + step * 0.001; v += step) out.push(v);
  if (out[out.length - 1] < max) out.push(out[out.length - 1] + step);
  return [...new Set(out)];
}

export function CcuChart({ data, showUsers, height = 300, domain, onBrush, onResetZoom, zoomed }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  // Anchor and current index of an in-progress drag. `a` may be greater than
  // `b`: selecting right-to-left is legal and normalised at read time.
  const [rawHover, setHover] = useState<number | null>(null);
  const [drag, setDrag] = useState<{ a: number; b: number } | null>(null);

  // Hover and drag are INDEXES into `data`, so they stop meaning anything the
  // moment `data` changes -- and it changes on every zoom, filter and range
  // pick. A brush that cuts 361 minutes down to 51 leaves an index of ~300
  // pointing past the end of the array, and `data[hover].ccu` throws. Clamp on
  // read rather than trusting the setter: the array can shrink between a
  // mousemove and the render that consumes it.
  const hover = rawHover !== null && rawHover < data.length ? rawHover : null;

  // Track container width so the chart is responsive without a resize library.
  //
  // MUST be useEffect, not useMemo. useMemo runs DURING render, when
  // wrapRef.current is still null -- so the observer was never attached, width
  // stayed at its initial 900 forever, and the viewBox stayed "0 0 900 300"
  // while the element rendered up to 1646px wide. SVG then stretched the
  // 900-unit coordinate space to fill it, scaling every axis label and mark by
  // up to 1.8x. The chart looked oversized and misaligned with its card.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    setWidth(el.getBoundingClientRect().width); // seed before the first callback
    return () => ro.disconnect();
  }, []);

  // Clearing on identity change (not length) is deliberate: a new fetch of the
  // same length is still different data, and a crosshair left standing over it
  // would be pointing at the old minute's position.
  useEffect(() => {
    setHover(null);
    setDrag(null);
  }, [data]);

  const plotW = Math.max(320, width) - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;

  const max = useMemo(
    () => Math.max(1, ...data.map((d) => Math.max(d.ccu, showUsers ? d.user_ccu : 0))),
    [data, showUsers],
  );
  const yTicks = useMemo(() => ticks(max), [max]);
  const yMax = yTicks[yTicks.length - 1];

  // TIME-POSITIONED X AXIS, not index-positioned.
  //
  // The old `x = i / (n-1)` spaced points evenly by ORDER, which makes this an
  // ordinal axis wearing a time axis's clothes. gold is sparse -- 21 Jul has 9
  // populated minutes, 22 Jul has 168 -- so a day with almost no traffic got
  // the same width as a busy one, and the six days with no data at all simply
  // vanished rather than showing as a gap. Every distance along the axis was
  // meaningless.
  const ms = (t: string) => Date.parse(`${t.replace(" ", "T")}Z`);
  const times = useMemo(() => data.map((d) => ms(d.minute)), [data]);

  const tMin = domain?.from ? ms(domain.from) : times[0];
  // The API's `to` is exclusive and carries a spare minute; trim it so the axis
  // ends on the last minute the user asked for rather than one past it.
  const tMax = domain?.to ? ms(domain.to) - 60_000 : times[times.length - 1];
  const tSpan = Math.max(1, tMax - tMin);

  const xAt = (t: number) => ((t - tMin) / tSpan) * plotW;
  const x = (i: number) => xAt(times[i]);
  const y = (v: number) => plotH - (v / yMax) * plotH;

  // A run of missing minutes is a HOLE, and a line drawn straight across it
  // asserts traffic that was never measured. Break the path instead: start a
  // new subpath whenever the step jumps well past the normal sampling
  // interval, so the gap is visible as a gap.
  const step = useMemo(() => {
    if (times.length < 3) return 60_000;
    const deltas = times.slice(1).map((t, i) => t - times[i]).sort((a, b) => a - b);
    return Math.max(60_000, deltas[Math.floor(deltas.length / 2)]);
  }, [times]);
  const GAP = step * 4;

  const path = (key: "ccu" | "user_ccu") =>
    data
      .map((d, i) => {
        const brk = i === 0 || times[i] - times[i - 1] > GAP;
        return `${brk ? "M" : "L"}${x(i).toFixed(1)},${y(d[key]).toFixed(1)}`;
      })
      .join(" ");

  // Peak marker: the headline the tiles report, shown in place on the curve.
  const peakIdx = useMemo(
    () => data.reduce((best, d, i) => (d.ccu > data[best].ccu ? i : best), 0),
    [data],
  );

  /** Pixel position -> nearest data index, clamped to the plot. */
  const indexAt = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    // getBoundingClientRect is in CSS pixels but the SVG coordinate space is
    // viewBox units; they only coincide while width matches the viewBox. Scale
    // explicitly so the mapping survives any future fixed-width layout.
    const scale = (Math.max(320, width) || 1) / (rect.width || 1);
    const px = (e.clientX - rect.left) * scale - PAD.left;
    // Pixel -> TIME -> nearest sample. With a time-positioned axis the cursor
    // no longer maps linearly to an index, so hovering has to search: a
    // proportional guess would land on the wrong minute wherever data is
    // sparse, which is most of this dataset.
    const t = tMin + (px / plotW) * tSpan;
    let lo = 0;
    let hi = times.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (times[mid] < t) lo = mid + 1;
      else hi = mid;
    }
    if (lo > 0 && Math.abs(times[lo - 1] - t) <= Math.abs(times[lo] - t)) lo -= 1;
    return Math.max(0, Math.min(data.length - 1, lo));
  };

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!data.length) return;
    const i = indexAt(e);
    setHover(i);
    if (drag) setDrag((d) => (d ? { ...d, b: i } : null));
  };

  const onDown = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!data.length || !onBrush || e.button !== 0) return;
    e.preventDefault(); // suppress the browser's own text/image drag
    const i = indexAt(e);
    setDrag({ a: i, b: i });
  };

  const commit = () => {
    if (!drag) return;
    const [lo, hi] = drag.a <= drag.b ? [drag.a, drag.b] : [drag.b, drag.a];
    setDrag(null);
    if (hi - lo >= MIN_BRUSH_MINUTES) onBrush?.(data[lo].minute, data[hi].minute);
  };

  // A drag that ends outside the SVG -- past the card edge, or off the window
  // entirely -- never fires the element's mouseup. Without this the selection
  // band would stay painted and the next mousemove would keep extending it.
  useEffect(() => {
    if (!drag) return;
    const up = () => commit();
    window.addEventListener("mouseup", up);
    return () => window.removeEventListener("mouseup", up);
  });

  if (!data.length) {
    return (
      <div ref={wrapRef} style={{ height, display: "grid", placeItems: "center", color: "var(--text-muted)" }}>
        No data for these filters
      </div>
    );
  }

  const hp = hover !== null && !drag ? data[hover] : null;

  const bandLo = drag ? Math.min(drag.a, drag.b) : 0;
  const bandHi = drag ? Math.max(drag.a, drag.b) : 0;
  const band = drag ? { x0: x(bandLo), x1: x(bandHi) } : null;
  const bandMinutes = bandHi - bandLo + 1;
  const bandValid = bandHi - bandLo >= MIN_BRUSH_MINUTES;

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      {/* Legend is always present for >=2 series; the swatch carries identity
          next to text in normal ink, never coloured text. */}
      <div style={{ display: "flex", gap: 16, marginBottom: 8, fontSize: 12, color: "var(--text-secondary)" }}>
        <Key color="var(--series-1)" label="Sessions (streams open)" />
        {showUsers && <Key color="var(--series-2)" label="People (distinct users)" />}
        {onBrush && (
          <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-muted)" }}>
            {zoomed ? "Drag to zoom · double-click to zoom out" : "Drag across the chart to zoom"}
          </span>
        )}
      </div>

      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${Math.max(320, width)} ${height}`}
        onMouseMove={onMove}
        onMouseDown={onDown}
        onMouseUp={commit}
        onDoubleClick={() => zoomed && onResetZoom?.()}
        onMouseLeave={() => setHover(null)}
        style={{ display: "block", cursor: drag ? "ew-resize" : "crosshair", userSelect: "none" }}
        role="img"
        aria-label={`Concurrency over time. Peak ${fmtInt(data[peakIdx].ccu)} at ${data[peakIdx].minute}.`}
      >
        <g transform={`translate(${PAD.left},${PAD.top})`}>
          {/* Recessive hairline grid + axis labels in muted ink. */}
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={0} x2={plotW} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth={1} />
              <text
                x={-8}
                y={y(t)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={11}
                fill="var(--text-muted)"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {fmtInt(t)}
              </text>
            </g>
          ))}
          <line x1={0} x2={plotW} y1={plotH} y2={plotH} stroke="var(--axis)" strokeWidth={1} />

          {/* Time axis: labels come from the REQUESTED window, at fixed
              positions along it -- not from whichever samples happen to exist.
              Labelling by data made an axis that started six days after the
              range did, which read as the picker having been ignored.
              They must also know the span: over eleven days "12:36" is a time
              of day that could belong to any of them. */}
          {[0, 0.5, 1].map((f) => (
            <text
              key={f}
              x={f * plotW}
              y={plotH + 18}
              textAnchor={f === 0 ? "start" : f === 1 ? "end" : "middle"}
              fontSize={11}
              fill="var(--text-muted)"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {axisLabel(fmtTs(tMin + f * tSpan), tSpan)}
            </text>
          ))}

          {/* Selection band. Painted BEFORE the series so the lines stay on
              top -- you are choosing a window by looking at the curve, so the
              curve must not be dimmed by the thing you are choosing with.
              Neutral wash, not a series colour: this is chrome, not data. */}
          {band && (
            <g>
              <rect
                x={band.x0}
                y={0}
                width={Math.max(band.x1 - band.x0, 1)}
                height={plotH}
                fill="var(--text-primary)"
                opacity={0.1}
              />
              {[band.x0, band.x1].map((bx, i) => (
                <line key={i} x1={bx} x2={bx} y1={0} y2={plotH} stroke="var(--axis)" strokeWidth={1} />
              ))}
            </g>
          )}

          {showUsers && (
            <path d={path("user_ccu")} fill="none" stroke="var(--series-2)" strokeWidth={2} strokeLinejoin="round" />
          )}
          <path d={path("ccu")} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" />

          {/* Peak marker -- a 2px surface ring so it reads over the line. */}
          <circle
            cx={x(peakIdx)}
            cy={y(data[peakIdx].ccu)}
            r={5}
            fill="var(--series-1)"
            stroke="var(--surface-1)"
            strokeWidth={2}
          />

          {hover !== null && !drag && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={0} y2={plotH} stroke="var(--axis)" strokeWidth={1} />
              {showUsers && (
                <circle cx={x(hover)} cy={y(data[hover].user_ccu)} r={4.5} fill="var(--series-2)" stroke="var(--surface-1)" strokeWidth={2} />
              )}
              <circle cx={x(hover)} cy={y(data[hover].ccu)} r={4.5} fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth={2} />
            </g>
          )}
        </g>
      </svg>

      {/* While dragging, the tooltip's slot shows what the release will do.
          Saying "18 minutes -- release to zoom" up front is what stops the
          gesture from being a guess. Below the threshold it says so instead of
          silently doing nothing on release. */}
      {drag && (
        <div
          className="card"
          style={{
            position: "absolute",
            top: 24,
            left: Math.min(Math.max(0, PAD.left + (band!.x0 + band!.x1) / 2 - 80), Math.max(320, width) - 180),
            padding: "7px 10px",
            fontSize: 12,
            pointerEvents: "none",
            minWidth: 160,
            textAlign: "center",
          }}
        >
          <div style={{ fontVariantNumeric: "tabular-nums" }}>
            {hhmm(data[bandLo].minute)} &ndash; {hhmm(data[bandHi].minute)}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
            {bandValid ? `${bandMinutes} min · release to zoom` : "drag further to select"}
          </div>
        </div>
      )}

      {hp && (
        <div
          className="card"
          style={{
            position: "absolute",
            top: 24,
            left: Math.min(Math.max(0, PAD.left + x(hover!) - 70), Math.max(320, width) - 170),
            padding: "8px 10px",
            fontSize: 12,
            pointerEvents: "none",
            minWidth: 150,
          }}
        >
          <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>{stamp(hp.minute)}</div>
          <Row color="var(--series-1)" label="Sessions" value={hp.ccu} />
          {showUsers && <Row color="var(--series-2)" label="People" value={hp.user_ccu} />}
        </div>
      )}
    </div>
  );
}

function Key({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 12, height: 2, background: color, borderRadius: 1 }} />
      {label}
    </span>
  );
}

function Row({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "space-between" }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--text-secondary)" }}>
        <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
        {label}
      </span>
      <strong style={{ fontVariantNumeric: "tabular-nums" }}>{fmtInt(value)}</strong>
    </div>
  );
}
