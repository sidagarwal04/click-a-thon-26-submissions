import type { EvidenceBundle, Health, InvestigationRow } from "./types";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// NOTE: there is deliberately no `investigate()` helper here anymore. It POSTed /investigate and,
// on any failure, returned fixtures/sample_bundle.json — invented numbers rendered as though they
// were a real diagnosis. The dashboard's Investigate button drives the seed flow
// (startRangeInvestigation) instead, and an empty dashboard now says so rather than showing a
// sample. Don't reintroduce a fixture fallback: showing fake evidence is worse than showing none.

/** Add prose to a stored investigation. Returns the narrated bundle, or null if narration is
 *  unavailable (no LLM creds / Bedrock down) — the numbers are already complete either way. */
export async function narrate(investigationId: string): Promise<EvidenceBundle | null> {
  try {
    const res = await fetch(`${API}/narrate/${investigationId}`, { method: "POST" });
    if (!res.ok) return null;
    return (await res.json()) as EvidenceBundle;
  } catch {
    return null;
  }
}

/** Investigation history (flattened rows, not full bundles) for the past-runs panel. */
export async function listBundles(limit = 20): Promise<InvestigationRow[]> {
  try {
    const res = await fetch(`${API}/bundles?limit=${limit}`);
    if (!res.ok) return [];
    const data = await res.json();
    return (data.investigations ?? []) as InvestigationRow[];
  } catch {
    return [];
  }
}

/** Re-read a stored bundle by id (clicking a history row). */
export async function getBundle(investigationId: string): Promise<EvidenceBundle | null> {
  try {
    const res = await fetch(`${API}/bundle/${investigationId}`);
    if (!res.ok) return null;
    return (await res.json()) as EvidenceBundle;
  } catch {
    return null;
  }
}

/** Liveness + engine status (live vs fixture) + Langfuse wiring, for the topbar. */
export async function getHealth(): Promise<Health | null> {
  try {
    const res = await fetch(`${API}/health`);
    if (!res.ok) return null;
    return (await res.json()) as Health;
  } catch {
    return null;
  }
}

// One row per stored anomaly/run — the dashboard's incident switcher list.
export interface IncidentRow {
  investigation_id: string;
  created_at: string;
  window_start: string;
  window_end: string;
  metric: string;
  direction: string;
  pct_delta: number;
  is_anomaly: number;
  primary_factor: string;
  localized_segment: string; // JSON string
  narrated: number;
}

// Fetch a wide window, not just the latest N: the feed is dominated by detection-only bundles
// (chat/scan runs persist a `pending` row per check), and only a handful are fully investigated.
// With a small limit those few get crowded out entirely, the switcher comes back empty, and the
// dashboard silently falls back to the bundled sample. 200 comfortably covers the store today;
// the real anomalies are what we filter TO, so over-fetching pending rows is cheap.
export async function listIncidents(limit = 200): Promise<IncidentRow[]> {
  try {
    const res = await fetch(`${API}/dashboard?limit=${limit}`);
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    // The chat path (POST /v1/chat/completions) persists a detection-only bundle — real
    // anomaly, but no decompose/drill yet (primary_factor stays "pending"). Showcasing one
    // would leave the factor split, ruled-out panel and drill tree empty on the dashboard, so
    // the switcher only offers fully-investigated bundles. Chat-only anomalies still surface
    // through GET /bundles (Past investigations) and remain replayable in chat.
    return (data.incidents as IncidentRow[]).filter(
      (r) => r.is_anomaly === 1 && r.primary_factor && r.primary_factor !== "pending"
    );
  } catch {
    return [];
  }
}

// Windowed investigate = the dev "find anomalies → seed" flow: discover every anomaly in the
// range, run the full pipeline (detect + decompose + drill + narrate) per primary incident, and
// persist each to `bundles`. Runs server-side as a background job — start it, then poll.
export interface SeedResult {
  seeded: number;
  errors: number;
  already_present: number;
  echoes_skipped: number;
  bundles: Array<{
    investigation_id?: string;
    metric: string;
    window: string;
    detected?: boolean;
    localized?: Record<string, string>;
    skipped?: string;
    error?: string;
  }>;
}

