import "server-only";

import { createClient } from "@clickhouse/client";
import type {
  ChartPoint,
  DashboardData,
  Incident,
  Metric,
  MetricKey,
  SegmentEvidence,
  SegmentSignal,
} from "./types";

const HOUR_MS = 60 * 60 * 1000;
const METRICS: MetricKey[] = [
  "requests",
  "revenue",
  "fill_rate",
  "render_rate",
  "ctr",
  "ecpm",
  "rpr",
];

interface AnomalyRow {
  detected_at: string;
  metric: MetricKey;
  method: string;
  time_window: string;
  observed: number | null;
  expected: number | null;
  pct_delta: number | null;
  z: number;
}

interface SegmentEvidenceRow {
  metric: MetricKey;
  incident_start: string;
  incident_end: string;
  dimension: string;
  segment: string;
  peak_z: number;
  mean_z: number;
  global_peak_z: number;
  global_mean_z: number;
  incident_correlation: number | null;
  incident_correlation_n: number;
  baseline_correlation: number | null;
  baseline_correlation_n: number;
  direction_match_pct: number;
  scored_hours: number;
  quiet_hours: number;
}

interface IncidentRow {
  metric: MetricKey;
  start_time: string;
  end_time: string;
  flagged_hours: number;
  methods: string[];
  detected_at: string;
  observed: number | null;
  expected: number | null;
  pct_delta: number | null;
}

interface GlobalSeasonalZRow {
  metric: MetricKey;
  hour_ts: string;
  z: number;
}

interface HourRow {
  hour_ts: string;
  dow: number;
  hod: number;
  requests: number;
  fills: number;
  impressions: number;
  clicks: number;
  revenue: number;
}

function asTime(value: string): number {
  return Date.parse(value);
}

function metricValue(metric: MetricKey, rows: HourRow[]): number {
  const requests = rows.reduce((sum, row) => sum + Number(row.requests), 0);
  const fills = rows.reduce((sum, row) => sum + Number(row.fills), 0);
  const impressions = rows.reduce(
    (sum, row) => sum + Number(row.impressions),
    0,
  );
  const clicks = rows.reduce((sum, row) => sum + Number(row.clicks), 0);
  const revenue = rows.reduce((sum, row) => sum + Number(row.revenue), 0);

  switch (metric) {
    case "requests":
      return requests;
    case "revenue":
      return revenue;
    case "fill_rate":
      return requests ? fills / requests : 0;
    case "render_rate":
      return fills ? impressions / fills : 0;
    case "ctr":
      return impressions ? clicks / impressions : 0;
    case "ecpm":
      return impressions ? (revenue / impressions) * 1000 : 0;
    case "rpr":
      return requests ? revenue / requests : 0;
  }
}

function mean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function buildSeries(
  metric: MetricKey,
  rows: HourRow[],
  anomalousHours: Set<string>,
): ChartPoint[] {
  return rows.map((row, index) => {
    const baselineRows = rows
      .slice(0, index)
      .filter(
        (candidate) => candidate.dow === row.dow && candidate.hod === row.hod,
      )
      .slice(-4);
    const baselineValues = baselineRows.map((candidate) =>
      metricValue(metric, [candidate]),
    );
    const expected = baselineRows.length
      ? metric === "requests" || metric === "revenue"
        ? mean(baselineValues)
        : metricValue(metric, baselineRows)
      : null;
    const variance =
      baselineValues.length > 1 && expected != null
        ? mean(baselineValues.map((value) => (value - expected) ** 2))
        : 0;
    const spread = Math.sqrt(variance) * 2;

    return {
      time: row.hour_ts,
      actual: metricValue(metric, [row]),
      expected,
      lower: expected == null ? null : expected - spread,
      upper: expected == null ? null : expected + spread,
      anomalous: anomalousHours.has(`${metric}|${row.hour_ts}`),
    };
  });
}

function segmentSignalsFor(evidence: SegmentEvidence[]): SegmentSignal[] {
  return evidence
    .map((row) => ({
      dimension: row.dimension,
      segment: row.segment,
      methods: ["trend_seasonal"],
      maxAbsZ: Math.abs(row.peakZ),
      pctDelta: null,
    }))
    .sort((a, b) => b.maxAbsZ - a.maxAbsZ)
    .filter((signal) => signal.maxAbsZ >= 5)
    .slice(0, 3);
}

function seasonalPeakZFor(
  incident: Pick<Incident, "metric" | "startTime" | "endTime">,
  rows: GlobalSeasonalZRow[],
): number {
  const start = asTime(incident.startTime);
  const end = asTime(incident.endTime);
  return rows.reduce((peak, row) => {
    const time = asTime(row.hour_ts);
    return row.metric === incident.metric && time >= start && time <= end
      ? Math.max(peak, Math.abs(Number(row.z)))
      : peak;
  }, 0);
}

