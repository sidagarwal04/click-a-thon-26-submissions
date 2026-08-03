/**
 * The Thread, Work Feed, and Visualization shapes the API returns.
 *
 * These mirror `thread_schemas.py`, `work_feed.py`, and the visualization half
 * of `schemas.py` exactly. Nothing here is derived or widened for the client's
 * convenience — where the chat surface wants a friendlier shape (a `role`, for
 * instance) that derivation lives in `to-chat-message.ts`, not in the contract.
 */

import type { DraftFinding } from '../draft-finding-panel';
import type { MetricComparison } from './investigation';

/* -------------------------------------------------------------------------- */
/* Workspace                                                                   */
/* -------------------------------------------------------------------------- */

export interface Group {
  readonly group_id: string;
  readonly name: string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly archived_at: string | null;
  /** Server-decided. Never re-derived from the caller's role. */
  readonly can_manage: boolean;
}

export interface Project {
  readonly project_id: string;
  readonly group_id: string;
  readonly name: string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly latest_activity_at: string;
  readonly archived_at: string | null;
  readonly can_manage: boolean;
}

export interface Page<T> {
  readonly items: readonly T[];
  readonly next_cursor: string | null;
}

/* -------------------------------------------------------------------------- */
/* Threads                                                                     */
/* -------------------------------------------------------------------------- */

/**
 * The server has no notion of an author "role" — it reports who wrote the
 * message and what kind of message it is, and those are different questions.
 * `kind` is a bare string because the vocabulary grows server-side; the two
 * values the surface renders differently are `user_question` and
 * `router_clarification`.
 */
export interface ThreadMessage {
  readonly message_id: string;
  readonly kind: string;
  readonly content: string;
  readonly created_at: string;
  readonly authored_by_user: boolean;
}

/**
 * What this actor may do to this Thread right now.
 *
 * Read, never computed. The lifecycle rule that a follow-up is legal only once
 * the latest Investigation is terminal lives on the server; a client that
 * re-derived it would be a second rule that can disagree with the first.
 */
export interface ThreadActions {
  readonly can_append_message: boolean;
  readonly can_archive: boolean;
  readonly can_restore: boolean;
  readonly can_delete: boolean;
  readonly can_cancel: boolean;
  readonly can_retry: boolean;
}

export interface ThreadRouting {
  readonly disposition: 'resolved' | 'unsupported' | 'ambiguous' | string;
  readonly scenario_key: string | null;
  readonly canonical_question: string | null;
  readonly clarification: string | null;
  /** The supported canonical questions, when the router could not resolve one. */
  readonly suggestions: readonly string[];
}

export interface ThreadUsage {
  readonly input_tokens: number;
  readonly output_tokens: number;
  readonly total_cost_usd: string;
  readonly latency_ms: number;
}

export interface ThreadApprovalState {
  readonly approval_id: string;
  readonly reason: string;
  readonly status: string;
  readonly failed_conditions: readonly string[];
  readonly requested_at: string;
  readonly decided_at: string | null;
  readonly decision_reason: string | null;
  readonly can_decide: boolean;
}

export type InvestigationStatus =
  | 'pending'
  | 'running'
  | 'evaluating'
  | 'awaiting_approval'
  | 'completed'
  | 'rejected'
  | 'failed'
  | 'cancelled';

export interface ThreadInvestigation {
  readonly investigation_id: string;
  readonly sequence: number;
  readonly status: InvestigationStatus;
  readonly parent_investigation_id: string | null;
  readonly retry_of_investigation_id: string | null;
  readonly created_at: string;
  readonly updated_at: string;
  readonly canonical_question: string;
  readonly finding: {
    readonly headline: string;
    readonly summary: string;
    readonly metrics: readonly MetricComparison[];
    readonly evidence_references: readonly string[];
  } | null;
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
  readonly approval: ThreadApprovalState | null;
  readonly citations: readonly EvidenceCitation[];
  readonly audit_delivery: 'complete' | 'pending';
  readonly usage: ThreadUsage;
}

export interface Thread {
  readonly thread_id: string;
  readonly project_id: string;
  readonly title: string;
  readonly status: 'draft' | 'active' | 'archived' | string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly latest_activity_at: string;
  readonly messages: readonly ThreadMessage[];
  /**
   * The latest attempt, retained for compatibility. `investigations` is the
   * ordered collection and is what the surface should render.
   */
  readonly investigation_id: string | null;
  readonly investigations: readonly ThreadInvestigation[];
  /** Where to resume the Work Feed from. Snapshot first, then tail. */
  readonly event_cursor: number;
  readonly usage: ThreadUsage;
  readonly routing: ThreadRouting | null;
  readonly actions: ThreadActions;
}

