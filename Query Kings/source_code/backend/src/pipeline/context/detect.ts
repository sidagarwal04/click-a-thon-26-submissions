import { insertJsonRows } from "./sql.js";
import { UpdateGeneratedContextInput } from "./types.js";
import { slugify } from "./utils.js";

export type DetectedContradiction = {
  id: string;
  summary: string;
  evidence: string;
  status: "open";
};

/**
 * After a validated Silver load, compare the generated schema and feature
 * semantics against base context expectations and known product issues.
 * Deterministic only — no LLM. Writes open rows into context.contradictions.
 */
export async function detectAndWriteContextGaps(
  input: UpdateGeneratedContextInput & {
    baseContext?: string;
  },
): Promise<DetectedContradiction[]> {
  const detected = [
    ...detectSchemaGaps(input),
    ...detectKnownIssueLinks(input),
    ...detectMetricGaps(input),
  ];

  if (detected.length > 0) {
    await insertJsonRows("context.contradictions", detected);
  }

  return detected;
}

function detectSchemaGaps(
  input: UpdateGeneratedContextInput,
): DetectedContradiction[] {
  const gaps: DetectedContradiction[] = [];
  const columns = new Set(
    input.schema_plan.columns.map((column) => column.name),
  );
  const fullTable = `silver.${input.table_name}`;

  if (!columns.has("user_id")) {
    gaps.push({
      id: `gap:${input.feature_slug}:missing_user_id`,
      summary: `${input.feature_slug} Silver table is missing user_id, so it cannot join the base conversion funnel on the primary user key.`,
      evidence: `${fullTable} columns: ${Array.from(columns).join(", ")}`,
      status: "open",
    });
  }

  if (!columns.has("application_id")) {
    gaps.push({
      id: `gap:${input.feature_slug}:missing_application_id`,
      summary: `${input.feature_slug} Silver table is missing application_id; application-level joins to base funnel tables will be weak or impossible.`,
      evidence: `${fullTable} columns: ${Array.from(columns).join(", ")}`,
      status: "open",
    });
  }

  const segmentCandidates = [
    "device_type",
    "os",
    "geoip_country_code",
    "destination",
  ];
  const missingSegments = segmentCandidates.filter(
    (column) => !columns.has(column),
  );
  if (missingSegments.length === segmentCandidates.length) {
    gaps.push({
      id: `gap:${input.feature_slug}:no_segment_dimensions`,
      summary: `${input.feature_slug} has no common segment dimensions (device/os/geo/destination). Segment comparison and known-issue cuts will be limited.`,
      evidence: `Missing: ${missingSegments.join(", ")}`,
      status: "open",
    });
  }

  // Base context claims visa_issuance_eta_days; DDL uses eta_shown.
  // If this feature invents or inherits the wrong name, surface it.
  if (columns.has("visa_issuance_eta_days") && !columns.has("eta_shown")) {
    gaps.push({
      id: `gap:${input.feature_slug}:eta_field_name`,
      summary: `${input.feature_slug} uses visa_issuance_eta_days while base funnel DDL uses eta_shown — treat ETA field naming as ambiguous.`,
      evidence:
        "base_context.md vs data/ddl.sql known naming mismatch; feature schema picked visa_issuance_eta_days.",
      status: "open",
    });
  }

  return gaps;
}

function detectKnownIssueLinks(
  input: UpdateGeneratedContextInput,
): DetectedContradiction[] {
  const links: DetectedContradiction[] = [];
  const eventBlob = input.event_names.join(" ").toLowerCase();
  const metricBlob = input.metric_hints.join(" ").toLowerCase();
  const columnBlob = input.schema_plan.columns
    .map((column) => column.name)
    .join(" ")
    .toLowerCase();
  const text = `${eventBlob} ${metricBlob} ${columnBlob} ${input.feature_slug}`;

  if (/\botp\b|payment|checkout|pay_now|express/.test(text)) {
    links.push({
      id: `known_issue_link:${input.feature_slug}:k1_ios_webkit_otp`,
      summary: `Feature ${input.feature_slug} touches payment/OTP/checkout flows. Analytics should cut by iOS/device and check against known issue K1 (iOS WebKit OTP autofill regression).`,
      evidence:
        "base_context.md known-issues log K1 — pay_now_clicked → purchase_completed weakness on iOS; payment-heavy geos most exposed.",
      status: "open",
    });
  }

  if (/passport|document|capture|mrz|ocr/.test(text)) {
    links.push({
      id: `known_issue_link:${input.feature_slug}:k2_k3_passport`,
      summary: `Feature ${input.feature_slug} relates to document/passport capture. Watch K2 (Android capture failures after model update) and K3 (non-Latin MRZ OCR retries).`,
      evidence:
        "base_context.md known-issues log K2 and K3; document_uploaded.retry_count and is_crossed_failed_attempt_threshold are the base signals.",
      status: "open",
    });
  }

  if (/abandon|recovery|nudge|reengage|whatsapp/.test(text)) {
    links.push({
      id: `known_issue_link:${input.feature_slug}:k5_whatsapp_nudge`,
      summary: `Feature ${input.feature_slug} relates to recovery/re-engagement. Context notes K5 WhatsApp nudge can lift returns for previously dropped users — separate campaign lift from product changes.`,
      evidence: "base_context.md known-issues log K5.",
      status: "open",
    });
  }

  if (/coupon|promo|discount|forex|fx|currency/.test(text)) {
    links.push({
      id: `known_issue_link:${input.feature_slug}:k6_summer20`,
      summary: `Feature ${input.feature_slug} may interact with promo/currency behaviour. K6 SUMMER20 campaign elevates coupon_applied and can lower realised value — do not treat value drops as pure product regressions without checking coupons.`,
      evidence: "base_context.md known-issues log K6.",
      status: "open",
    });
  }

  return links;
}

