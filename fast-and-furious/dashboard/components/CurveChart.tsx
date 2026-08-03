"use client";

import type { CurvePoint } from "@/lib/types";

/**
 * The live activity curve.
 *
 * Hand-authored SVG rather than a charting library: one series, no interaction
 * beyond a hover readout, and pulling in a chart package for that would be more
 * bytes than the whole app. It also keeps the static export dependency-free.
 *
 * Deliberate choices, per the same rules the rest of the app follows:
 *  - an area fill under the line, so the shape reads at a glance rather than
 *    needing the eye to trace a 1px stroke;
 *  - a faint horizontal grid, because the question asked of this chart is "how
 *    high" and an unlabelled line cannot answer it;
 *  - the final point emphasised, since "what is it now" is the live question.
 */
export function CurveChart({
  points,
  height = 200,
}: {
  points: CurvePoint[];
  height?: number;
}) {
  const W = 800;
  const H = height;
  const padL = 34;
  const padR = 6;
  const padT = 10;
  const padB = 18;

  if (points.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded border border-line-soft bg-sunken font-mono text-xs text-ink-3"
        style={{ height }}
      >
        no traffic in the window yet
      </div>
    );
  }

  const max = Math.max(1, ...points.map((p) => p.sessions));
  // Round the ceiling up to something a human reads as a round number, so the
  // top gridline is 500 rather than 487.
  const niceMax = niceCeiling(max);

  const x = (i: number) =>
    points.length === 1
      ? padL + (W - padL - padR) / 2
      : padL + (i * (W - padL - padR)) / (points.length - 1);
  const y = (v: number) => H - padB - (v / niceMax) * (H - padT - padB);

  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.sessions).toFixed(1)}`)
    .join("");
  const area = `${line}L${x(points.length - 1).toFixed(1)},${H - padB}L${x(0).toFixed(1)},${H - padB}Z`;

  const gridValues = [0, niceMax / 2, niceMax];
  const last = points[points.length - 1];

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="block h-auto w-full"
        role="img"
        aria-label={`Sessions active per minute. Latest ${last.sessions}, peak ${max}.`}
      >
        {gridValues.map((v) => (
          <g key={v}>
            <line
              x1={padL}
              x2={W - padR}
              y1={y(v)}
              y2={y(v)}
              stroke="var(--color-line-soft)"
              strokeWidth="1"
            />
            <text
              x={padL - 6}
              y={y(v) + 3.5}
              textAnchor="end"
              fill="var(--color-ink-3)"
              fontSize="10"
              fontFamily="var(--font-mono)"
            >
              {v === 0 ? "0" : compact(v)}
            </text>
          </g>
        ))}

        <path d={area} fill="var(--color-accent)" opacity="0.14" />
        <path
          d={line}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* The live value, emphasised. */}
        <circle
          cx={x(points.length - 1)}
          cy={y(last.sessions)}
          r="3"
          fill="var(--color-accent)"
        />

        <line
          x1={padL}
          x2={W - padR}
          y1={H - padB}
          y2={H - padB}
          stroke="var(--color-line)"
          strokeWidth="1"
        />
        <text
          x={padL}
          y={H - 5}
          fill="var(--color-ink-3)"
          fontSize="10"
          fontFamily="var(--font-mono)"
        >
          {points[0].minute.slice(11, 16)}
        </text>
        <text
          x={W - padR}
          y={H - 5}
          textAnchor="end"
          fill="var(--color-ink-3)"
          fontSize="10"
          fontFamily="var(--font-mono)"
        >
          {last.minute.slice(11, 16)} UTC
        </text>
      </svg>
    </div>
  );
}

function niceCeiling(v: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(v));
  const stepped = Math.ceil(v / magnitude) * magnitude;
  return stepped === v ? stepped : stepped;
}

function compact(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}k` : String(v);
}