export interface ThreadSummary {
  readonly thread_id: string;
  readonly project_id: string;
  readonly title: string;
  readonly status: string;
  readonly latest_activity_at: string;
  readonly investigation_id: string | null;
}

/* -------------------------------------------------------------------------- */
/* Work Feed (SSE)                                                             */
/* -------------------------------------------------------------------------- */

/**
 * Every kind the server declares.
 *
 * Five of these — `investigation.started`, `investigation.status_changed`,
 * `investigation.completed`, `investigation.failed`, and
 * `visualization.tombstoned` — are declared but never emitted by the current
 * runtime. They are listed because the contract carries them, and deliberately
 * not depended on for any state transition.
 */
export type WorkFeedEventKind =
  | 'thread.message_added'
  | 'thread.routing_clarification'
  | 'thread.routing_resolved'
  | 'investigation.queued'
  | 'investigation.started'
  | 'investigation.status_changed'
  | 'investigation.cancel_requested'
  | 'investigation.cancelled'
  | 'investigation.completed'
  | 'investigation.failed'
  | 'investigation.retry_created'
  | 'agent.started'
  | 'agent.public_update'
  | 'agent.capability_used'
  | 'agent.handoff'
  | 'agent.completed'
  | 'approval.requested'
  | 'approval.decided'
  | 'finding.published'
  | 'visualization.requested'
  | 'visualization.started'
  | 'visualization.completed'
  | 'visualization.failed'
  | 'visualization.retry_requested'
  | 'visualization.tombstoned';

export interface MessageEventPayload {
  readonly type: 'message';
  readonly message_id: string;
  readonly message_kind: string;
}

export interface RoutingEventPayload {
  readonly type: 'routing';
  readonly disposition: string;
  readonly scenario_key: string | null;
  readonly suggestion_count: number;
}

export interface InvestigationEventPayload {
  readonly type: 'investigation';
  readonly investigation_id: string;
  readonly status: string;
  readonly parent_investigation_id: string | null;
  readonly retry_of_investigation_id: string | null;
  readonly failure_category: string | null;
}

export interface AgentEventPayload {
  readonly type: 'agent';
  readonly execution_id: string;
  readonly agent_id: string;
  readonly role: string;
  readonly capability_id: string | null;
  readonly from_agent_id: string | null;
  readonly to_agent_id: string | null;
  /** The public sentence. Never a prompt, a row, or a credential. */
  readonly summary: string | null;
  readonly provider: string | null;
  readonly model: string | null;
  readonly fallback_count: number;
  readonly latency_ms: number | null;
  readonly input_tokens: number;
  readonly output_tokens: number;
  readonly cost_usd: string;
}

export interface ApprovalEventPayload {
  readonly type: 'approval';
  readonly approval_id: string;
  readonly status: string;
  readonly failed_conditions: readonly string[];
}

export interface FindingEventPayload {
  readonly type: 'finding';
  readonly investigation_id: string;
  readonly citation_count: number;
}

export interface VisualizationEventPayload {
  readonly type: 'visualization';
  readonly visualization_id: string;
  readonly investigation_id: string;
  readonly status: string;
  readonly model: string | null;
  readonly api_version: string | null;
  readonly failure_category: string | null;
}

export type WorkFeedPayload =
  | MessageEventPayload
  | RoutingEventPayload
  | InvestigationEventPayload
  | AgentEventPayload
  | ApprovalEventPayload
  | FindingEventPayload
  | VisualizationEventPayload;

export interface ThreadEvent {
  readonly event_id: string;
  readonly tenant_id: string;
  readonly thread_id: string;
  readonly sequence: number;
  readonly kind: WorkFeedEventKind;
  readonly occurred_at: string;
  readonly payload: WorkFeedPayload;
}

/* -------------------------------------------------------------------------- */
/* Visualization                                                               */
/* -------------------------------------------------------------------------- */

export type VisualizationView =
  | 'auto'
  | 'line'
  | 'area'
  | 'bar'
  | 'horizontal_bar'
  | 'grouped_bar'
  | 'stacked_bar'
  | 'pie'
  | 'radar'
  | 'radial'
  | 'table'
  | 'metric_cards'
  | 'structured_text';

export type VisualizationStatus = 'pending' | 'generating' | 'ready' | 'failed' | 'tombstoned';

export type BriefActionKind = 'continue_conversation' | 'open_citation';

