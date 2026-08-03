/**
 * Mirrors the JSON the Go service emits. Field names are snake_case because they
 * are the wire format from `internal/mock`, not a local convention — renaming
 * them here would put a translation layer between two things that should stay
 * obviously identical.
 */

export interface ContentInfo {
  content_id: number;
  title: string;
  video_type: string;
  category: string;
}

/** Mirrors generator.Summary, which Go marshals with its Go field names. */
export interface GeneratorSummary {
  Events: number;
  Sessions: number;
  SessionsOpen: number;
  Duplicates: number;
  LateEvents: number;
  DroppedPastCutoff: number;
  PeakConcurrency: number;
}

export interface SimParams {
  concurrency: number;
  user_pool: number;
  content_ids: number[];
  content_pool: number;
  speed_factor: number;
  ramp_up_seconds: number;
  duration_minutes: number;
  max_events: number;
  /**
   * null means "use the measured rates" (7% late, 0.5% duplicate); an explicit 0
   * means "generate a perfectly ordered stream". The Go side models this as
   * *float64 for exactly that reason, so the distinction has to survive the wire.
   */
  late_fraction: number | null;
  dup_fraction: number | null;
  batch_size: number;
  workers: number;
  async: boolean;
  /**
   * "direct" writes over the ClickHouse native protocol; "api" makes the
   * generator a real client of POST /api/events, exercising that endpoint's
   * decoding, validation, chunking and async-insert path on every run.
   */
  sink: "direct" | "api";
}

export interface SimStatus {
  running: boolean;
  run_id?: string;
  started_at?: string;
  elapsed_seconds: number;
  params?: SimParams;
  content_requested: number;
  content_resolved: number;
  rows: number;
  batches: number;
  retries: number;
  rows_per_sec: number;
  insert_p50_ms: number;
  insert_p99_ms: number;
  summary?: GeneratorSummary;
  finished: boolean;
  error?: string;
}

export interface CurvePoint {
  minute: string;
  sessions: number;
  events: number;
}

export interface CurveResponse {
  points: CurvePoint[];
  /** The server labels its own estimator; the UI surfaces that label verbatim. */
  estimator: string;
}

export interface ManualSession {
  video_session_id: string;
  user_id: string;
  content_id: number;
  content_title: string;
  platform: string;
  app_version: string;
  country: string;
  start_epoch: string;
  /** Event-time cursor, advanced by the operator — not wall clock. */
  clock: string;
  events_sent: number;
}

export interface TimelineRow {
  event_ts: string;
  event_type: string;
  event: string;
  signal: string;
  is_liveness: boolean;
  started: boolean;
  end_seen: boolean;
  foreground: boolean;
  playing: boolean;
  last_eligible_signal: string;
  lease_expires: string;
  active: boolean;
}

export interface Interval {
  start: string;
  end: string;
}

export interface SessionState {
  session: ManualSession;
  timeline: TimelineRow[];
  intervals: Interval[];
  active_ms: number;
  timeout_ms: number;
}

// ---------------------------------------------------------------------------
// The session fleet. Mirrors internal/fleet.
// ---------------------------------------------------------------------------

/**
 * Lifecycle label. `expired` is the one worth reading twice: the session is still
 * nominally foregrounded and playing, but no eligible liveness signal landed
 * inside the lease, so the pipeline counts it as gone. That is the state a
 * silenced session reaches, and the one most people do not expect to exist.
 */
export type FleetPhase =
  | "active"
  | "paused"
  | "backgrounded"
  | "expired"
  | "ended";

/**
 * Who drives a session.
 *
 * `autonomous` sessions pause, background and end themselves from the rates
 * measured on the supplied extract — a hundred thousand of them is the load test,
 * on the same write path, with every session still individually addressable.
 * `manual` sessions hold whatever state an operator put them in.
 */
export type FleetMode = "manual" | "autonomous";

