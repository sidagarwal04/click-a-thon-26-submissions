"use client";

import type { FleetCurvePoint } from "@/lib/types";

/**
 * Fleet truth against the pipeline's answer, overlaid.
 *
 * The two lines come from independent inputs. The solid one is what the fleet
 * recorded at the moment of each transition — it did not infer activity, it decided
 * it. The dashed one is what ClickHouse infers from the events the fleet wrote,
 * using the same five-term predicate the served pipeline uses.
 *
 * So agreement is evidence and disagreement is a defect: either the pipeline is
 * wrong, events were lost, or reordering broke something. That is the entire point
 * of the chart, which is why the gap is rendered as a number and not left for the
 * eye to estimate.
 *
 * The two series are told apart by FORM, not hue: gold and solid for the fleet,
 * white and dashed for the pipeline. This surface runs one signal colour, so a
 * second accent would have been invented rather than measured — and gold-over-
 * white is SonyLIV's own hierarchy, which makes the borrowed pair honest.
 *
 * Hand-authored SVG for the same reason CurveChart is: two series and a hover
 * readout do not justify a charting dependency in a static export.
 */
export function DualCurveChart({
  generator,
  clickhouse,
  height = 260,
}: {
  generator: FleetCurvePoint[];
  clickhouse: FleetCurvePoint[];
  height?: number;
}) {
  const W = 800;
  const H = height;
  const padL = 38;
  const padR = 8;
  const padT = 12;
  const padB = 30;

  if (generator.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded border border-line-soft bg-sunken font-mono text-xs text-ink-3"
        style={{ height }}
      >
        no sessions in the window yet
      </div>
    );
  }

  // The generator series is dense over the whole window, so it defines the x axis.
  // ClickHouse is looked up by minute and may legitimately be missing points — a
  // minute with no matching events produces no row rather than a zero.
  const chByMinute = new Map(clickhouse.map((p) => [p.minute, p.sessions]));

  const max = Math.max(
    1,
    ...generator.map((p) => p.sessions),
    ...clickhouse.map((p) => p.sessions),
  );
  const niceMax = niceCeiling(max);

  const x = (i: number) =>
    generator.length === 1
      ? padL + (W - padL - padR) / 2
      : padL + (i * (W - padL - padR)) / (generator.length - 1);
  const y = (v: number) => H - padB - (v / niceMax) * (H - padT - padB);

  const genLine = generator
    .map(
      (p, i) =>
        `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.sessions).toFixed(1)}`,
    )
    .join("");
  const genArea = `${genLine}L${x(generator.length - 1).toFixed(1)},${H - padB}L${x(0).toFixed(1)},${H - padB}Z`;

  // Break the ClickHouse path at missing minutes instead of bridging them. A
  // straight line across a gap would read as a measured value that was never
  // measured.
  const chSegments: string[] = [];
  let current: string[] = [];
  generator.forEach((p, i) => {
    const v = chByMinute.get(p.minute);
    if (v === undefined) {
      if (current.length > 1) chSegments.push(current.join(""));
      current = [];
      return;
    }
    current.push(`${current.length === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  });
  if (current.length > 1) chSegments.push(current.join(""));

  const gridValues = [0, niceMax / 2, niceMax];
  const last = generator[generator.length - 1];
  const lastCH = chByMinute.get(last.minute);

  return (
    <div>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="block h-auto w-full"
          role="img"
          aria-label={`Active sessions per minute. Fleet ${last.sessions}, pipeline ${lastCH ?? "no data"}, peak ${max}.`}
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

          <path d={genArea} fill="var(--color-accent)" opacity="0.1" />
          <path
            d={genLine}
            fill="none"
            stroke="var(--color-accent)"
            strokeWidth="1.75"
            strokeLinejoin="round"
          />

          {chSegments.map((d, i) => (
            <path
              key={i}
              d={d}
              fill="none"
              stroke="var(--color-ink)"
              strokeWidth="1.5"
              strokeDasharray="5 3"
              opacity="0.85"
              strokeLinejoin="round"
            />
          ))}

          <circle
            cx={x(generator.length - 1)}
            cy={y(last.sessions)}
            r="3"
            fill="var(--color-accent)"
          />
          {lastCH !== undefined && (
            <circle
              cx={x(generator.length - 1)}
              cy={y(lastCH)}
              r="3"
              fill="var(--color-ink)"
            />
          )}

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
            y={H - 16}
            fill="var(--color-ink-3)"
            fontSize="10"
            fontFamily="var(--font-mono)"
          >
            {generator[0].minute.slice(11, 16)}
          </text>
          <text
            x={W - padR}
            y={H - 16}
            textAnchor="end"
            fill="var(--color-ink-3)"
            fontSize="10"
            fontFamily="var(--font-mono)"
          >
            {last.minute.slice(11, 16)} UTC
          </text>
        </svg>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[0.6875rem]">
        <span className="flex items-center gap-1.5 text-accent">
          <svg width="18" height="3" aria-hidden="true">
            <line x1="0" y1="1.5" x2="18" y2="1.5" stroke="currentColor" strokeWidth="2" />
          </svg>
          fleet (exact)
        </span>
        <span className="flex items-center gap-1.5 text-ink">
          <svg width="18" height="3" aria-hidden="true">
            <line
              x1="0"
              y1="1.5"
              x2="18"
              y2="1.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeDasharray="5 3"
            />
          </svg>
          clickhouse (pipeline)
        </span>
        <GapReadout fleet={last.sessions} pipeline={lastCH} />
      </div>
    </div>
  );
}

/**
 * The latest disagreement, in absolute and relative terms.
 *
 * Rendered even when it is zero, because "0" is the result worth seeing — a blank
 * space would be indistinguishable from the readout not working.
 */
function GapReadout({
  fleet,
  pipeline,
}: {
  fleet: number;
  pipeline: number | undefined;
}) {
  if (pipeline === undefined) {
    return (
      <span className="text-ink-3">
        gap: no pipeline data for the latest minute
      </span>
    );
  }
  const delta = pipeline - fleet;
  const pct = fleet === 0 ? 0 : (delta / fleet) * 100;
  const tone =
    delta === 0 ? "text-accent" : Math.abs(pct) < 2 ? "text-ink-2" : "text-bad";
  return (
    <span className={tone}>
      gap: {delta > 0 ? "+" : ""}
      {delta}
      {fleet > 0 && ` (${delta > 0 ? "+" : ""}${pct.toFixed(1)}%)`}
    </span>
  );
}

function niceCeiling(v: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(v));
  return Math.ceil(v / magnitude) * magnitude;
}

function compact(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}k` : String(v);
}
