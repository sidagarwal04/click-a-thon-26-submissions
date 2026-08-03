export type FieldProfile = {
  path: string;
  count: number;
  null_count: number;
  types: string[];
  sample_values: unknown[];
};

export type EventProfile = {
  feature_slug: string;
  row_count: number;
  event_counts: Record<string, number>;
  event_order: string[];
  fields: FieldProfile[];
};

export type FeatureManifest = {
  feature_slug: string;
  feature_name: string;
  primary_entity: string;
  workflow_type:
    | "funnel"
    | "revenue_addon"
    | "referral_loop"
    | "recovery"
    | "generic";
  event_order: string[];
  success_event: string | null;
  metric_hints: string[];
  context_notes: string[];
};

export type SchemaPlan = {
  database: "silver";
  table_name: string;
  engine: string;
  partition_by: string;
  order_by: string[];
  ttl: string;
  columns: Array<{
    name: string;
    type: string;
    source_path: string | null;
    reason: string;
  }>;
  materialized_views: Array<{
    name: string;
    target_table: string;
    target_table_sql: string;
    view_sql: string;
    purpose: string;
    dimensions: string[];
    metrics: string[];
  }>;
};

export type MappingPlan = {
  table_name: string;
  mappings: Array<{
    column: string;
    source_path: string | null;
    transform: string;
  }>;
};

export type SilverLoadValidation = {
  passed: boolean;
  failures: string[];
  expected_rows: number;
  actual_rows: number;
  expected_events: string[];
  actual_events: string[];
  timestamp_min_max: string;
};

export type SilverLoadReport = {
  job_id: string;
  table: string;
  inserted_rows: number;
  validation: SilverLoadValidation;
  loaded_at: string;
};
