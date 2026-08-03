// Mirrors contracts/evidence_bundle.schema.json. Lane D renders this; it never computes metrics.
export type Status = "culprit" | "contributor" | "normal";

export interface Anomaly {
  detected: boolean;
  observed: number;
  expected: number;
  abs_delta: number;
  pct_delta: number;
  score: number;
  direction: "drop" | "spike";
}

export interface Factor {
  factor: string;
  contribution_pct: number;
  from: number;
  to: number;
}

export interface DrilldownNode {
  depth: number;
  split_dimension: string;
  segment: Record<string, string>;
  metric_from?: number;
  metric_to?: number;
  contribution_pct: number;
  status: Status;
  query_id: string;
}

export interface RuledOut {
  hypothesis: string;
  evidence: string;
  query_id: string;
}

export interface Window {
  start: string;
  end: string;
}

export interface EvidenceBundle {
  investigation_id: string;
  created_at: string;
  metric: string;
  target_window?: Window;
  anomaly: Anomaly;
  factor_decomposition: { method: string; primary_factor: string; factors: Factor[] };
  drilldown: DrilldownNode[];
  localized_segment: Record<string, string>;
  ruled_out: RuledOut[];
  narrative?: string | null;
  trace_url?: string | null;
}

// GET /health — is the RCA engine running the real pipeline, serving the fixture, or is the
// datastore unreachable (offline: engine ready but ClickHouse down — results are sample data)?
export interface Health {
  ok: boolean;
  engine: "live" | "fixture" | "offline";
  dataset?: { target: string; history: string; available?: string[] };
  langfuse: { enabled: boolean; host: string };
}

// GET /bundles — flattened investigation rows for the history panel.
export interface InvestigationRow {
  investigation_id: string;
  created_at: string;
  metric: string;
  window_start: string;
  window_end: string;
  primary_factor: string;
  localized_segment: string; // JSON string
  detected: number; // 0 | 1
  narrated: number; // 0 | 1
  trace_id?: string;
  session_id?: string;
}
