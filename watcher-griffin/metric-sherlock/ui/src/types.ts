// Mirrors engine/evidence.py's EvidenceBundle and api/main.py's response
// models exactly -- keep in sync by hand, there's no shared schema generator.

/* ===========================================================================
 * Operations console types — mirror the /api/ops/summary, /api/incidents,
 * /api/coverage and /api/registry payloads.
 *
 * Still hand-maintained (see the header note above): there is no schema generator,
 * so a field added in Python needs a matching edit here and the compiler will not
 * catch the omission.
 * =========================================================================== */

export interface BandPoint {
  window_start: string
  window_end: string
  value: number | null
  center: number | null
  spread: number | null
  breached: boolean
  severity: string
  seasonal_cell: string
}

export interface GrainCell {
  grain: string
  status: string
  deviation_score?: number | null
  value?: number | null
  center?: number | null
  sample_count?: number
  reason: string
}

export interface TreeNode {
  metric: string
  label: string
  role: 'root' | 'factor' | 'sibling'
  owner: string
  status: string
  value: number | null
  center: number | null
  spread: number | null
  deviation_score: number | null
  pct_change: number | null
  direction: string
  is_driver: boolean
  share_of_move: number | null
  unit: string
  reason: string
  seasonal_cell: string
  sample_count: number
  baseline_method: string
  series: BandPoint[]
  grain_ladder: GrainCell[]
  source_step: string
}

export interface MetricTree {
  grain: string
  grain_seconds: number
  window_start: string
  window_end: string
  identity: string
  identity_note: string
  nodes: TreeNode[]
  meanings: Record<string, string>
}

export interface DataClock {
  as_of: string
  max_event_time: string | null
  total_rows: number
  pinned: boolean
  explanation: string
  source_step: string
}

export interface IncidentRow {
  incident_id: string
  opened_at: string
  last_seen_at: string
  closed_at: string | null
  root_scope_type: string
  root_scope_value: string
  root_metric: string
  grain: string
  direction: string
  signature: string
  signature_confidence: number
  mechanism: string
  owner: string
  /** Exposure summed over the consecutive windows of the root's own grain that the
   *  incident persisted for -- see windows_spanned for how many that is. */
  impact_usd: number
  /** The same exposure as a daily run rate. This is what incidents are ranked by --
   *  raw window figures are not comparable across grains. */
  impact_usd_per_day: number
  /** How many consecutive root-grain windows impact_usd covers. 1 = a single window.
   *  Needed to state the total honestly: "$48.84 over 2 days" not just "$48.84". */
  windows_spanned: number
  member_event_count: number
  breached_metrics: string[]
  fingerprint: string
  narration: string
  narration_available: boolean
  investigation_id: string | null
  langfuse_trace_url: string
  label: string
  gated_by_impact: boolean
  evidence_score: number
  /* How far the ROOT metric actually moved, joined from metric_events at the window where it
   * was furthest from its band -- the peak of the movement, not its first or last moment.
   * Nullable because the join is a LEFT JOIN: an incident whose events were pruned still
   * lists rather than vanishing, and `root_deviation_score` is additionally nulled when it
   * carries bands.py's flat-history sentinel rather than a real measurement. */
  root_deviation_score?: number | null
  root_value?: number | null
  root_center?: number | null
  root_spread?: number | null
  root_severity?: string | null
  root_peak_window?: string | null
}

/** The largest movement outside its band right now — the ops home's headline. */
export interface PeakMovement {
  root_metric: string
  root_scope_type: string
  root_scope_value: string
  grain: string
  direction: string
  root_deviation_score: number | null
  root_value: number | null
  root_center: number | null
  root_severity: string
  incident_id: string
}

export interface SweepRun {
  run_id: string
  started_at: string
  as_of: string
  duration_ms: number
  grains_swept: string[]
  scopes_swept: string[]
  metrics_swept: string[]
  cells_total: number
  evaluations: number
  breaches: number
  events_written: number
  incidents_opened: number
  skipped_low_power: number
  skipped_no_band: number
  skipped_cadence: number
  queries_issued: number
  error: string
}

export interface Staleness {
  stale: boolean
  reason: string
  sweep_as_of?: string
  clock_as_of?: string
  lag_hours?: number
}

