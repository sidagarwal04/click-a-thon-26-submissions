export type ReportMode = "overview" | "ask" | "run";

export type ReportEvidence = {
  claim: string;
  query_id: string;
  confidence: "high" | "medium" | "low" | string;
};

export type FeatureCard = {
  job_id: string;
  feature_slug: string;
  table_name: string;
  event_names: string[];
  success_event: string;
  primary_entity: string;
  row_count: number | null;
  langfuse_trace_id: string;
  langfuse_trace_url: string;
  schema_preview: string;
  order_by: string[];
  partition_by: string;
  engine: string;
  context_diff_excerpt: string;
};

export type AskCard = {
  job_id: string;
  question: string;
  short_answer: string;
  feature_slug: string;
  key_findings: string[];
  evidence: ReportEvidence[];
  recommended_actions: string[];
  caveats: string[];
  langfuse_trace_id: string;
  langfuse_trace_url: string;
};

export type ReportContradiction = {
  id: string;
  summary: string;
};

export type PipelineReport = {
  generated_at: string;
  mode: ReportMode;
  /** Selected deep-dive job, if any */
  job_id: string | null;
  title: string;
  subtitle: string;
  features: FeatureCard[];
  recent_asks: AskCard[];
  /** Deep-dive ask/run payload */
  focus: AskCard | FeatureCard | null;
  contradictions: ReportContradiction[];
  context_changelog: string;
  stats: {
    instrumentation_runs: number;
    ask_jobs: number;
    features_instrumented: number;
  };
  how_to: string[];
};