export async function startRangeInvestigation(
  start: string,
  end: string,
): Promise<string | null> {
  try {
    const res = await fetch(`${API}/dev/seed_bundles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start, end }),
    });
    if (!res.ok) return null;
    return ((await res.json()) as { job_id: string }).job_id ?? null;
  } catch {
    return null;
  }
}

/** Poll the background job until it finishes; resolves with the seed result (or null on error). */
export async function waitForRangeInvestigation(
  jobId: string,
  intervalMs = 3000,
  timeoutMs = 15 * 60 * 1000,
): Promise<SeedResult | null> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${API}/dev/jobs/${jobId}`);
      if (res.ok) {
        const j = await res.json();
        if (j.finished) return j.status === "done" ? (j.result as SeedResult) : null;
      }
    } catch {
      // transient network blip — keep polling until the deadline
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return null;
}

// One hour bucket behind the anomaly card's chart. `actual`/`expected` are null when that
// hour has no data (empty bucket, or segment younger than the baseline window).
export interface SeriesPoint {
  hour: string; // ISO, start of the hour (UTC)
  actual: number | null;
  expected: number | null;
}

export interface AnomalySeries {
  metric: string;
  scope: string; // "global" — matches the card's population-wide headline
  points: SeriesPoint[];
}

/** The real 24h actual-vs-expected series for a stored anomaly. Returns null when the backend
 *  is unreachable or the investigation isn't in the store (sample/offline) — the card then
 *  falls back to its synthetic curve so it always renders. */
export async function getSeries(investigationId: string): Promise<AnomalySeries | null> {
  try {
    const res = await fetch(`${API}/series/${investigationId}`);
    if (!res.ok) return null;
    return (await res.json()) as AnomalySeries;
  } catch {
    return null;
  }
}

// Dashboard chat: talks to our own OpenAI-shaped endpoint, carrying the showcased
// anomaly's bundle id so "this anomaly" resolves to what's on screen.
export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export async function sendChat(
  messages: ChatTurn[],
  bundleId: string | null,
  sessionId: string,
): Promise<string> {
  const res = await fetch(`${API}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-Id": sessionId },
    body: JSON.stringify({ messages, bundle_id: bundleId }),
  });
  if (!res.ok) throw new Error(String(res.status));
  const data = await res.json();
  return data.choices?.[0]?.message?.content ?? "(no reply)";
}

// The investigation's Langfuse trace, reshaped by the backend into a readable timeline.
// Always resolves: when tracing is off or Langfuse is unreachable the backend returns
// { available: false, reason }, which the drawer shows instead of failing.
export interface TraceQuery {
  name: string;
  sql: string;
  ms: number;
  summary: Record<string, unknown>;
}

export interface TraceStep {
  phase: string;
  ms: number;
  headline: string;
  verdict: Record<string, unknown>;
  queries: TraceQuery[];
}

export interface TraceView {
  available: boolean;
  reason?: string;
  total_ms?: number;
  scores?: Record<string, number>;
  steps?: TraceStep[];
}

export async function getTrace(investigationId: string): Promise<TraceView> {
  try {
    const res = await fetch(`${API}/trace/${investigationId}`);
    if (!res.ok) return { available: false, reason: `API returned ${res.status}` };
    return (await res.json()) as TraceView;
  } catch {
    return { available: false, reason: "Backend unreachable" };
  }
}

// Anomaly sweep over an arbitrary window — no case list, it finds them itself. A full sweep is
// ~50 queries, so the backend runs it as a job: start it, then poll until finished.
export interface ScanIncident {
  incident_id: string;
  metric: string;
  window_start: string;
  window_end: string;
  direction: string;
  peak_pct_delta: number;
  peak_z: number;
  score: number;
  role: string; // "primary" | "echo"
  scope?: string; // "global" | "segment"
  echo_of?: string;
  localized?: Record<string, string> | { error: string };
}

export interface ScanJob {
  status: string;
  finished: boolean;
  log?: string;
  result?: { count: number; primary_count: number; incidents: ScanIncident[] };
}

export async function startScan(start: string, end: string, method = "isolation_forest"): Promise<string | null> {
  try {
    const res = await fetch(`${API}/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start, end, method }),
    });
    if (!res.ok) return null;
    return (await res.json()).job_id ?? null;
  } catch {
    return null;
  }
}

export async function scanStatus(jobId: string): Promise<ScanJob | null> {
  try {
    const res = await fetch(`${API}/scan/${jobId}`);
    if (!res.ok) return null;
    return (await res.json()) as ScanJob;
  } catch {
    return null;
  }
}

// Live replay of the sealed unseen slice. Starting it truncates the stream tables and refills
// them batch by batch, scoring each batch as it lands — the dashboard's real-time mode.
export interface StreamDetection {
  metric: string;
  hour: string;
  direction: string;
  observed: number;
  expected: number;
  pct_delta: number;
  score: number;
  investigation_id?: string | null;
}

export interface SegmentFinding {
  metric: string;              // e.g. "fill_rate[category=gaming]" for a segment-scoped find
  peak_pct_delta: number;
  direction: string;
  scope?: string;              // "global" | "segment"
  localized?: Record<string, string> | { error: string };
}

export interface StreamStatus {
  status: "idle" | "running" | "done" | "stopped" | "error";
  batches_done?: number;
  batches_total?: number;
  rows_ingested?: number;
  checks?: number;
  detections?: StreamDetection[];
  segment_findings?: SegmentFinding[];   // deep scan: global + per-segment
  deep_scans?: number;
  deep_scan_window?: [string, string] | null;
  current_window?: [string, string] | null;
  last_tick_ms?: number;
  dataset?: string;
  error?: string | null;
  analysis?: { metric_hours_scored?: number; hours_covered?: number; detections?: number };
}

export async function startStream(): Promise<StreamStatus | null> {
  try {
    const res = await fetch(`${API}/stream/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reset: true }), // fresh run: truncate, then refill from scratch
    });
    if (!res.ok) return null;
    return (await res.json()) as StreamStatus;
  } catch {
    return null;
  }
}

export async function stopStream(): Promise<StreamStatus | null> {
  try {
    const res = await fetch(`${API}/stream/stop`, { method: "POST" });
    return res.ok ? ((await res.json()) as StreamStatus) : null;
  } catch {
    return null;
  }
}

export async function getStreamStatus(): Promise<StreamStatus | null> {
  try {
    const res = await fetch(`${API}/stream/status`);
    return res.ok ? ((await res.json()) as StreamStatus) : null;
  } catch {
    return null;
  }
}

// Which table set investigations point at. Surfaced because it is otherwise invisible: a sweep
// over the streamed range silently returned nothing when the target had reverted to dev.
export interface DatasetMode { target: string; history: string; }

export async function setDataset(target: string): Promise<DatasetMode | null> {
  try {
    const res = await fetch(`${API}/dataset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target }),
    });
    return res.ok ? ((await res.json()) as DatasetMode) : null;
  } catch {
    return null;
  }
}