/** Operator actions, matching fleet.Command. `silence` writes no event at all. */
export type FleetCommand =
  | "pause"
  | "resume"
  | "background"
  | "foreground"
  | "silence"
  | "unsilence"
  | "end";

export interface FleetSession {
  video_session_id: string;
  user_id: string;
  content_id: number;
  content_title: string;
  video_type: string;
  platform: string;
  app_version: string;
  country: string;
  start_epoch: string;
  cadence_seconds: number;
  /** When the simulator retires this session on its own, with a real session_end. */
  expires_at: string;
  mode: FleetMode;

  phase: FleetPhase;
  active: boolean;

  /** The five terms of the activity predicate, exposed individually so the detail
   *  page can show WHICH one is false rather than only that the session is idle. */
  started: boolean;
  ended: boolean;
  foreground: boolean;
  playing: boolean;
  heartbeating: boolean;

  last_eligible: string;
  lease_expires: string;
  next_tick: string;

  events_sent: number;
  active_ms: number;
  intervals: Interval[];
}

export interface FleetStats {
  total: number;
  active: number;
  paused: number;
  backgrounded: number;
  expired: number;
  ended: number;
  events_sent: number;
  autonomous: number;
  manual: number;
}

/** Health of the write path. A fleet line with no ClickHouse line under it is
 *  usually explained here rather than by a pipeline bug. */
export interface FleetWriteStats {
  rows: number;
  batches: number;
  errors: number;
  last_error?: string;
  queued: number;
}

export interface FleetListResponse {
  sessions: FleetSession[] | null;
  total: number;
  offset: number;
  stats: FleetStats;
}

export interface FleetStatsResponse {
  stats: FleetStats;
  writes: FleetWriteStats;
  timeout_ms: number;
  max_create: number;
  max_live: number;
}

export interface FleetCurvePoint {
  minute: string;
  /** Any-overlap count: sessions active for at least one millisecond of the minute. */
  sessions: number;
  /** Summed active milliseconds. Divided by 60,000 this is average concurrency,
   *  which is always ≤ sessions. */
  active_ms: number;
}

export interface FleetCurveResponse {
  from: string;
  to: string;
  minutes: number;
  /** What the fleet recorded at transition time. Exact by construction. */
  generator: FleetCurvePoint[];
  /** What the pipeline infers from the events the fleet wrote. */
  clickhouse: FleetCurvePoint[];
  /** Set when the comparison query failed. The generator line still renders. */
  clickhouse_error?: string;
  scoped_sessions: number;
  timeout_ms: number;
}

/**
 * What a bulk command did.
 *
 * Counted rather than errored: a bulk pause over a filter always meets sessions the
 * command is a no-op for, and failing because 3 of 500 were already paused would
 * make the buttons unusable.
 */
export interface FleetBulkResult {
  applied: number;
  /** No-ops — already paused, already ended. Deliberately not written. */
  skipped: number;
  /** Ids the server no longer knows, e.g. selected then cleared. */
  unknown: number;
  wrote: number;
  stats: FleetStats;
}

export interface FleetSpec {
  count: number;
  content_id: number;
  content_title: string;
  platform: string;
  app_version: string;
  country: string;
  cadence_seconds: number;
  ttl_minutes: number;
  mode: FleetMode;
}

export interface FleetDimensions {
  platform: string[] | null;
  app_version: string[] | null;
  country: string[] | null;
  video_type: string[] | null;
}

/** The dimensions both the listing and the graph filter on. */
export interface FleetFilter {
  content_id?: string;
  video_type?: string;
  platform?: string;
  app_version?: string;
  country?: string;
  phase?: string;
  mode?: string;
}

/** The stepper's buttons, matching mock.Action on the Go side. */
export type Action =
  | "start"
  | "play"
  | "pause"
  | "resume"
  | "background"
  | "foreground"
  | "heartbeat"
  | "error"
  | "end"
  | "adbreak"
  | "ratechange";
