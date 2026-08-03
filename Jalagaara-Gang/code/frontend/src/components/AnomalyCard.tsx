import type { Anomaly } from "../types";
import type { SeriesPoint } from "../api";
import { Sparkline } from "./Sparkline";

// Counts (requests/revenue) round + group; ratios (fill_rate/ctr/ecpm) keep significant digits —
// otherwise a fill_rate of 0.98 rounds to a meaningless "1".
const fmt = (n: number) =>
  Math.abs(n) >= 1000 ? Math.round(n).toLocaleString("en-US") : String(Number(n.toPrecision(3)));

// "Jul 04 10:00–11:00 UTC" from the anomaly's target window; falls back to "" if unset.
function windowLabel(window?: { start: string; end: string }): string {
  if (!window) return "";
  const s = new Date(window.start);
  const e = new Date(window.end);
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return "";
  const day = s.toLocaleDateString("en-US", { month: "short", day: "2-digit", timeZone: "UTC" });
  const hm = (d: Date) =>
    d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
  return `${day} ${hm(s)}–${hm(e)} UTC`;
}

// Hero card: the anomaly headline, actuals vs expected, and the real 24h drop curve.
export function AnomalyCard({
  metric,
  anomaly,
  confidence,
  running,
  window,
  series,
  seriesLoading,
}: {
  metric: string;
  anomaly: Anomaly;
  confidence?: number;
  running?: boolean;
  window?: { start: string; end: string };
  series?: SeriesPoint[];
  seriesLoading?: boolean;
}) {
  const pct = (anomaly.pct_delta * 100).toFixed(1);
  const sign = anomaly.pct_delta < 0 ? "−" : "+";
  const headline = running ? "−?" : `${sign}${Math.abs(Number(pct))}%`;
  const when = windowLabel(window);
  const hasSeries = !!series && series.some((p) => p.actual !== null);
  // "−24h" applies to the real chart AND to the loading skeleton (a live series is coming);
  // only the synthetic offline fallback spans 48h.
  const realWindow = hasSeries || seriesLoading;

  return (
    <section className="card card--feature">
      <div className="anomaly-head">
        <div className="anomaly-figures">
          <span className="eyebrow">Anomaly detected</span>
          <div className="figure-row">
            <span className="metric-name">{metric}</span>
            <span className={`headline ${anomaly.direction === "spike" ? "is-up" : ""}`}>{headline}</span>
          </div>
          <span className="sub-mono">
            {fmt(anomaly.observed)} actual · {fmt(anomaly.expected)} expected{when ? ` · ${when}` : ""}
          </span>
        </div>
        <div className="culprit-badge">
          <span className="dot" />
          <div>
            <div className="cb-title">{confidence != null ? "culprit localized" : "population-wide"}</div>
            <div className="cb-sub">
              {confidence != null ? `confidence ${confidence.toFixed(2)}` : "no single segment"}
            </div>
          </div>
        </div>
      </div>

      <Sparkline points={series} loading={seriesLoading} />
      <div className="spark-legend">
        <span>{realWindow ? "−24h" : "−48h"}</span>
        <span className="keys">
          <span className="key"><span className="swatch-line" />actual</span>
          <span className="key"><span className="swatch-dash" />expected</span>
        </span>
        <span>now</span>
      </div>
    </section>
  );
}
