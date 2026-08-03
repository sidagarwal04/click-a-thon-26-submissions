import type { SeriesPoint } from "../api";

// Actual-vs-expected curve for the anomaly card. With real `points` (24 hourly buckets from
// GET /series) it plots them to scale; with none it falls back to a synthetic curve so the
// card always renders offline. Coordinates are SVG viewBox units — colours come from CSS.
const W = 900;
const H = 220;
const PAD_TOP = 12;
const PAD_BOT = 8;

function median(a: number[]): number {
  const s = [...a].sort((x, y) => x - y);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// Break the path at null holes so an empty hour gaps instead of drawing a line to zero.
function pathFrom(vals: (number | null)[], x: (i: number) => number, y: (v: number) => number): string {
  let d = "";
  let pen = false; // is the pen down (mid-segment)?
  vals.forEach((v, i) => {
    if (v === null) {
      pen = false;
      return;
    }
    d += (pen ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1);
    pen = true;
  });
  return d;
}

function RealSpark({ points }: { points: SeriesPoint[] }) {
  const n = points.length;
  const actual = points.map((p) => p.actual);
  const expected = points.map((p) => p.expected);

  const finite = [...actual, ...expected].filter((v): v is number => v !== null && Number.isFinite(v));
  const expFinite = expected.filter((v): v is number => v !== null && Number.isFinite(v));

  // Scale the y-axis around the baseline with a MINIMUM relative half-span. Auto-fitting to the
  // data's raw min/max magnifies a tiny move (a 1% fill_rate dip fills the whole plot); the floor
  // keeps a small % move looking small, while a large move still expands the band and dominates —
  // so a −1% and a −40% anomaly no longer render identically.
  const MIN_REL = 0.06; // ±6% of baseline is the tightest the axis ever zooms
  const PAD = 1.15; // headroom so lines don't touch the top/bottom edges
  const center = expFinite.length ? median(expFinite) : (Math.min(...finite) + Math.max(...finite)) / 2;
  const dataHalf = Math.max(...finite.map((v) => Math.abs(v - center)), 0);
  const half = (Math.max(dataHalf, Math.abs(center) * MIN_REL) || 1) * PAD;
  const lo = center - half;
  const span = 2 * half;

  const x = (i: number) => (n <= 1 ? 0 : (i / (n - 1)) * W);
  const y = (v: number) => PAD_TOP + (1 - (v - lo) / span) * (H - PAD_TOP - PAD_BOT);

  const exp = pathFrom(expected, x, y);
  const act = pathFrom(actual, x, y);

  // Fill under the actual line, anchored to the baseline of the plot.
  const firstActual = actual.findIndex((v) => v !== null);
  const areaPath = act ? act + `L${x(n - 1).toFixed(1)} ${H} L${x(firstActual).toFixed(1)} ${H} Z` : "";

  // Endpoint marker: the last hour with an actual value.
  let lastIdx = -1;
  for (let i = n - 1; i >= 0; i--) if (actual[i] !== null) { lastIdx = i; break; }

  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="fillDrop" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--content-negative-dark)" stopOpacity="0.34" />
          <stop offset="100%" stopColor="var(--content-negative-dark)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[40, 90, 140, 190].map((gy) => (
        <line key={gy} x1="0" y1={gy} x2={W} y2={gy} stroke="var(--border-neutral-default)" />
      ))}
      {areaPath && <path d={areaPath} fill="url(#fillDrop)" stroke="none" />}
      {exp && (
        <path d={exp} fill="none" stroke="var(--content-neutral-main)" strokeWidth="1.6" strokeDasharray="5 5" />
      )}
      {act && (
        <path d={act} fill="none" stroke="var(--content-secondary-main)" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
      )}
      {lastIdx >= 0 && actual[lastIdx] !== null && (
        <circle cx={x(lastIdx)} cy={y(actual[lastIdx]!)} r="4.5" fill="var(--content-negative-dark)" />
      )}
    </svg>
  );
}

// Synthetic fallback (no real data): shape-only, used offline / for the bundled sample.
function SyntheticSpark() {
  const pts = 24;
  const drop = 18;
  const base = (i: number) => 88 + Math.sin(i / 3.1) * 5 + Math.sin(i / 7.7) * 4;
  const y = (v: number) => 200 - (v - 55) * 3.2;
  const x = (i: number) => (i / (pts - 1)) * W;

  let exp = "";
  let act = "";
  for (let i = 0; i < pts; i++) {
    const e = base(i);
    const a = i < drop ? e - 1.5 + Math.sin(i * 1.7) * 1.6 : e - (i - drop + 1) * 3.4;
    exp += (i ? "L" : "M") + x(i).toFixed(1) + " " + y(e).toFixed(1);
    act += (i ? "L" : "M") + x(i).toFixed(1) + " " + y(a).toFixed(1);
  }
  const last = base(pts - 1) - (pts - drop) * 3.4;
  const areaPath = act + `L${W} 212 L0 212 Z`;

  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="fillDrop" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--content-negative-dark)" stopOpacity="0.34" />
          <stop offset="100%" stopColor="var(--content-negative-dark)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[40, 90, 140, 190].map((gy) => (
        <line key={gy} x1="0" y1={gy} x2={W} y2={gy} stroke="var(--border-neutral-default)" />
      ))}
      <path d={exp} fill="none" stroke="var(--content-neutral-main)" strokeWidth="1.6" strokeDasharray="5 5" />
      <path d={areaPath} fill="url(#fillDrop)" stroke="none" />
      <path d={act} fill="none" stroke="var(--content-secondary-main)" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
      <line x1={x(drop)} y1="8" x2={x(drop)} y2="212" stroke="var(--content-negative-dark)" strokeWidth="1" strokeDasharray="3 4" opacity="0.7" />
      <circle cx={x(pts - 1)} cy={y(last)} r="4.5" fill="var(--content-negative-dark)" />
      {/* Say so on the chart itself. This curve is Math.sin(), not data, and it is styled
          exactly like the real one — unlabelled, it reads as a measured baseline. */}
      <text x="8" y="20" className="spark-synthetic-tag">illustrative shape — not measured data</text>
    </svg>
  );
}

// Grid-only placeholder shown while a real series is being fetched — avoids flashing the
// synthetic curve for a frame every time the shown anomaly changes.
function SkeletonSpark() {
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      {[40, 90, 140, 190].map((gy) => (
        <line key={gy} x1="0" y1={gy} x2={W} y2={gy} stroke="var(--border-neutral-default)" />
      ))}
    </svg>
  );
}

export function Sparkline({ points, loading }: { points?: SeriesPoint[]; loading?: boolean }) {
  const hasReal = !!points && points.some((p) => p.actual !== null);
  if (hasReal) return <RealSpark points={points!} />;
  // While a live fetch is in flight, show the empty grid rather than the synthetic curve.
  if (loading) return <SkeletonSpark />;
  return <SyntheticSpark />;
}
