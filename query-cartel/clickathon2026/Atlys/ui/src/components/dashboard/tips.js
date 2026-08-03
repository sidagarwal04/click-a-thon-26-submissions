/**
 * Shared tooltip copy — "what does this card/element actually tell you".
 * Single source of truth so explanations stay consistent across tabs.
 */

/** Run lifecycle states shown in Inspect (runs table + approval queue). */
export const STATE_TIP = {
  proposed: 'Schema proposed — waiting for approval. Nothing has touched ClickHouse yet.',
  running: 'Spec run in progress — the event chain is being produced right now.',
  approved: 'Schema approved — the pipeline created the table and generated an insight.',
  rejected: 'Schema rejected — the run stopped; no table was created.',
  failed: 'Run failed — an agent step errored. Open the chain to see where.',
  aborted: 'Run aborted — it exceeded the per-run event cap (flood guard).',
  unknown: 'State not recorded for this run.',
}

/** Insight evidence kinds (analytics playbook P1–P6 + MV). */
export const KIND_TIP = {
  funnel: 'Funnel step-through: unique users reaching each event step, in spec order.',
  overview: 'Event overview: total events and distinct users per event type.',
  segment: 'Segment skew: funnel completion split by OS / device / geo / destination.',
  timing: 'Completion timing: p50/p90 of the final step (or numeric feature columns).',
  cross_funnel: 'Cross-funnel: feature completers who also converted on purchase_completed.',
  funnel_timing: 'Per-user first→last step latency (capped sample).',
  mv_funnel: 'Rollup from the mv_funnel_daily materialized view — cheap segment breakdown.',
}

/** Event types in the run chain — what each one records. */
export const EVENT_TIP = {
  'spec.run.requested': 'A new spec run was started (from chat or the MCP tool).',
  'spec.ingested': 'The spec files were read into the pipeline.',
  'schema.proposed': 'Schema agent proposed a table design from the spec — awaiting approval.',
  'schema.approved': 'Approval received — the schema is authorized to be created.',
  'schema.rejected': 'Approval denied — the run stops here.',
  'schema.created': 'The table was actually created in ClickHouse.',
  'context.checked': 'Context agent checked the base context against the new schema.',
  'context.updated': 'Context snapshot updated so analytics reasons from the freshest context.',
  'insight.created': 'Analytics agent produced the PM-ready insight card.',
  'tool.called': 'The chat agent invoked an MCP tool (read or write).',
  'context.update.proposed': 'A human-proposed context edit is pending.',
  'run.aborted': 'The run was cut short (e.g. per-run event cap).',
}

/** Inspect runs-table column meanings. */
export const RUN_COLUMN_TIP = {
  run: 'Internal run id (UUID). Click a row to load its event chain below.',
  feature: 'The feature spec directory this run belongs to.',
  state: 'Lifecycle state of the run — see the badge for details.',
  events: 'How many events this run persisted to the event log.',
  duration: 'Wall time from the first to the last event in the run.',
  trace: 'Langfuse trace for this run — the full agent reasoning trail.',
  created: 'When the run started.',
}

/** Inspect tool-calls table column meanings. */
export const TOOL_COLUMN_TIP = {
  tool: 'MCP tool invoked by the chat agent.',
  arguments: 'Arguments sent to the tool (truncated for display).',
  trace: 'Langfuse trace the tool call belongs to.',
  time: 'When the tool was called.',
}

/** Schema timeline summary strip meanings. */
export const TIMELINE_SUMMARY_TIP = {
  changes: 'Total schema changes recorded across all runs.',
  tables: 'Tables created from feature specs.',
  columns: 'Columns added to feature tables.',
}
