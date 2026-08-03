import { EventProfile, FeatureManifest, FieldProfile } from "./types.js";

export function parseNdjson(ndjson: string): Record<string, unknown>[] {
  return ndjson
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      try {
        return JSON.parse(line) as Record<string, unknown>;
      } catch (error) {
        throw new Error(`Invalid JSON on NDJSON line ${index + 1}: ${error}`);
      }
    });
}

export function profileEvents(
  featureSlug: string,
  events: Record<string, unknown>[],
): EventProfile {
  const eventCounts: Record<string, number> = {};
  const fieldMap = new Map<string, FieldProfile>();

  for (const event of events) {
    const eventName = String(event.event ?? "unknown_event");
    eventCounts[eventName] = (eventCounts[eventName] ?? 0) + 1;

    for (const [fieldPath, value] of flattenObject(event)) {
      const existing =
        fieldMap.get(fieldPath) ??
        ({
          path: fieldPath,
          count: 0,
          null_count: 0,
          types: [],
          sample_values: [],
        } satisfies FieldProfile);

      existing.count += 1;
      if (value === null || value === undefined || value === "") {
        existing.null_count += 1;
      }

      const type = inferJsonType(value);
      if (!existing.types.includes(type)) {
        existing.types.push(type);
      }
      if (
        existing.sample_values.length < 5 &&
        value !== null &&
        value !== undefined &&
        value !== "" &&
        !existing.sample_values.includes(value)
      ) {
        existing.sample_values.push(value);
      }
      fieldMap.set(fieldPath, existing);
    }
  }

  return {
    feature_slug: featureSlug,
    row_count: events.length,
    event_counts: eventCounts,
    event_order: Object.keys(eventCounts),
    fields: [...fieldMap.values()].sort((a, b) => a.path.localeCompare(b.path)),
  };
}

export function extractSpecEventOrder(
  specMarkdown: string,
  fallback: string[],
) {
  const matches = [...specMarkdown.matchAll(/-\s+`([^`]+)`\s+[—-]/g)].map(
    (match) => match[1],
  );
  return matches.length > 0 ? matches : fallback;
}

export function inferMetricHints(
  workflowType: FeatureManifest["workflow_type"],
  eventOrder: string[],
) {
  const start = eventOrder[0] ?? "first_event";
  const end = eventOrder.at(-1) ?? "success_event";
  if (workflowType === "revenue_addon") {
    return ["attach_rate", "aov_uplift", "dropoff_by_step", "destination_mix"];
  }
  if (workflowType === "referral_loop") {
    return [
      "share_rate",
      "channel_mix",
      "new_user_open_rate",
      "recipient_cta_rate",
    ];
  }
  if (workflowType === "recovery") {
    return ["reconversion_rate", "channel_recovery_rate", "timing_effect"];
  }
  return [
    `${start}_to_${end}_conversion`,
    "step_through_rate",
    "segment_comparison",
  ];
}

export function toColumnName(fieldPath: string) {
  if (fieldPath === "event") {
    return "event_name";
  }
  if (fieldPath === "id") {
    return "event_id";
  }
  return fieldPath.replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_|_$/g, "");
}

export function normalizeFeatureSlug(folderName: string) {
  return folderName.replace(/^\d+_/, "").replace(/[^a-zA-Z0-9]+/g, "_");
}

export function getPath(value: Record<string, unknown>, sourcePath: string) {
  return sourcePath.split(".").reduce<unknown>((current, part) => {
    if (current && typeof current === "object" && part in current) {
      return (current as Record<string, unknown>)[part];
    }
    return undefined;
  }, value);
}

function flattenObject(
  value: Record<string, unknown>,
  prefix = "",
): Array<[string, unknown]> {
  const entries: Array<[string, unknown]> = [];
  for (const [key, child] of Object.entries(value)) {
    const childPath = prefix ? `${prefix}.${key}` : key;
    if (
      child &&
      typeof child === "object" &&
      !Array.isArray(child) &&
      !(child instanceof Date)
    ) {
      entries.push(
        ...flattenObject(child as Record<string, unknown>, childPath),
      );
    } else {
      entries.push([childPath, child]);
    }
  }
  return entries;
}

function inferJsonType(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "null";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  return typeof value;
}
