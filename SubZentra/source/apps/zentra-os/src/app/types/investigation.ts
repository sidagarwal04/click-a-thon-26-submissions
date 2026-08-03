/**
 * Shapes the API returns.
 *
 * These mirror the governed contract exactly — nothing here is derived or
 * widened for the client's convenience.
 */

import type { DraftFinding } from '../draft-finding-panel';

export interface DependencyStatus {
  readonly status: 'ready' | 'unavailable';
}

export interface ReadinessResponse {
  readonly status: 'ready' | 'degraded';
  readonly dependencies: Readonly<Record<string, DependencyStatus>>;
}

export interface IdentityContext {
  readonly user_id: string;
  readonly tenant_id: string;
  readonly email: string;
  readonly tenant_name: string;
  readonly role: 'owner' | 'admin' | 'member' | 'viewer';
}

export interface MetricComparison {
  readonly metric: string;
  readonly previous_value: string;
  readonly previous_label: string | null;
  readonly current_value: string;
  readonly current_label: string | null;
  readonly unit: string;
}

export interface Investigation {
  readonly investigation_id: string;
  readonly canonical_question: string;
  /** Present only on Investigations started before free-text questions. */
  readonly scenario_key: string | null;
  readonly status:
    | 'pending'
    | 'running'
    | 'evaluating'
    | 'awaiting_approval'
    | 'completed'
    | 'rejected'
    | 'failed'
    | 'cancelled';
  readonly version: number;
  readonly evaluation_attempts: number;
  readonly created_at: string;
  readonly updated_at: string;
  readonly finished_at: string | null;
  readonly finding: {
    readonly headline: string;
    readonly summary: string;
    readonly metrics: readonly MetricComparison[];
    readonly evidence_references: readonly string[];
  } | null;
  // Present only for Investigations that ran through the Insight Agent.
  // Null means legacy narrative, not missing evidence.
  readonly draft_finding: DraftFinding | null;
  readonly outcome:
    | {
        readonly kind: 'validation';
        readonly passed: boolean;
        readonly checks: readonly string[];
        readonly issues: readonly string[];
      }
    | {
        readonly kind: 'confidence';
        readonly score: number;
        readonly calibration_method: string;
      }
    | null;
  readonly pending_approval: {
    readonly approval_id: string;
    readonly reason: string;
    readonly requested_at: string;
    readonly can_decide: boolean;
    // Every condition the deterministic policy found failing, in its own
    // vocabulary — the same words the API and Replay use.
    readonly failed_conditions: readonly string[];
  } | null;
  readonly timeline: readonly {
    readonly entry_id: string;
    readonly event_type: string;
    readonly status: string;
    readonly created_at: string;
    readonly artifact_references: readonly string[];
    readonly delivery: 'complete' | 'pending';
    readonly agent_id: string | null;
    readonly step: number | null;
    readonly model: string | null;
    // The rungs that failed before `model` answered, and why a
    // publication decision went the way it did.
    readonly fallbacks: readonly string[];
    readonly failed_conditions: readonly string[];
    readonly latency_ms: number | null;
    readonly total_cost_usd: string | null;
  }[];
  readonly audit_delivery: 'complete' | 'pending';
  // Server-decided. Asking our own role here would be a second
  // authorisation rule that can disagree with the one that applies.
  readonly can_delete_evidence: boolean;
}

export type RejectionReason =
  | 'insufficient_evidence'
  | 'incorrect_interpretation'
  | 'policy_mismatch'
  | 'needs_more_analysis';

/** One governed measure or dimension this tenant may be asked about. */
export interface CatalogMember {
  readonly name: string;
  readonly type: string;
  readonly description: string | null;
  /** Dimensions only, and only where few enough to enumerate. */
  readonly values: readonly string[];
}

export interface CatalogSummary {
  readonly measures: readonly CatalogMember[];
  readonly dimensions: readonly CatalogMember[];
}