function segmentEvidenceFor(
  incident: Pick<Incident, "metric" | "startTime" | "endTime">,
  rows: SegmentEvidenceRow[],
): SegmentEvidence[] {
  return rows
    .filter(
      (row) =>
        row.metric === incident.metric &&
        row.incident_start === incident.startTime &&
        row.incident_end === incident.endTime,
    )
    .map((row) => ({
      dimension: row.dimension,
      segment: row.segment,
      peakZ: Number(row.peak_z),
      meanZ: Number(row.mean_z),
      globalPeakZ: Number(row.global_peak_z),
      globalMeanZ: Number(row.global_mean_z),
      incidentCorrelation:
        row.incident_correlation == null
          ? null
          : Number(row.incident_correlation),
      incidentCorrelationN: Number(row.incident_correlation_n),
      baselineCorrelation:
        row.baseline_correlation == null
          ? null
          : Number(row.baseline_correlation),
      baselineCorrelationN: Number(row.baseline_correlation_n),
      directionMatchPct: Number(row.direction_match_pct),
      scoredHours: Number(row.scored_hours),
      quietHours: Number(row.quiet_hours),
    }))
    .sort(
      (a, b) =>
        a.dimension.localeCompare(b.dimension) ||
        Math.abs(b.peakZ) - Math.abs(a.peakZ) ||
        a.segment.localeCompare(b.segment),
    );
}

function overlaps(
  a: Pick<Incident, "startTime" | "endTime">,
  b: Pick<Incident, "startTime" | "endTime">,
): boolean {
  return (
    asTime(a.startTime) <= asTime(b.endTime) + HOUR_MS &&
    asTime(b.startTime) <= asTime(a.endTime) + HOUR_MS
  );
}

async function queryRows<T>(query: string): Promise<T[]> {
  const client = createClient({
    url: process.env.CLICKHOUSE_URL,
    username: process.env.CLICKHOUSE_USER ?? "default",
    password: process.env.CLICKHOUSE_PASSWORD,
    database: process.env.CLICKHOUSE_DATABASE ?? "default",
    request_timeout: 30_000,
  });
  try {
    const result = await client.query({
      query,
      format: "JSONEachRow",
      clickhouse_settings: { readonly: "1", max_execution_time: 30 },
    });
    return await result.json<T>();
  } finally {
    await client.close();
  }
}

