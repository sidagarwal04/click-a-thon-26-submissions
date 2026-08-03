import type {
  ContributionRow,
  GlobalSeriesRow,
  RcaFilters,
  RcaReport,
  RcaReportSummary,
  SegmentSeriesRow,
} from "./types";

declare global {
  interface Window {
    __RCA_API__?: string;
  }
}

const envUrl = import.meta.env.VITE_RCA_API_URL as string | undefined;

/** Same-origin in Docker (nginx proxies /api); localhost:3002 for local dev. */
export const API_BASE =
  (typeof window !== "undefined" && window.__RCA_API__) ||
  (envUrl !== undefined ? envUrl : import.meta.env.PROD ? "" : "http://localhost:3002");

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json() as Promise<T>;
}

export function fetchReports() {
  return get<RcaReportSummary[]>("/api/rca/reports");
}

export function fetchReport(id: string) {
  return get<RcaReport>(`/api/rca/reports/${id}`);
}

export function fetchGlobalSeries(id: string, filters: RcaFilters) {
  return post<GlobalSeriesRow[]>(`/api/rca/reports/${id}/global-series`, filters);
}

export function fetchSegmentSeries(id: string, filters: RcaFilters) {
  return post<SegmentSeriesRow[]>(`/api/rca/reports/${id}/segment-series`, filters);
}

export function fetchContributions(id: string) {
  return get<ContributionRow[]>(`/api/rca/reports/${id}/contributions`);
}

export async function fetchRcaDashboard(id: string, filters: RcaFilters) {
  const [globalSeries, segmentSeries, contributions] = await Promise.all([
    fetchGlobalSeries(id, filters),
    fetchSegmentSeries(id, filters),
    fetchContributions(id),
  ]);
  return { globalSeries, segmentSeries, contributions };
}
