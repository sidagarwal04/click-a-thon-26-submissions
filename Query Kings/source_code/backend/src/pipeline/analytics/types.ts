import { GeneratedContextRegistry } from "../context.js";

export type QueryIntent = {
  original_question: string;
  normalized_question: string;
  feature_hints: string[];
  metric_hints: string[];
  table_hints: string[];
  segment_hints: string[];
  time_hints: string[];
  requested_analyses: Array<
    | "metric_lookup"
    | "trend"
    | "funnel"
    | "root_cause"
    | "segment_comparison"
    | "latency"
    | "data_quality"
    | "schema_explanation"
    | "open_ended"
  >;
  ambiguity_notes: string[];
};

export type PmRelevantContext = {
  features: GeneratedContextRegistry["features"];
  workflows: GeneratedContextRegistry["workflows"];
  columns: GeneratedContextRegistry["columns"];
  metrics: GeneratedContextRegistry["metrics"];
  joins: GeneratedContextRegistry["joins"];
  schema_quality: GeneratedContextRegistry["schema_quality"];
  contradictions: GeneratedContextRegistry["contradictions"];
  base_context_excerpt: string;
  retrieval_notes: string[];
};

export type AnalysisPlan = {
  interpreted_question: string;
  answer_type: QueryIntent["requested_analyses"][number];
  tables: string[];
  joins: Array<{
    left_table: string;
    left_column: string;
    right_table: string;
    right_column: string;
    reason: string;
  }>;
  queries: PlannedQuery[];
  evidence_standard: {
    needs_comparison: boolean;
    needs_segment_cut: boolean;
    min_rows: number;
    can_answer_if_empty: boolean;
  };
  assumptions: string[];
  risks: string[];
};

export type PlannedQuery = {
  id: string;
  purpose: string;
  sql_intent: string;
  expected_columns: string[];
  priority: "required" | "nice_to_have";
};

export type GeneratedSqlQuery = PlannedQuery & {
  sql: string;
};

export type SqlGuardrailResult = {
  passed: boolean;
  repaired_sql: string;
  warnings: string[];
};

export type QueryResult = {
  query_id: string;
  purpose: string;
  sql: string;
  rows: Record<string, unknown>[];
  row_count: number;
  statistics?: Record<string, unknown>;
};

export type ResultEvaluation = {
  passed: boolean;
  needs_repair: boolean;
  repair_notes: string[];
  evidence_gaps: string[];
};

export type EvidencePack = {
  question: string;
  intent: QueryIntent;
  context: PmRelevantContext;
  plan: AnalysisPlan;
  query_results: QueryResult[];
  evaluation: ResultEvaluation;
};

export type InsightDraft = {
  short_answer: string;
  key_findings: string[];
  evidence: Array<{
    claim: string;
    query_id: string;
    confidence: "high" | "medium" | "low";
  }>;
  recommended_actions: string[];
  caveats: string[];
};

export type FinalAnalyticsAnswer = InsightDraft & {
  critic_notes: string[];
  artifact_root: string;
  trace_id: string;
};
