import { RAW_MEASURES } from "./rawMeasures.js";
import type { MetricDefinition } from "./types.js";

/**
 * Generates the `trend_seasonal` detection query for every `kind: 'ratio'`
 * metric in the registry, over `inmobi.metrics_hourly` (global grain).
 * Structurally identical to the ratio block in sql/04_detect_and_populate.sql
 * — same shrinkage/z-score math — the only thing that varies per call is
 * which metrics are in `metrics`, generated from data instead of hand-written
 * per metric. See scripts/prototype-registry.ts for the equivalence check
 * against the static file.
 *
 * Every identifier this emits (`numerator`/`denominator` column names) comes
 * from RAW_MEASURES (hardcoded in code) via a MetricDefinition's
 * numeratorId/denominatorId — never from free text, so there's no
 * injection surface even though this is templated SQL. `withThreshold`
 * controls whether the z-threshold WHERE (via detection_config) is applied;
 * pass false to get every computed z back, e.g. for the equivalence check.
 */
export function buildRatioTrendSeasonalSelect(
  metrics: MetricDefinition[],
  opts: { withThreshold: boolean } = { withThreshold: true },
): string {
  const ratios = metrics.filter((m) => m.kind === "ratio");
  if (ratios.length === 0) throw new Error("no ratio metrics in registry");
  for (const m of ratios) {
    if (!m.denominatorId) throw new Error(`ratio metric "${m.id}" missing denominatorId`);
  }

  const valueExprs = ratios
    .map((m) => {
      const num = RAW_MEASURES[m.numeratorId].column;
      const den = RAW_MEASURES[m.denominatorId!].column;
      const scaleSuffix = m.scale !== 1 ? `*${m.scale}` : "";
      return `    ${num}/${den}${scaleSuffix} AS ${m.id}`;
    })
    .join(",\n");

  const unpivotBranches = ratios
    .map((m, i) => {
      const select = `SELECT hour_ts, d, dow, hod, '${m.id}' AS metric, ${m.id} AS value FROM ratios`;
      return i === 0 ? `  ${select}` : `  UNION ALL ${select}`;
    })
    .join("\n");

  const thresholdJoin = opts.withThreshold
    ? `INNER JOIN inmobi.detection_config c ON c.metric = x.metric AND c.method = 'trend_seasonal' AND c.enabled = 1\nWHERE baseline_n >= 2 AND abs((value-mean_v)/nullif(std_v,0)) > c.z_threshold`
    : `WHERE baseline_n >= 2`;

  return `
WITH ratios AS (
  SELECT hour_ts, d, dow, hod,
${valueExprs}
  FROM inmobi.metrics_hourly
),
unpivoted AS (
${unpivotBranches}
),
cell_mean AS (SELECT metric, dow, hod, avg(value) AS ca FROM unpivoted GROUP BY metric, dow, hod),
noise AS (
  SELECT u.metric AS metric, varSamp(u.value - cm.ca) AS v
  FROM unpivoted u JOIN cell_mean cm USING (metric, dow, hod)
  GROUP BY u.metric
),
seasonal AS (
  SELECT *,
    avg(value) OVER w AS mean_v, varSamp(value) OVER w AS var_v,
    count(value) OVER w AS baseline_n
  FROM unpivoted
  WINDOW w AS (PARTITION BY metric, dow, hod ORDER BY d ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
),
scored AS (
  SELECT s.*, n.v AS noise_v,
    sqrt((baseline_n*ifNull(var_v,0) + 3*n.v) / (baseline_n+3)) AS std_v
  FROM seasonal s JOIN noise n USING (metric)
)
SELECT x.metric, hour_ts, value, mean_v, value-mean_v, (value-mean_v)/mean_v AS pct_delta,
  (value-mean_v)/nullif(std_v,0) AS z, baseline_n
FROM scored x
${thresholdJoin}`.trim();
}
