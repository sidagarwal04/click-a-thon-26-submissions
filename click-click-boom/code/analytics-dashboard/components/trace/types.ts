export type EventKind = 'generation' | 'reasoning' | 'tool_call' | 'approved' | 'execution' | 'context_update' | 'span_start' | 'span_end' | 'log' | 'trace_start' | 'trace_end';

export type ToolFamily =
  | 'sql_query' | 'schema' | 'tables'
  | 'context_lookup' | 'context_index'
  | 'skill_file' | 'skill_list'
  | 'python' | 'scratch'
  | 'generation' | 'span' | 'other';

export interface AgentEvent {
  id: string;
  ts: number;
  kind: EventKind;
  step: string;
  agent?: string;
  spec?: string;
  trace_id?: string;
  trace_url?: string;
  input?: unknown;
  output?: unknown;
  reasoning?: string;         // caller-derived summary (from agent's JSON rationale)
  model_reasoning?: string;   // raw LLM chain-of-thought
  usage?: { input?: number; output?: number; reasoning?: number; total?: number };
  n_tool_calls?: number;
  execution_time_ms?: number;
}

// Parsed output shapes per tool
export interface SqlOutput {
  columns?: string[];
  rows?: Record<string, unknown>[];
  execution_time_ms?: number;
  scratch_file?: string;
  preview?: Record<string, unknown>[];
  row_count?: number;
  hit_cap?: boolean;
}

export interface SchemaOutput {
  columns?: { column: string; type: string }[];
  execution_time_ms?: number;
}

export interface TablesOutput {
  tables?: { table: string; engine: string; row_count: number }[];
  execution_time_ms?: number;
}

export interface ContextSection {
  section: string;
  title?: string;
  summary?: string;
  body?: string;
  confidence?: number;
}

export interface PythonOutput {
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  truncated?: boolean;
}

export interface SkillFileOutput {
  content?: string;
  path?: string;
}

// orchestrator/pipeline.py's "executed" step output -- what actually landed
// in ClickHouse (real DDL + row count), not just "it worked".
export interface ExecutionOutput {
  base_table?: string;
  base_table_ddl?: string;
  rows_inserted?: number;
  materialized_views?: { name: string; ddl: string }[];
}

// orchestrator/pipeline.py's "context_updated" step output -- every section
// the chronicler wrote/updated on this run.
export interface ContextUpdateOutput {
  sections?: { section: string; title?: string; is_new?: boolean; diff_summary?: string }[];
}
