/**
 * What a harvested catalog looks like on the wire.
 *
 * Mirrors `CatalogResponse` and friends in the Connector API. Written as the
 * contract rather than copied from the server's models, so a change there shows
 * up here as a type error rather than as an empty column list.
 */

/** Observed statistics, always carrying the sample size behind them. */
export interface FieldProfile {
  readonly sampled_rows: number;
  readonly null_fraction?: number | null;
  readonly distinct_count?: number | null;
  readonly min_value?: string | null;
  readonly max_value?: string | null;
  readonly sample_values?: readonly string[];
}

export interface CatalogField {
  readonly field_id: string;
  readonly name: string;
  readonly declared_type: string;
  /** Join-relevant grouping — `string`, `integer`, `uuid`, … */
  readonly family: string;
  readonly nullable: boolean;
  readonly position: number;
  readonly profile?: FieldProfile | null;
  /** Whether the agent system may see this field. Visible unless toggled off. */
  readonly agent_visible: boolean;
}

export interface CatalogTable {
  readonly table_id: string;
  readonly name: string;
  readonly database: string;
  readonly engine?: string | null;
  readonly estimated_rows?: number | null;
  readonly size_bytes?: number | null;
  readonly fields?: readonly CatalogField[];
  readonly agent_visible: boolean;
}

/** A table/field agent-access decision, as the toggle endpoints return it. */
export interface AgentAccessResponse {
  readonly override_id: string;
  readonly data_source_id: string;
  readonly table_name: string;
  readonly field_name?: string | null;
  readonly agent_visible: boolean;
  readonly decided_by: string;
  readonly decided_at: string;
}

export interface UnreadableTable {
  readonly qualified_name: string;
  readonly reason: string;
}

export interface CatalogResponse {
  readonly catalog_version_id: string;
  readonly data_source_id: string;
  readonly harvest_run_id: string;
  readonly created_at: string;
  readonly tables?: readonly CatalogTable[];
  readonly unreadable?: readonly UnreadableTable[];
}

/** Where a harvest has reached. Ordered as the phases occur. */
export type HarvestPhase =
  | 'pending'
  | 'connecting'
  | 'listing_tables'
  | 'describing_fields'
  | 'profiling'
  | 'inferring_relations'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface HarvestResponse {
  readonly harvest_run_id: string;
  readonly data_source_id: string;
  readonly phase: HarvestPhase;
  readonly tables_found: number;
  readonly fields_described: number;
  readonly fields_profiled: number;
  readonly relations_proposed: number;
  readonly unreadable_count: number;
  readonly queries_used: number;
  readonly queries_budget: number;
  readonly seconds_used: number;
  readonly catalog_version_id?: string | null;
  readonly failure_code?: string | null;
  readonly failure_message?: string | null;
}

export const TERMINAL_PHASES: readonly HarvestPhase[] = [
  'completed',
  'failed',
  'cancelled',
];

export const isTerminal = (phase: HarvestPhase): boolean =>
  TERMINAL_PHASES.includes(phase);

/** One page of a Source Table's raw rows, read straight through Cube. */
export interface TableRowsResponse {
  readonly data_source_id: string;
  readonly table_name: string;
  readonly columns: readonly string[];
  readonly rows: readonly (string | null)[][];
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
}