export interface OpsSummary {
  clock: DataClock
  tree: MetricTree
  staleness: Staleness
  revenue_at_risk_usd: number
  impact_gate_usd: number
  /** Empty object when nothing is currently outside its band. */
  peak_movement: PeakMovement | Record<string, never>
  /** Counted over the whole incidents table, not over the page in `incidents` below. */
  incidents_open: number
  incidents_gated: number
  /** How many alertable incidents this payload actually carries, so the queue can say
   *  "showing 25 of 33" rather than implying it is the complete list. */
  incidents_returned: number
  incidents_by_owner: Record<string, number>
  incidents: IncidentRow[]
  last_sweep: SweepRun | null
  queries: QueryRecord[]
}

export interface RuledOutBlock {
  check: string
  reason: string
  numbers: Record<string, unknown>
  source_steps: string[]
}

export interface ImpactPart {
  scope_type: string
  scope_value: string
  metric: string
  grain: string
  impact_usd: number
  share_of_impact: number
  basis: string
}

export interface ScoreComponent {
  name: string
  points: number
  max_points: number
  raw: string
  reason: string
  source: string
}

export interface EvidenceScoreDetail {
  score: number
  label: string
  formula: string
  caveat: string
  components: ScoreComponent[]
  components_sum: number
}

export interface PriorIncident {
  incident_id: string
  opened_at: string
  signature: string
  root: string
  metric: string
  grain: string
  impact_usd: number
  label: string
  match_strength: string
}

export interface HistoryBlock {
  looked_up: boolean
  reason?: string
  fingerprint?: string
  recurrence_count?: number
  is_novel?: boolean
  first_seen?: string | null
  last_seen?: string | null
  prior_impact_total_usd?: number
  chronic?: boolean
  chronic_detail?: Record<string, unknown>
  labels_seen?: Record<string, number>
  priors?: PriorIncident[]
  summary?: string
  source_step?: string
}

export interface IncidentMember {
  metric: string
  scope_type: string
  scope_value: string
  grain: string
  direction: string
  severity: string
  value: number
  center: number
  spread: number
  deviation_score: number
  impact_usd: number
  window_start: string
  window_end: string
  seasonal_cell: string
  baseline_method: string
  sample_count: number
}

export interface AbsorbedCluster {
  root: string
  metric: string
  impact_usd: number
  events: number
  reason: string
}

export interface IncidentDetail extends IncidentRow {
  members: IncidentMember[]
  ruled_out: RuledOutBlock[] | null
  seasonality: Record<string, unknown> | null
  impact_breakdown: { total_impact_usd: number; parts: ImpactPart[] } | null
  history: HistoryBlock | null
  /** A preview, ordered by exposure — see absorbed_total for how many there are.
   *  One real incident absorbed 2,520 of these; rendering them all is a megabyte on
   *  the wire and 2,520 list items on the page. */
  absorbed: AbsorbedCluster[] | null
  absorbed_total: number | null
  evidence_score_detail: EvidenceScoreDetail | null
  evidence: EvidenceBundle | null
  /** The supporting query for every number on this page, carried ON the incident so
   *  whoever holds the incident holds the proof. Present for every incident, unlike
   *  `evidence` which only exists for the few that were fully investigated. */
  provenance: ProvenanceBlock | null
  /** Persisted follow-up transcript for this incident. Served so the page and the
   *  model share one history — the API feeds these same turns into the prompt. */
  chat: ChatTurn[]
}

export interface CoverageCellRow {
  scope_type: string
  metric: string
  grain: string
  window_start: string
  window_end: string
  entities_total: number
  entities_evaluated: number
  entities_breached: number
  skipped_low_power: number
  skipped_no_band: number
  skipped_cadence: number
  power_floor: number
  min_denom_seen: number
  max_denom_seen: number
  finest_valid_grain: string
  skip_reason: string
}

export interface CoverageResponse {
  sweep: SweepRun | null
  cells: CoverageCellRow[]
}

export interface RegistryMetric {
  name: string
  label: string
  unit: string
  meaning: string
  owner: string
  bad_direction: string
  numerator: string
  denominator: string | null
  multiplier: number
  power_base: string
  power_floor: number
  monitored: boolean
}

