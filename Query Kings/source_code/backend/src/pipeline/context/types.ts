import { EventProfile, SchemaPlan } from "../instrumentation/types.js";

export type ContextBundle = {
  baseContext: string;
  existingDdl: string;
  instrumentationNotes: string;
  generatedContext: GeneratedContextRegistry;
};

export type RelevantContextBundle = {
  similar_workflows: GeneratedContextRegistry["workflows"];
  column_type_precedents: GeneratedContextRegistry["columns"];
  reusable_metrics: GeneratedContextRegistry["metrics"];
  recommended_joins: GeneratedContextRegistry["joins"];
  schema_quality: GeneratedContextRegistry["schema_quality"];
  contradictions: GeneratedContextRegistry["contradictions"];
  retrieval_notes: string[];
};

export type GeneratedContextRegistry = {
  version: number;
  updated_at: string | null;
  features: Array<{
    feature_slug: string;
    table_name: string;
    primary_entity: string;
    event_names: string[];
    success_event: string | null;
    metric_hints: string[];
    added_at: string;
  }>;
  contradictions: Array<{
    id: string;
    summary: string;
    evidence: string;
  }>;
  columns: Array<{
    table_name: string;
    column_name: string;
    clickhouse_type: string;
    source_path: string | null;
    semantic_role: string;
    is_nullable: boolean;
  }>;
  workflows: Array<{
    feature_slug: string;
    table_name: string;
    workflow_type: string;
    start_event: string | null;
    success_event: string | null;
    primary_entity: string;
    primary_entity_column: string;
    segment_columns: string[];
  }>;
  metrics: Array<{
    metric_name: string;
    feature_slug: string;
    formula_sql: string;
    grain: string;
    segment_columns: string[];
  }>;
  joins: Array<{
    left_table: string;
    left_column: string;
    right_table: string;
    right_column: string;
    grain: string;
    confidence: number;
  }>;
  schema_quality: Array<{
    table_name: string;
    order_by: string[];
    partition_by: string;
    ttl: string;
    materialized_views: string[];
    validation_passed: boolean;
  }>;
};

export type UpdateGeneratedContextInput = {
  job_id: string;
  feature_slug: string;
  table_name: string;
  primary_entity: string;
  workflow_type: string;
  event_names: string[];
  success_event: string | null;
  metric_hints: string[];
  validation: Record<string, unknown>;
  schema_plan: SchemaPlan;
  event_profile: EventProfile;
};

export const emptyRegistry: GeneratedContextRegistry = {
  version: 1,
  updated_at: null,
  features: [],
  contradictions: [
    {
      id: "base_context_eta_name_mismatch",
      summary:
        "Base context mentions visa_issuance_eta_days, while the loaded application_started DDL exposes eta_shown.",
      evidence:
        "base_context.md defines visa_issuance_eta_days; data/ddl.sql defines application_started.eta_shown Nullable(String).",
    },
    {
      id: "conversion_denominator_ambiguity",
      summary:
        "Base context defines leadership conversion as purchases divided by sessions, but funnel conversion as purchases divided by application_started users.",
      evidence:
        "Metric definitions contain both formulas; analytics must choose based on question type.",
    },
  ],
  columns: [],
  workflows: [],
  metrics: [],
  joins: [],
  schema_quality: [],
};
