export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export interface RunSummary {
  id: string;
  name: string;
  timestamp: string;
  updated_at: string | null;
  latency: number | null;
  total_cost: number | null;
  environment: string | null;
  release: string | null;
  version: string | null;
  user_id: string | null;
  session_id: string | null;
  tags: string[];
  status: string;
  error_count: number;
  observation_count: number;
  feature: string | null;
  pipeline_run_id: string | null;
}

export interface Observation {
  id: string;
  trace_id: string;
  parent_observation_id: string | null;
  name: string;
  type: string;
  start_time: string;
  end_time: string | null;
  completion_start_time: string | null;
  latency: number | null;
  level: string;
  status_message: string | null;
  input: JsonValue;
  output: JsonValue;
  metadata: Record<string, JsonValue>;
  model: string | null;
  model_parameters: Record<string, JsonValue>;
  usage: Record<string, JsonValue>;
  cost: number | null;
  cost_details: Record<string, JsonValue>;
  time_to_first_token: number | null;
  prompt_name: string | null;
  prompt_version: number | null;
  offset_ms: number;
}

export interface RunDetail extends RunSummary {
  input: JsonValue;
  output: JsonValue;
  metadata: Record<string, JsonValue>;
  scores: JsonValue[];
  observations: Observation[];
  html_path: string | null;
}

export interface RunsResponse {
  data: RunSummary[];
  meta: { page: number; limit: number; total_items: number; total_pages: number };
}

export interface FeatureUploadResult {
  feature_folder: string;
  status: "uploaded";
  files: string[];
}

export interface ProcessFeatureResult {
  run_id: string;
  status: string;
  feature: string;
  table_created: string | null;
  rows_loaded: number;
  context_version: number | null;
  insights: Array<{ title: string; confidence: string }>;
  langfuse_trace_id: string | null;
}

export interface RunReport {
  summary: {
    run_id: string;
    status: string;
    feature: string;
    table_created: string | null;
    rows_loaded: number;
    context_version: number | null;
    insights: Array<{ title: string; confidence: string }>;
    langfuse_trace_id: string | null;
  };
  artifacts: Record<string, JsonValue>;
}

export interface ContextDocument {
  version: number;
  run_id: string | null;
  entities: Array<Record<string, JsonValue>>;
  relationships: Array<Record<string, JsonValue>>;
  metrics: Array<Record<string, JsonValue>>;
  known_issues: Array<Record<string, JsonValue>>;
  naming_conventions: string[];
  conflicts: JsonValue[];
  source: string;
}

export type AsklysIntent = "funnel" | "trend" | "user_path" | "text";

export interface AsklysContextItem {
  kind: "table" | "column";
  label: string;
  table: string;
  column: string | null;
  data_type: string | null;
  description: string;
}

export interface AsklysContextResponse {
  database: string;
  connected: boolean;
  items: AsklysContextItem[];
}

export interface AsklysContextRef {
  kind: "table" | "column";
  table: string;
  column?: string | null;
}

export interface AsklysFunnelStep {
  name: string;
  value: number;
  conversion_rate: number;
  previous_conversion_rate: number;
  dropoff: number;
  dropoff_rate: number;
}

export interface AsklysTrendSeries {
  name: string;
  points: Array<{ x: string; y: number }>;
}

export interface AsklysPathLink {
  source: string;
  target: string;
  value: number;
}

export interface AsklysResponse {
  intent: AsklysIntent;
  title: string;
  answer: string;
  visualization: {
    kind: AsklysIntent;
    funnel: AsklysFunnelStep[];
    series: AsklysTrendSeries[];
    paths: AsklysPathLink[];
  } | null;
  sql: string | null;
  columns: string[];
  rows: Array<Record<string, JsonValue>>;
  database: string;
  context_used: string[];
  analysis_steps: string[];
  query_attempts: number;
  model: string;
  langfuse_trace_id: string | null;
}

export type AsklysActivityEvent = {
  type: "status";
  stage: string;
  message: string;
  detail?: string;
  sql?: string;
};

export type AsklysStreamEvent =
  | AsklysActivityEvent
  | { type: "complete"; data: AsklysResponse }
  | { type: "error"; message: string };
