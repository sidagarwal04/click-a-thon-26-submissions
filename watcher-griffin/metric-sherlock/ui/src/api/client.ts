import type {
  CalibrationResponse,
  CausalChain,
  ChatResponse,
  CoverageResponse,
  DashboardResponse,
  DatasetsResponse,
  IncidentDetail,
  IncidentRow,
  InvestigateResponse,
  InvestigationDetailResponse,
  InvestigationListItem,
  OpsSummary,
  Registry,
  ScanTick,
  VerifyResponse,
} from '../types'

import { getDataset } from '../lib/dataset'

// Relative paths only -- proxied to the API in dev (vite.config.ts) and by
// nginx in prod (ui/nginx.conf), so this file never hardcodes a host/port.

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/* Attaches the selected dataset to every request, in ONE place.
 *
 * A query parameter rather than a header, for two reasons: nginx and the Vite dev proxy
 * are both path-prefix based so a query string passes through with no config change, and
 * a URL that fully identifies its response keeps the browser cache honest -- two datasets
 * answering on the same URL with different bodies is a cache bug waiting to happen.
 *
 * Appended by URL parsing rather than string concatenation because several paths already
 * carry a query string (`?limit=`, `?include_gated=`), where a naive `?dataset=` would
 * produce a second question mark and a silently ignored parameter. */
function withDataset(path: string): string {
  const url = new URL(path, window.location.origin)
  url.searchParams.set('dataset', getDataset())
  // Relative again, so the "relative paths only" contract above still holds and the
  // request stays same-origin through whichever proxy is in front of it.
  return `${url.pathname}${url.search}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(withDataset(path), {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? `Request to ${path} failed with ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function investigate(metric: string, windowStart: string, windowEnd: string) {
  return request<InvestigateResponse>('/investigate', {
    method: 'POST',
    body: JSON.stringify({ metric, window_start: windowStart, window_end: windowEnd }),
  })
}

export function listMetrics() {
  return request<{ metrics: string[]; watchlist: string[] }>('/api/metrics')
}

/** The datasets this deployment can serve, each with its own data clock and whether it
 *  has been swept yet. The switcher renders from this rather than a hardcoded list, so a
 *  label can never claim a date range the data does not have. */
export function listDatasets() {
  return request<DatasetsResponse>('/api/datasets')
}

export function listInvestigations(limit = 50) {
  return request<{ investigations: InvestigationListItem[] }>(`/api/investigations?limit=${limit}`)
}

export function getInvestigation(id: string) {
  return request<InvestigationDetailResponse>(`/api/investigations/${id}`)
}

export function sendChatMessage(investigationId: string, message: string) {
  return request<ChatResponse>(`/api/investigations/${investigationId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

/** The backtest record: what each threshold caught and what it raised on quiet days.
 *  A file read on the server, never a live replay. */
export function getCalibration() {
  return request<CalibrationResponse>('/api/calibration')
}

export function getCausalChain(incidentId: string) {
  return request<CausalChain>(`/api/incidents/${incidentId}/causal-chain`)
}

/** Chat grounded in an incident's own evidence rather than an investigation's.
 *  Most incidents are never fully investigated (only the top few per sweep are), so
 *  this is the path that actually has a chat box on it. */
export function sendIncidentChatMessage(incidentId: string, message: string) {
  return request<ChatResponse>(`/api/incidents/${incidentId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

export function listScanTicks(limit = 100) {
  return request<{ ticks: ScanTick[] }>(`/api/scanner/ticks?limit=${limit}`)
}

export function getDashboard(asOf?: string) {
  const qs = asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''
  return request<DashboardResponse>(`/api/dashboard${qs}`)
}

/* ---------------------------------------------------------------------------
 * Operations console.
 *
 * Note what these signatures do NOT take: no metric, no window, no dimension.
 * The system already knows what moved and when, so the operator is never asked.
 * `investigate()` above is the one exception and it lives on the Analyst panel,
 * off the operations path.
 * ------------------------------------------------------------------------- */

/** The whole operations home screen in one call. No parameters, by design. */
export function getOpsSummary() {
  return request<OpsSummary>('/api/ops/summary')
}

export function listIncidents(limit = 100, includeGated = true) {
  return request<{ incidents: IncidentRow[]; impact_gate_usd: number; gate_note: string }>(
    `/api/incidents?limit=${limit}&include_gated=${includeGated}`,
  )
}

export function getIncident(id: string) {
  return request<IncidentDetail>(`/api/incidents/${id}`)
}

/** Records a post-mortem verdict. This is the feedback loop that makes per-slice
 *  precision measurable, so band thresholds can eventually be tuned from evidence
 *  rather than taste. */
export function labelIncident(id: string, label: string) {
  return request<{ incident_id: string; label: string; saved: boolean }>(
    `/api/incidents/${id}/label`,
    { method: 'POST', body: JSON.stringify({ label }) },
  )
}

/** Re-runs the query behind ONE number and reports whether it still reproduces it.
 *
 *  Sends a fact KEY, never SQL — the server re-derives the statement from the incident's
 *  own fields. That is deliberate and not incidental: an endpoint that accepted a query
 *  string would be a SQL-execution surface, and the engine's own client runs whatever it
 *  is given. */
export function verifyFact(incidentId: string, fact: string) {
  return request<VerifyResponse>(`/api/incidents/${incidentId}/verify`, {
    method: 'POST',
    body: JSON.stringify({ fact }),
  })
}

export function getCoverage() {
  return request<CoverageResponse>('/api/coverage')
}

/** Metric labels, owners, scope labels, grain list and thresholds. Fetched once so
 *  the UI never keeps its own copy of the backend's tables — a second copy is free
 *  to drift out of agreement with the engine that produced the numbers. */
export function getRegistry() {
  return request<Registry>('/api/registry')
}

export { ApiError }