export interface RegistryScope {
  name: string
  label: string
  implicates: string
  key_columns: string[]
  is_entity: boolean
  is_composite: boolean
  unsupported_metrics: string[]
  sub_hour_capable: boolean
  monitored: boolean
}

export interface Registry {
  metrics: RegistryMetric[]
  scopes: RegistryScope[]
  grains: { name: string; seconds: number | null; is_rolling: boolean }[]
  tree: {
    root: string
    factors: string[]
    siblings: string[]
    identity: string
    decomposition_factors: string[]
    grain: string
  }
  thresholds: {
    band_k_amber: number
    band_k_red: number
    impact_usd_gate: number
    consecutive_points_required: number
    band_min_samples: number
    band_method: string
  }
  owners: string[]
}

export interface SegmentEvidence {
  dimension: string
  value: string
  metric_now: number
  metric_baseline: number
  share_of_deviation: number
  source_step: string
}

export interface RuledOutEvidence {
  check: string
  reason: string
  numbers: Record<string, unknown>
}

/* One displayed number and the evidence for it (engine/provenance.py).
 *
 * `kind` decides what "proof" means and therefore what the disclosure renders:
 *   measured  one query returns it -> sql + a verify action
 *   derived   a published formula over `inputs`, each of which is itself a Fact
 *   config    a settings constant, labelled as such rather than dressed as a measurement
 */
export interface Fact {
  key: string
  label: string
  value: number | string | null
  kind: 'measured' | 'derived' | 'config'
  sql?: string
  step?: string
  table?: string
  /** Which column of the returned row holds the figure — what makes verification exact. */
  column?: string
  formula?: string
  inputs?: string[]
  config_path?: string
  note?: string
}

export interface ProvenanceBlock {
  facts: Record<string, Fact>
  counts: Record<string, number>
  /** measured facts whose SQL could not be reconstructed — empty is the expected state. */
  unverifiable: string[]
  note: string
}

export interface VerifyResponse {
  fact: string
  kind: string
  verifiable: boolean
  /** Present when verifiable === false: why, plus what to check instead. */
  reason?: string
  sql?: string
  step?: string
  table?: string
  column?: string
  formula?: string
  inputs?: string[]
  config_path?: string
  displayed: number | string | null
  returned?: number | string | null
  /** null when the fact is an input bundle rather than a single displayed number. */
  matches?: boolean | null
  note?: string | null
  rows?: Record<string, unknown>[]
  row_count?: number
  read_rows?: number
  latency_ms?: number
}

export interface QueryRecord {
  step: string
  sql: string
  row_count: number
  latency_ms: number
  error: string | null
  /** Rows/bytes ClickHouse actually scanned, from its own response summary.
   *  0 means the driver did not report it, not that nothing was read. */
  read_rows?: number
  read_bytes?: number
}

export interface FactorBreakdown {
  factor: string
  now: number
  baseline: number
  share: number
}

export interface EvidenceBundle {
  metric: string
  window_start: string
  window_end: string
  baseline_trailing_weeks: number
  current_value: number
  baseline_mean: number
  baseline_sample_count: number
  zscore: number
  pct_change: number | null
  is_anomalous: boolean
  insufficient_baseline: boolean
  primary_factor: string | null
  factor_breakdown: FactorBreakdown[]
  drilldown_levels: SegmentEvidence[][]
  ruled_out: RuledOutEvidence[]
  queries: QueryRecord[]
}

export interface NarrationOut {
  text: string | null
  available: boolean
  provider: string
  error: string | null
}

export interface InvestigateResponse {
  id: string | null
  evidence: EvidenceBundle
  narration: NarrationOut
  langfuse_trace_url: string | null
}

export interface InvestigationListItem {
  id: string
  created_at: string
  triggered_by: 'manual' | 'scanner'
  metric: string
  window_start: string
  window_end: string
  current_value: number
  baseline_mean: number
  zscore: number
  is_anomalous: boolean
  insufficient_baseline: boolean
  primary_factor: string
  narration_available: boolean
  langfuse_trace_url: string
}

/** One replayed threshold setting. `detections` maps an incident label to the date it
 *  was first raised, or null for a miss — misses are rows, never omissions. */
