/** Filter object for RCA chart endpoints — same shape drives every visualization. */
export type Granularity = "hour" | "day";

export interface RcaFilters {
  from: string;
  to: string;
  os_versions: string[];
  granularity: Granularity;
}

export interface RcaReportSummary {
  id: string;
  title: string;
  created_at: string;
  status: string;
  metric_id: string;
  window: { start: string; end: string };
  // absent when the verdict is not_reproducible — no finding means no peak z to report
  peak_abs_z?: number;
}

export interface RcaTrigger {
  metric_id: string;
  alert_title: string;
  alert_body: string;
  window: { start: string; end: string };
  dimension_hint?: string;
  // absent when the verdict is not_reproducible — no finding means no global summary to report
  actual?: number;
  expected?: number;
  peak_abs_z?: number;
  hours?: number;
}

export interface RcaCandidate {
  dim_name: string;
  dim_value: string;
  avg_actual: number;
  avg_expected: number;
  peak_abs_z: number;
  contribution: number;
}

export interface RcaRuledOut {
  segment: string;
  reason: string;
}

export interface RcaReport extends RcaReportSummary {
  trigger: RcaTrigger;
  sections: {
    what_went_wrong: string;
    why_it_happened: string;
    supporting_data_summary: string;
  };
  ruled_out: RcaRuledOut[];
  candidates: RcaCandidate[];
  // null when the verdict is not_reproducible — no finding means no holdout was ever run
  holdout: {
    candidate: Array<{ dim_name: string; dim_value: string }>;
    // null when the complement matched zero rows (candidate is ~all the traffic in this
    // window) — the comparison genuinely couldn't be made
    residual_actual: number | null;
    residual_delta: number | null;
    candidate_delta: number;
    verdict: string;
  } | null;
  ledger: Record<string, unknown>;
}

export interface GlobalSeriesRow {
  bucket: string;
  actual: number;
  expected: number;
  z_score: number;
}

export interface SegmentSeriesRow {
  bucket: string;
  os_version: string;
  fill_rate: number;
  expected: number;
}

export interface ContributionRow {
  segment: string;
  contribution: number;
  peak_abs_z: number;
  avg_actual: number;
  avg_expected: number;
}
