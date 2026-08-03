import type { AsklysContextRef, AsklysContextResponse, AsklysResponse, AsklysStreamEvent, ContextDocument, FeatureUploadResult, ProcessFeatureResult, RunDetail, RunReport, RunsResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function fetchRuns(signal?: AbortSignal) {
  return request<RunsResponse>("/observability/runs?limit=100", signal);
}

export function fetchRun(traceId: string, signal?: AbortSignal) {
  return request<RunDetail>(`/observability/runs/${encodeURIComponent(traceId)}`, signal);
}

export function fetchRunReport(runId: string, signal?: AbortSignal) {
  return request<RunReport>(`/runs/${encodeURIComponent(runId)}/report`, signal);
}

export async function uploadFeature(featureFolder: string, spec: File, events: File) {
  const form = new FormData();
  form.append("feature_folder", featureFolder);
  form.append("spec", spec, "spec.md");
  form.append("events", events, "events.ndjson");
  const response = await fetch(`${API_BASE}/features/upload`, { method: "POST", body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Upload failed (${response.status})`);
  }
  return response.json() as Promise<FeatureUploadResult>;
}

export async function processFeature(featureFolder: string) {
  const response = await fetch(`${API_BASE}/features/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feature_folder: featureFolder }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Processing failed (${response.status})`);
  }
  return response.json() as Promise<ProcessFeatureResult>;
}

export function fetchContextVersion(version: number, signal?: AbortSignal) {
  return request<ContextDocument>(`/context/${version}`, signal);
}

export function fetchAsklysContext(query = "", signal?: AbortSignal) {
  return request<AsklysContextResponse>(`/asklys/context?q=${encodeURIComponent(query)}&limit=100`, signal);
}

export async function askAsklys(
  payload: {
  question: string;
  context: AsklysContextRef[];
  conversation: Array<{ role: "user" | "assistant"; content: string }>;
  },
  onEvent?: (event: AsklysStreamEvent) => void,
) {
  const response = await fetch(`${API_BASE}/asklys/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Asklys query failed (${response.status})`);
  }
  if (!response.body) throw new Error("Asklys streaming is unavailable in this browser");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: AsklysResponse | null = null;
  let streamError: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line) as AsklysStreamEvent;
      onEvent?.(event);
      if (event.type === "complete") result = event.data;
      if (event.type === "error") streamError = event.message;
    }
    if (done) break;
  }
  if (streamError) throw new Error(streamError);
  if (!result) throw new Error("Asklys finished without returning an answer");
  return result;
}
