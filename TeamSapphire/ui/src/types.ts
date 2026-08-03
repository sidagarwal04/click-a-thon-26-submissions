// Mirrors the engine's dataclasses exactly (engine/investigate.py,
// engine/decompose.py, engine/localize.py, engine/narrate.py, engine/db.py).
// This is the API contract: GET /api/v1/investigation returns this shape
// verbatim from disk, so the fixture and the live endpoint must match.

export type Classification = "localized" | "global" | "unattributed";
export type Direction = "drop" | "spike";
export type Factor = "requests" | "fill_rate" | "render_rate" | "ecpm";
// "not_applicable": the dimension cannot vary with this metric at all — e.g.
// fill rate within campaign_type, which is 1.0 for every value by construction
// because campaign_type only exists once a request has filled. Distinct from
// "inconclusive", which means we asked a real question and could not settle it.
export type Verdict = "responsible" | "uniform" | "inconclusive" | "not_applicable";

export interface Trigger {
  scope: string; // "global" or "dim_name=dim_value"
  metric: string;
  direction: Direction;
  hours: number;
  mean_pct_change: number;
  peak_z: number;
}

export interface FactorMove {
  factor: Factor;
  actual: number;
  baseline: number;
  pct_change: number;
  log_change: number;
  contribution_share: number; // percent; can exceed 100 or go negative when factors offset
  contribution_pct_points: number;
}

// Raw funnel counts pass through alongside the four derived factors — already
// summed by the query, not recomputed. Lets a consumer render the funnel
// (requests -> fills -> impressions -> clicks) without multiplying a rate
// back out client-side.
export interface FactorTotals {
  requests: number;
  fill_rate: number;
  render_rate: number;
  ecpm: number;
  revenue: number;
  fills: number;
  impressions: number;
  clicks: number;
}

export interface Decomposition {
  window_start: string;
  window_end: string;
  baseline_weeks_used: number;
  actual: FactorTotals;
  baseline: FactorTotals;
  revenue_pct_change: number;
  factors: FactorMove[];
  primary_factor: Factor;
  identity_residual: number; // ~0 proves the decomposition is complete
}

export interface SegmentMove {
  dim_name: string;
  dim_value: string;
  actual: number;
  baseline: number;
  delta: number;
  pct_change: number;
  expected_delta_if_uniform: number;
  excess: number;
  excess_share: number;
  excess_of_total: number;
}

// Full form (event.responsible[]) — includes per-value detail.
export interface DimensionVerdict {
  dim_name: string;
  verdict: Verdict;
  top_value: string;
  top_excess_share: number;
  top_excess_of_total: number;
  reason: string;
  segments: SegmentMove[];
}

// Ledger form (event.ruled_out[]) — DimensionVerdict.summary(), no segments.
export interface RuledOutEntry {
  dim_name: string;
  verdict: Verdict;
  top_value: string;
  top_excess_share: number;
  top_excess_of_total: number;
  reason: string;
}

// Stage 4b (engine/characterize.py) — the shape of the transition, not just
// its size. "step" = toggled at that hour; "gradual" = ramped/degraded.
export interface Transition {
  at_hour: string;
  before: number;
  after: number;
  change: number;
  step_fraction: number; // share of the total move landing in this one hour
  shape: "step" | "gradual";
  aligns_to_day_boundary: boolean;
}

export interface Signature {
  factor: Factor;
  scope: string; // "global" or "dim_name=dim_value"
  onset: Transition | null;
  recovery: Transition | null;
  duration_hours: number | null;
  held_steady: string[]; // other factors that stayed flat through the window
  reading: string; // prose: what the shape is consistent with, never the cause
  rules_out: string[];
}

export interface Event {
  start: string;
  end: string;
  hours: number;
  classification: Classification;
  severity: number; // percent-hours; events are sorted by this, descending
  headline: string;
  primary_factor: Factor;
  revenue_pct_change: number;
  trigger_count: number;
  triggers: Trigger[]; // top 8, strongest first
  decomposition: Decomposition;
  responsible: DimensionVerdict[]; // empty = no segment responsible, a real finding
  ruled_out: RuledOutEntry[];
  signature: Signature | null;
}

export interface Narration {
  text: string;
  model: string;
  all_numbers_verified: boolean; // directly scored — surface, don't bury
  unverified_numbers: string[];
}

export interface QueryEvidence {
  label: string;
  sql: string;
  query_ms: number;
  rows_read: number;
  rows_returned: number;
}

// Stage 4c (engine/intersect.py) — two-dimension anomalies invisible to any
// single-dimension scan by construction (the cell moved >=2x more than either
// parent). No `scope` field on the wire — Python's asdict() skips the
// @property; derive the "dim_a=value_a x dim_b=value_b" label in the UI.
export interface CompoundFinding {
  day: string;
  dim_a: string;
  value_a: string;
  dim_b: string;
  value_b: string;
  metric: string;
  actual: number;
  baseline: number;
  pct_change: number;
  parent_a_pct: number;
  parent_b_pct: number;
  requests: number;
}

export interface CompoundLedgerEntry {
  pair: string; // "dim_a x dim_b", or "(summary)" for the final tally entry
  cells_examined?: number;
  flagged?: number;
  query_ms?: number;
  rows_read?: number;
  novel?: number; // present only on the "(summary)" entry
  inside_known_windows?: number;
}

export interface Investigation {
  window_start: string;
  window_end: string;
  trace_url: string | null;
  total_query_ms: number;
  total_rows_read: number;
  discarded_noise: number;
  suppressed_low_severity: number;
  events: Event[];
  compound_findings: CompoundFinding[]; // investigation-wide, not per-event
  compound_ledger: CompoundLedgerEntry[];
  narrations: Record<string, Narration>; // keyed by 1-based event index, as a string
  queries: QueryEvidence[];
  runtime_seconds: number;
}