export interface CalibrationSetting {
  label: string
  k_amber: number
  min_relative_spread: number
  min_relative_move: number
  adopted: boolean
  /** Raised the fewest false alarms. Not always the adopted one — a quieter setting can
   *  be bought by raising the smallest move the system can ever detect. */
  quietest: boolean
  /** k × spread floor: the smallest relative move that can ever breach at this setting.
   *  The cost the false-alarm columns cannot show. */
  min_detectable_move: number
  detections: Record<string, string | null>
  /** Every alert on every quiet day. Over-counts a slice that re-fires. */
  fp_raises: number
  /** Unique root fingerprints across quiet days. Under-counts a genuinely noisy day. */
  fp_distinct: number
  fp_days: number
  quiet_days: number
  median_confirmed: number
  capped_days: number
}

/* One selectable dataset, as reported by GET /api/datasets.
 *
 * `provisioned` is the field that keeps an empty console honest: a dataset with no
 * baselines has nothing to detect against, so it renders blank -- which is correct and
 * indistinguishable from "all clear" unless the switcher says so. */
export interface DatasetInfo {
  key: string
  label: string
  database: string
  note?: string
  as_of?: string
  min_event_time?: string | null
  max_event_time?: string | null
  total_rows?: number
  clock_source?: string
  baselines?: number
  incidents?: number
  sweeps?: number
  provisioned: boolean
  available: boolean
  error?: string
}

export interface DatasetsResponse {
  datasets: DatasetInfo[]
  active: string
  default: string
}

export interface CalibrationResponse {
  available: boolean
  /** Why there is no calibration, when there is none. */
  reason?: string
  generated_from?: string
  subset?: boolean
  data_start?: string
  data_end?: string
  days_replayed?: number
  /** Which database the replay was run against, and whether that is the dataset
   *  currently on screen. The scorecard is a file on disk describing the primary
   *  dataset only, so displaying its false-alarm rate unlabelled beside another
   *  dataset's incidents would be a claim about data that was never tested. */
  measured_on?: string
  measured_on_dataset?: string
  active_dataset?: string
  measured_on_active?: boolean
  adopted?: string
  quietest?: string
  adopted_min_detectable_move?: number
  ground_truth?: { label: string; start: string; end: string; mechanism: string }[]
  settings: CalibrationSetting[]
  per_day?: {
    day: string
    expected: string | null
    hit: boolean
    raised: number
    incidents: number
    confirmed: number
  }[]
}

/** One rung of the because-ladder. `certainty` is never inferred by the UI — the
 *  engine states how strongly each step is held, including when it is not. */
export interface ChainLink {
  step: number
  title: string
  claim: string
  because: string
  numbers: Record<string, unknown>
  source_steps: string[]
  certainty: 'measured' | 'ruled_out' | 'derived' | 'unknown'
}

export interface CausalChain {
  incident_id: string
  headline: string
  /** True only when no rung is 'unknown'. */
  complete: boolean
  links: ChainLink[]
}

export interface ChatTurn {
  turn_index: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface InvestigationDetailResponse {
  id: string
  created_at: string
  triggered_by: string
  metric: string
  window_start: string
  window_end: string
  current_value: number
  baseline_mean: number
  baseline_sample_count: number
  zscore: number
  is_anomalous: boolean
  insufficient_baseline: boolean
  primary_factor: string
  narration: string
  narration_available: boolean
  narration_provider: string
  narration_error: string
  langfuse_trace_url: string
  evidence: EvidenceBundle
  chat: ChatTurn[]
}

export interface ScanTick {
  id: string
  ts: string
  metric: string
  window_start: string
  window_end: string
  current_value: number
  baseline_mean: number
  zscore: number
  is_anomalous: boolean
  investigation_id: string | null
}

export interface DashboardSeriesPoint {
  hour: string
  requests: number
  fills: number
  impressions: number
  clicks: number
  revenue: number
}

export interface DashboardResponse {
  series: DashboardSeriesPoint[]
  metric_tiles: ScanTick[]
  data_freshness: { max_event_time: string | null; total_rows: number }
  scanner: { enabled: boolean; interval_seconds: number }
}

export interface ChatResponse {
  reply: string | null
  available: boolean
  provider: string
  error: string | null
}