export async function loadDashboardData(): Promise<DashboardData> {
  if (!process.env.CLICKHOUSE_URL) {
    return {
      incidents: [],
      metrics: [],
      rawSignalCount: 0,
      generatedAt: new Date().toISOString(),
      error: "CLICKHOUSE_URL is not configured for apps/web.",
    };
  }

  try {
    const [
      incidentRows,
      anomalies,
      evidenceRows,
      globalSeasonalZRows,
      hourRows,
    ] = await Promise.all([
      // Incident policy is owned by ClickHouse's refreshable mv_incidents;
      // this layer only maps its canonical rows into the dashboard shape.
      queryRows<IncidentRow>(`
        SELECT
          metric,
          formatDateTime(start_time, '%FT%TZ', 'UTC') AS start_time,
          formatDateTime(end_time, '%FT%TZ', 'UTC') AS end_time,
          toUInt16(flagged_hours) AS flagged_hours,
          methods,
          formatDateTime(detected_at, '%FT%TZ', 'UTC') AS detected_at,
          toFloat64(observed) AS observed,
          toFloat64(expected) AS expected,
          pct_delta
        FROM inmobi.incidents
        ORDER BY start_time DESC, end_time DESC, metric
      `),
      queryRows<AnomalyRow>(`
        SELECT
          formatDateTime(a.detected_at, '%FT%TZ', 'UTC') AS detected_at,
          a.metric AS metric, a.method AS method,
          formatDateTime(a.time_window, '%FT%TZ', 'UTC') AS time_window,
          toFloat64(a.observed) AS observed, toFloat64(a.expected) AS expected,
          a.pct_delta AS pct_delta, toFloat64(a.z) AS z
        FROM inmobi.anomalies AS a
        INNER JOIN inmobi.detection_config AS c
          ON c.metric = a.metric AND c.method = a.method AND c.enabled = 1
        WHERE a.time_window >= (SELECT max(time_window) - INTERVAL 60 DAY FROM inmobi.anomalies)
        ORDER BY a.metric, a.method, a.time_window
      `),
      queryRows<SegmentEvidenceRow>(`
        SELECT
          metric,
          formatDateTime(incident_start, '%FT%TZ', 'UTC') AS incident_start,
          formatDateTime(incident_end, '%FT%TZ', 'UTC') AS incident_end,
          dimension, segment,
          toFloat64(peak_z) AS peak_z,
          toFloat64(mean_z) AS mean_z,
          toFloat64(global_peak_z) AS global_peak_z,
          toFloat64(global_mean_z) AS global_mean_z,
          toFloat64(incident_correlation) AS incident_correlation,
          toUInt16(incident_correlation_n) AS incident_correlation_n,
          toFloat64(baseline_correlation) AS baseline_correlation,
          toUInt16(baseline_correlation_n) AS baseline_correlation_n,
          toFloat64(direction_match_pct) AS direction_match_pct,
          toUInt16(scored_hours) AS scored_hours,
          toUInt16(quiet_hours) AS quiet_hours
        FROM inmobi.segment_incident_evidence
        ORDER BY metric, incident_start, dimension, segment
      `),
      queryRows<GlobalSeasonalZRow>(`
        SELECT
          metric,
          formatDateTime(hour_ts, '%FT%TZ', 'UTC') AS hour_ts,
          toFloat64(zr) AS z
        FROM inmobi.metric_zr_hourly AS seasonal
        WHERE seasonal.hour_ts >= (
          SELECT max(hour_ts) - INTERVAL 60 DAY
          FROM inmobi.metric_zr_hourly
        )
        ORDER BY metric, seasonal.hour_ts
      `),
      queryRows<HourRow>(`
        SELECT
          formatDateTime(hour_ts, '%FT%TZ', 'UTC') AS hour_ts,
          toUInt8(dow) AS dow, toUInt8(hod) AS hod,
          toFloat64(requests) AS requests, toFloat64(fills) AS fills,
          toFloat64(impressions) AS impressions, toFloat64(clicks) AS clicks,
          toFloat64(revenue) AS revenue
        FROM inmobi.metrics_hourly_v AS h
        WHERE h.hour_ts >= (SELECT max(hour_ts) - INTERVAL 90 DAY FROM inmobi.metrics_hourly_v)
        ORDER BY hour_ts
      `),
    ]);

    const anomalousHours = new Set(
      anomalies.map((row) => `${row.metric}|${row.time_window}`),
    );
    const allSeries = new Map(
      METRICS.map((metric) => [
        metric,
        buildSeries(metric, hourRows, anomalousHours),
      ]),
    );
    const collapsed: Array<
      Omit<
        Incident,
        "series" | "segmentSignals" | "segmentEvidence" | "relatedMetrics"
      >
    > = incidentRows.map((row) => ({
      id: `${row.metric}-${row.start_time.replaceAll(/[-:.TZ]/g, "")}`,
      metric: row.metric,
      methods: row.methods,
      startTime: row.start_time,
      endTime: row.end_time,
      detectedAt: row.detected_at,
      flaggedHours: Number(row.flagged_hours),
      maxAbsZ: seasonalPeakZFor(
        {
          metric: row.metric,
          startTime: row.start_time,
          endTime: row.end_time,
        },
        globalSeasonalZRows,
      ),
      observed: row.observed == null ? null : Number(row.observed),
      expected: row.expected == null ? null : Number(row.expected),
      pctDelta: row.pct_delta == null ? null : Number(row.pct_delta),
    }));
    const incidents: Incident[] = collapsed.map((incident) => {
      const paddingStart = asTime(incident.startTime) - 24 * HOUR_MS;
      const paddingEnd = asTime(incident.endTime) + 24 * HOUR_MS;
      const segmentEvidence = segmentEvidenceFor(incident, evidenceRows);
      return {
        ...incident,
        series: (allSeries.get(incident.metric) ?? []).filter((point) => {
          const time = asTime(point.time);
          return time >= paddingStart && time <= paddingEnd;
        }),
        segmentSignals: segmentSignalsFor(segmentEvidence),
        segmentEvidence,
        relatedMetrics: [
          ...new Set(
            collapsed
              .filter(
                (other) =>
                  other.metric !== incident.metric && overlaps(incident, other),
              )
              .map((other) => other.metric),
          ),
        ],
      };
    });

    const metrics: Metric[] = METRICS.map((key) => {
      const series = (allSeries.get(key) ?? []).slice(-48);
      const latest = series.at(-1);
      const delta = latest?.expected
        ? (latest.actual - latest.expected) / latest.expected
        : null;
      const incident =
        incidents.find((candidate) => candidate.metric === key) ?? null;
      return {
        key,
        value: latest?.actual ?? 0,
        expected: latest?.expected ?? null,
        delta,
        tone: incident
          ? incident.pctDelta != null && incident.pctDelta > 0
            ? "warn"
            : "bad"
          : "ok",
        incidentId: incident?.id ?? null,
        series,
      };
    });
    return {
      incidents,
      metrics,
      rawSignalCount: anomalies.length,
      generatedAt: new Date().toISOString(),
    };
  } catch (error) {
    console.error("Failed to load Baseline dashboard data", error);
    return {
      incidents: [],
      metrics: [],
      rawSignalCount: 0,
      generatedAt: new Date().toISOString(),
      error:
        error instanceof Error ? error.message : "Unknown ClickHouse error",
    };
  }
}