function detectMetricGaps(
  input: UpdateGeneratedContextInput,
): DetectedContradiction[] {
  const gaps: DetectedContradiction[] = [];
  const columns = new Set(
    input.schema_plan.columns.map((column) => column.name.toLowerCase()),
  );

  for (const hint of input.metric_hints) {
    const tokens = slugify(hint).split("_").filter(Boolean);
    const latencyHint = /latency|duration|time_to|tt[cf]|ms\b/i.test(hint);
    if (latencyHint) {
      const hasLatencyColumn = Array.from(columns).some((column) =>
        /latency|duration|time_to|elapsed|ms$/.test(column),
      );
      if (!hasLatencyColumn) {
        gaps.push({
          id: `gap:${input.feature_slug}:metric_${slugify(hint)}`,
          summary: `Metric hint "${hint}" suggests latency analysis, but ${input.feature_slug} schema has no latency/duration-like column.`,
          evidence: `Columns: ${Array.from(columns).join(", ")}`,
          status: "open",
        });
      }
    }

    // Segment-by hints with no matching dimension
    if (
      /by_device|device_/.test(slugify(hint)) &&
      !columns.has("device_type") &&
      !columns.has("os") &&
      !columns.has("device")
    ) {
      gaps.push({
        id: `gap:${input.feature_slug}:metric_device_cut_${slugify(hint)}`,
        summary: `Metric hint "${hint}" implies a device cut, but no device/os column is present on the generated schema.`,
        evidence: `metric_hints=${input.metric_hints.join(", ")}`,
        status: "open",
      });
    }

    // Soft check: if hint names a concrete field token that never appears
    const specific = tokens.filter(
      (token) =>
        token.length > 3 &&
        ![
          "rate",
          "count",
          "total",
          "share",
          "ratio",
          "with",
          "from",
          "into",
          "over",
          "per",
        ].includes(token),
    );
    const anyTokenInColumns = specific.some((token) =>
      Array.from(columns).some((column) => column.includes(token)),
    );
    if (specific.length >= 2 && !anyTokenInColumns && !latencyHint) {
      // Only warn when clearly orphaned — avoid noise on abstract metrics like conversion
      if (!/conversion|success|adoption|completion|drop/.test(slugify(hint))) {
        gaps.push({
          id: `gap:${input.feature_slug}:orphan_metric_${slugify(hint)}`,
          summary: `Metric hint "${hint}" does not clearly map to any generated column name; analytics should treat the formula as approximate.`,
          evidence: `hint tokens=${specific.join(", ")}; columns=${Array.from(columns).slice(0, 40).join(", ")}`,
          status: "open",
        });
      }
    }
  }

  return gaps;
}

/** Seed structured known-issue facts once at bootstrap so analytics can retrieve them. */
export function buildKnownIssueFacts(jobId: string) {
  return [
    {
      fact_id: "known_issue:k1_ios_webkit_otp",
      fact_type: "known_issue",
      subject: "ios_payment_otp",
      predicate: "known_issue",
      object:
        "K1 iOS WebKit OTP autofill regression causes pay-step abandon; watch iOS device/os cuts on checkout.",
      confidence: 0.95,
      evidence_json: JSON.stringify(["base_context.md#known-issues-log"]),
      source_job_id: jobId,
    },
    {
      fact_id: "known_issue:k2_passport_android",
      fact_type: "known_issue",
      subject: "document_uploaded",
      predicate: "known_issue",
      object:
        "K2 Android passport capture failures elevated after Apr 2026 model update.",
      confidence: 0.9,
      evidence_json: JSON.stringify(["base_context.md#known-issues-log"]),
      source_job_id: jobId,
    },
    {
      fact_id: "known_issue:k3_mrz_non_latin",
      fact_type: "known_issue",
      subject: "document_uploaded",
      predicate: "known_issue",
      object:
        "K3 MRZ OCR weaker on non-Latin passports — higher retry_count expected.",
      confidence: 0.9,
      evidence_json: JSON.stringify(["base_context.md#known-issues-log"]),
      source_job_id: jobId,
    },
    {
      fact_id: "known_issue:k4_schengen_summer",
      fact_type: "known_issue",
      subject: "destination",
      predicate: "known_issue",
      object:
        "K4 Schengen summer slot scarcity (Apr–Jun) causes seasonal softness, not necessarily a product bug.",
      confidence: 0.85,
      evidence_json: JSON.stringify(["base_context.md#known-issues-log"]),
      source_job_id: jobId,
    },
    {
      fact_id: "known_issue:k5_whatsapp_nudge",
      fact_type: "known_issue",
      subject: "recovery",
      predicate: "known_issue",
      object:
        "K5 WhatsApp re-engagement nudge (Feb 2026) can lift funnel returns for previously dropped users.",
      confidence: 0.85,
      evidence_json: JSON.stringify(["base_context.md#known-issues-log"]),
      source_job_id: jobId,
    },
    {
      fact_id: "known_issue:k6_summer20",
      fact_type: "known_issue",
      subject: "coupon_applied",
      predicate: "known_issue",
      object:
        "K6 SUMMER20 campaign elevates coupon_applied and lowers realised value.",
      confidence: 0.85,
      evidence_json: JSON.stringify(["base_context.md#known-issues-log"]),
      source_job_id: jobId,
    },
    {
      fact_id: "known_issue:k7_app_745",
      fact_type: "known_issue",
      subject: "app_version",
      predicate: "known_issue",
      object:
        "K7 App 7.45.x rollout mid-quarter — expect minor funnel-timing shifts around rollout.",
      confidence: 0.8,
      evidence_json: JSON.stringify(["base_context.md#known-issues-log"]),
      source_job_id: jobId,
    },
  ];
}
