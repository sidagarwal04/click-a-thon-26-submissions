import type {
  Action,
  ContentInfo,
  CurveResponse,
  FleetBulkResult,
  FleetCommand,
  FleetCurveResponse,
  FleetDimensions,
  FleetFilter,
  FleetSession,
  FleetSpec,
  FleetStatsResponse,
  SessionState,
  SimParams,
  SimStatus,
} from "./types";

/**
 * Base URL of the Go service.
 *
 * Empty in production: `next build` with `output: 'export'` produces static files
 * that the Go binary itself serves, so the API is same-origin and no base is
 * needed. In development `next dev` runs on :3000 while Go runs on :8088, so
 * .env.development points this at Go — and Go must be started with
 * `--cors-origin http://localhost:3000` to accept it.
 *
 * A next.config rewrite would be the usual way to avoid the cross-origin hop, but
 * rewrites are unsupported under `output: 'export'` and error even in `next dev`.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/**
 * Bearer token for /api/, kept in localStorage.
 *
 * The Go service refuses to bind a non-loopback address unless --token is set,
 * because /api/ writes to ClickHouse. That guard is the reason this exists: on
 * loopback the token is empty and every request works without one, but the moment
 * the service is exposed the browser has to present it, and a static export has
 * nowhere to bake a secret at build time. So it is entered once and stored.
 *
 * localStorage rather than a cookie: there is no server to set one, the value is
 * only ever read by this origin's own fetches, and it survives a reload — which
 * matters because changing the token reloads the page to re-run every SWR fetch.
 */
const TOKEN_KEY = "sonyliv-mock.token";

/** Dispatched when the service answers 401, so the UI can prompt for a token. */
export const UNAUTHORIZED_EVENT = "sonyliv-mock:unauthorized";

export function getToken(): string {
  // Guarded: this module is imported during the static export's prerender, where
  // window does not exist.
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    // Private-mode Safari throws on localStorage access rather than returning null.
    return "";
  }
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing useful to do; the header simply will not be sent */
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      // Only sent when set, so loopback use with no --token is unchanged.
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });

  // Surface 401 before parsing: the body is Go's plain-text "unauthorized", which
  // would otherwise fail JSON parsing and be reported as "not the API".
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
    }
    throw new ApiError(
      token
        ? "401 unauthorized: the stored token was rejected."
        : "401 unauthorized: this service requires a token.",
      401,
    );
  }

  const text = await res.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    // A non-JSON body means we reached something that is not the API — most
    // often the Next dev server itself, when NEXT_PUBLIC_API_BASE is unset.
    throw new ApiError(
      `${res.status} ${res.statusText}: response was not JSON. Is the Go service running, and is NEXT_PUBLIC_API_BASE set?`,
      res.status,
    );
  }

  if (!res.ok) {
    const msg =
      typeof body === "object" && body && "error" in body
        ? String((body as { error: unknown }).error)
        : `${res.status} ${res.statusText}`;
    throw new ApiError(msg, res.status);
  }
  return body as T;
}

/** SWR fetcher. Keyed by path so SWR dedupes across components. */
export const fetcher = <T,>(path: string) => request<T>(path);

export const api = {
  content: (q: string, limit = 40) =>
    request<{ items: ContentInfo[] | null }>(
      `/api/content?limit=${limit}&q=${encodeURIComponent(q)}`,
    ),

  simStatus: () => request<SimStatus>("/api/sim"),

  simStart: (params: SimParams) =>
    request<SimStatus>("/api/sim/start", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  simStop: () =>
    request<{ stopped: boolean; status: SimStatus }>("/api/sim/stop", {
      method: "POST",
    }),

  curve: (minutes = 30) =>
    request<CurveResponse>(`/api/curve?minutes=${minutes}`),

  manualNew: (content: ContentInfo, platform: string) =>
    request<SessionState["session"]>("/api/manual/session", {
      method: "POST",
      body: JSON.stringify({
        content_id: content.content_id,
        title: content.title,
        video_type: content.video_type,
        platform,
      }),
    }),

  manualEvent: (session: string, action: Action, advanceSeconds: number) =>
    request<SessionState>("/api/manual/event", {
      method: "POST",
      body: JSON.stringify({
        session,
        action,
        advance_seconds: advanceSeconds,
      }),
    }),

  manualSessions: () =>
    request<{ sessions: SessionState["session"][] | null }>(
      "/api/manual/sessions",
    ),

  manualState: (session: string) =>
    request<SessionState>(`/api/manual/session/${session}`),

  fleetCreate: (spec: FleetSpec) =>
    request<{ created: number; sessions: FleetSession[] }>(
      "/api/fleet/sessions",
      { method: "POST", body: JSON.stringify(spec) },
    ),

  fleetCommand: (id: string, command: FleetCommand) =>
    request<{ session: FleetSession; wrote: number }>(
      `/api/fleet/sessions/${id}/command`,
      { method: "POST", body: JSON.stringify({ command }) },
    ),

  /**
   * One command over many sessions.
   *
   * `all` sends the filter instead of ids, so "select all matching" acts on every
   * session the server can see rather than the 50 on this page — and cannot be
   * stale by the time it arrives.
   */
  fleetBulk: (
    command: FleetCommand,
    target: { ids: string[] } | { all: true },
    filter: FleetFilter,
  ) =>
    request<FleetBulkResult>(`/api/fleet/bulk?${filterQuery(filter)}`, {
      method: "POST",
      body: JSON.stringify({ command, ...target }),
    }),

  fleetClearEnded: () =>
    request<{ removed: number }>("/api/fleet/clear-ended", { method: "POST" }),

  fleetStats: () => request<FleetStatsResponse>("/api/fleet/stats"),

  fleetDimensions: () => request<FleetDimensions>("/api/fleet/dimensions"),

  fleetCurve: (filter: FleetFilter, minutes: number) =>
    request<FleetCurveResponse>(
      `/api/fleet/curve?minutes=${minutes}&${filterQuery(filter)}`,
    ),
};

/**
 * Serialises a filter for the query string.
 *
 * One helper for both the listing and the curve, deliberately. The two must narrow
 * to the same set of sessions or the graph's comparison would be answering a
 * different question from the table beside it — and the Go side derives the
 * ClickHouse scope from the same filter, so a mismatch here would split all three.
 *
 * Keys are emitted in a fixed order so equal filters produce equal strings, which
 * is what lets SWR dedupe and cache by path.
 */
export function filterQuery(filter: FleetFilter): string {
  const keys: (keyof FleetFilter)[] = [
    "content_id",
    "video_type",
    "platform",
    "app_version",
    "country",
    "phase",
    "mode",
  ];
  const qs = new URLSearchParams();
  for (const k of keys) {
    const v = filter[k];
    if (v) qs.set(k, v);
  }
  return qs.toString();
}

// ---------------------------------------------------------------------------
// Formatting. Centralised so the same number never renders two ways.
// ---------------------------------------------------------------------------

const nf = new Intl.NumberFormat("en-US");

export const num = (n: number | undefined | null) => nf.format(n ?? 0);

/** HH:MM:SS.mmm in UTC — the only timezone in this system. */
export function clockTime(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  // A zero DateTime64 comes back as 1970; showing "00:00:00.000" would read as a
  // real time rather than "never set".
  if (d.getUTCFullYear() <= 1970) return "—";
  return d.toISOString().slice(11, 23);
}

export const seconds = (ms: number) => `${(ms / 1000).toFixed(1)}s`;

export function durationBetween(start: string, end: string): string {
  return seconds(new Date(end).getTime() - new Date(start).getTime());
}