export interface BriefMetric {
  readonly label: string;
  /** The validated figure, unrounded. `display_value` is what a reader sees. */
  readonly exact_value: string;
  readonly display_value: string;
  readonly unit: string;
  readonly direction: 'up' | 'down' | 'flat' | 'not_applicable';
  readonly citation_ids: readonly string[];
}

export interface BriefComparison {
  readonly label: string;
  readonly previous_label: string | null;
  readonly previous_exact_value: string;
  readonly previous_display_value: string;
  readonly current_label: string | null;
  readonly current_exact_value: string;
  readonly current_display_value: string;
  readonly unit: string;
  readonly citation_ids: readonly string[];
}

export interface BriefSeriesPoint {
  readonly position: number;
  readonly label: string;
  readonly exact_value: string;
  readonly display_value: string;
  readonly citation_ids: readonly string[];
}

export interface BriefSeries {
  readonly label: string;
  readonly dimensions: readonly string[];
  readonly unit: string;
  readonly points: readonly BriefSeriesPoint[];
}

export interface BriefClaim {
  readonly kind: 'observed' | 'interpretation';
  readonly text: string;
  readonly citation_ids: readonly string[];
}

export interface BriefTimeRange {
  readonly start_label: string;
  readonly end_label: string;
}

export interface BriefAction {
  readonly action_id: string;
  readonly kind: BriefActionKind;
  readonly label: string;
}

/** The governed spec. Present even when the renderer never ran. */
export interface VisualizationBrief {
  readonly schema_version: '1.0';
  readonly investigation_id: string;
  readonly question: string;
  readonly headline: string;
  readonly summary: string;
  readonly view: VisualizationView;
  readonly metrics: readonly BriefMetric[];
  readonly comparisons: readonly BriefComparison[];
  readonly time_range: BriefTimeRange | null;
  readonly series: readonly BriefSeries[];
  readonly claims: readonly BriefClaim[];
  readonly caveats: readonly string[];
  readonly outcome_kind: 'confidence' | 'validation';
  readonly confidence: number | null;
  readonly actions: readonly BriefAction[];
}

export interface Visualization {
  readonly visualization_id: string;
  readonly investigation_id: string;
  readonly status: VisualizationStatus;
  readonly renderer_kind: string;
  readonly model: string | null;
  readonly api_version: string | null;
  /** The rendered generative UI. Opaque, and null until the render succeeds. */
  readonly c1_response: string | null;
  readonly input_tokens: number;
  readonly output_tokens: number;
  readonly cost_usd: string;
  readonly latency_ms: number;
  readonly failure_category: string | null;
  readonly retry_of_visualization_id: string | null;
  readonly fallback_brief: VisualizationBrief | null;
  readonly created_at: string;
  readonly updated_at: string;
  readonly erased_at: string | null;
  readonly erasure_category: string | null;
}

/** What the server resolved a stored safe action to. */
export interface VisualizationActionResult {
  readonly kind: BriefActionKind | string;
  readonly citation_id: string | null;
  readonly thread_id: string | null;
  readonly investigation_id: string | null;
}

/* -------------------------------------------------------------------------- */
/* Citations and agents                                                        */
/* -------------------------------------------------------------------------- */

export interface CitationFilter {
  readonly member: string;
  readonly operator: string;
  readonly values: readonly string[];
}

export interface EvidenceCitation {
  readonly citation_id: string;
  readonly metric: string;
  readonly filters: readonly CitationFilter[];
  readonly period: string | null;
  readonly grain: string | null;
  readonly producing_execution_id: string | null;
  readonly aggregate_value: string;
  readonly evaluator_outcome:
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
  readonly state: 'active' | 'unavailable' | 'tombstoned';
}

/**
 * What a citation resolves to once its evidence was deliberately erased.
 *
 * Identity, category, timestamp — and nothing else. Erased evidence is a state
 * to be shown, not a request that failed.
 */
export interface CitationTombstone {
  readonly state: 'tombstoned';
  readonly citation_id: string;
  readonly category: string;
  readonly erased_at: string;
}

export type ResolvedCitation = EvidenceCitation | CitationTombstone;

export const isTombstone = (value: ResolvedCitation): value is CitationTombstone =>
  value.state === 'tombstoned' && !('metric' in value);

export interface AgentCapability {
  readonly capability_id: string;
  readonly version: string;
  readonly display_name: string;
  readonly description: string;
}

export interface Agent {
  readonly agent_id: string;
  readonly role: string;
  readonly version: string;
  readonly display_name: string;
  readonly description: string;
  readonly enabled: boolean;
  readonly evaluation_status: string;
  readonly capabilities: readonly AgentCapability[];
}
