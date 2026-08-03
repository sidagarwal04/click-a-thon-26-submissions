import type { Incident, MetricKey } from "./types";

const LABELS: Record<MetricKey, string> = {
  requests: "Requests",
  revenue: "Revenue",
  fill_rate: "Fill rate",
  render_rate: "Render rate",
  ctr: "CTR",
  ecpm: "eCPM",
  rpr: "Revenue / request",
};

export function metricLabel(metric: MetricKey): string {
  return LABELS[metric];
}

export function formatMetric(metric: MetricKey, value: number): string {
  if (metric === "fill_rate" || metric === "render_rate" || metric === "ctr") {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (metric === "revenue" || metric === "ecpm" || metric === "rpr") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: metric === "revenue" ? 0 : 3,
    }).format(value);
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(
    value,
  );
}

export function formatMetricMaybe(
  metric: MetricKey,
  value: number | null,
): string {
  return value == null ? "not recorded" : formatMetric(metric, value);
}

export function formatDelta(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value * 100).toFixed(1)}%`;
}

export function formatUtc(value: string): string {
  const formatted = new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(value));
  return `${formatted} UTC`;
}

export function durationLabel(
  incident: Pick<Incident, "startTime" | "endTime">,
): string {
  const hours =
    Math.round(
      (Date.parse(incident.endTime) - Date.parse(incident.startTime)) /
        3_600_000,
    ) + 1;
  return `${hours} hour${hours === 1 ? "" : "s"}`;
}

export function incidentHeadline(incident: Incident): string {
  if (incident.observed == null || incident.expected == null) {
    return `${metricLabel(incident.metric)} deviated from its seasonal baseline.`;
  }
  const direction =
    incident.observed >= incident.expected ? "rose above" : "fell below";
  return `${metricLabel(incident.metric)} ${direction} its seasonal baseline.`;
}

function formatOverviewWindow(
  incident: Pick<Incident, "startTime" | "endTime">,
): string {
  const start = new Date(incident.startTime);
  const end = new Date(incident.endTime);
  const time = new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const date = new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
  });

  return date.format(start) === date.format(end)
    ? `${time.format(start)}–${time.format(end)} UTC`
    : `${date.format(start)} ${time.format(start)}–${date.format(end)} ${time.format(end)} UTC`;
}

/** A high-level description composed solely from stored detector evidence. */
export function incidentOverview(incident: Incident): string {
  const direction = (incident.pctDelta ?? 0) >= 0 ? "rose" : "fell";
  const delta =
    incident.pctDelta == null
      ? "deviated"
      : `${direction} ${Math.abs(incident.pctDelta * 100).toFixed(1)}%`;
  const overview = `${metricLabel(incident.metric)} ${delta} from its same-hour seasonal baseline between ${formatOverviewWindow(incident)}.`;
  const segmentDetail = incident.segmentSignals.length
    ? ` The strongest matching segment ${incident.segmentSignals.length === 1 ? "signal was" : "signals were"} ${incident.segmentSignals
        .map(
          (signal) =>
            `${signal.segment} (${signal.dimension.replaceAll("_", " ")}, seasonal |z| ${signal.maxAbsZ.toFixed(2)})`,
        )
        .join(", ")}.`
    : "";
  const relatedMetrics = incident.relatedMetrics.map(metricLabel);
  const relatedDetail = relatedMetrics.length
    ? ` Overlapping top-level incidents were also recorded for ${relatedMetrics.join(", ")}.`
    : "";

  return `${overview}${segmentDetail}${relatedDetail}`;
}

/** A plain-language explanation of why the incident cleared the reportability bar. */
export function reportabilitySummary(incident: Incident): string {
  const methods = incident.methods;
  const totalHours =
    Math.round(
      (Date.parse(incident.endTime) - Date.parse(incident.startTime)) /
        3_600_000,
    ) + 1;
  const persistent = incident.flaggedHours >= 8;
  const agreement = methods.length >= 2;
  const confirmedBy =
    methods.length === 1
      ? `the ${methods[0]} detector`
      : `${methods.length} independent detection methods (${methods.join(", ")})`;
  const rule =
    persistent && agreement
      ? "both persistence and independent method agreement satisfy the reportability rule"
      : persistent
        ? "persistence alone satisfies the reportability rule"
        : "independent method agreement satisfies the reportability rule";
  const flagged =
    incident.flaggedHours >= totalHours
      ? `Every hour in this ${totalHours}-hour window was flagged`
      : `${incident.flaggedHours} of the ${totalHours} hours in this window were flagged`;

  return `${flagged} (${formatUtc(incident.startTime)} – ${formatUtc(incident.endTime)}), confirmed by ${confirmedBy}. The strongest hour reached seasonal |z| ${incident.maxAbsZ.toFixed(2)} against its trailing 4-week same-hour baseline — ${rule}.`;
}
