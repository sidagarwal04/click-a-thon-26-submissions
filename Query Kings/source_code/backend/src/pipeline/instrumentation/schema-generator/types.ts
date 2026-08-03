import { EventProfile, FeatureManifest, SchemaPlan } from "../types.js";
import { ContextBundle, RelevantContextBundle } from "../../context.js";

export type RunSchemaGeneratorInput = {
  jobId: string;
  featureSlug: string;
  manifest: FeatureManifest;
  eventProfile: EventProfile;
  context: ContextBundle;
  artifactRoot: string;
  executionFeedback?: string[];
};

export type SchemaColumnDraft = {
  name: string;
  type: string;
  source_path: string | null;
  reason: string;
};

export type SchemaDesignDraft = {
  table_name?: string;
  engine?: string;
  order_by?: string[];
  partition_by?: string;
  ttl?: string;
  columns?: SchemaColumnDraft[];
  materialized_view_recommendations?: Array<{
    purpose: string;
    dimensions?: string[];
    metrics?: string[];
  }>;
  context_assumptions?: Array<{
    claim: string;
    evidence: string;
    trusted: boolean;
  }>;
  rationale?: string[];
};

export type SchemaCriticDraft = {
  verdict?: "pass" | "revise";
  issues?: string[];
  revision_instructions?: string[];
  rationale?: string[];
};

export type SchemaDesignLoop = {
  mode: "llm_assisted" | "deterministic_fallback";
  iterations: Array<{
    iteration: number;
    actor:
      | "schema_designer"
      | "schema_critic"
      | "schema_designer_revision"
      | "deterministic_guardrail"
      | "schema_repair";
    summary: string;
    issues: string[];
  }>;
  final_plan: SchemaPlan;
};
