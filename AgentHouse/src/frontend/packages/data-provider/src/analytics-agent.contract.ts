/**
 * Analytics Agent API — TypeScript contract (LibreChat ↔ Analytics Backend)
 * =============================================================================
 *
 * Two independent HTTP surfaces:
 *
 *   1) POST /api/analytics/query          Prompt  → Lego blocks (metadata only)
 *   2) POST /api/analytics/data           Insight config → chart series / matrix
 *      POST /api/analytics/dimensions     Dimension key → ordered member values
 *
 * Design principles
 * -----------------
 * - Blocks are **metadata only**. They never embed chart points.
 * - Chart points are fetched later by `da-insight-sdk` via dataResolver.
 * - Dimension members are fetched via dimensionValuesResolver (Ranking / Pivot / Funnel).
 * - Dates on the wire are ISO calendar dates: `YYYY-MM-DD` (no time zone suffix required).
 * - Auth: same LibreChat JWT as other `/api/*` routes (Bearer / session cookie).
 *
 * Mapping note (critical)
 * -----------------------
 * Agent block `insight_type` uses product names (PascalCase).
 * Data-plane `insight_type` uses SDK resolver keys (lowercase).
 * They are NOT 1:1 — see `AgentInsightType` vs `DataInsightType`.
 *
 * @module analytics-agent.contract
 */

/* =============================================================================
 * Shared primitives
 * ============================================================================= */

/** Product-facing insight kinds returned by the agent (prompt → blocks). */
export type AgentInsightType = 'Trend' | 'Ranking' | 'Pivot' | 'Funnel';

/**
 * SDK data-plane insight kinds sent to the data resolver.
 * Built by `da-insight-sdk` chart dataResolvers — not by the agent.
 */
export type DataInsightType =
  | 'trend'
  | 'contributor'
  | 'pivot'
  | 'comparison'
  | 'summary'
  | 'table'
  | 'xmr';

/** Time bucketing for agent blocks (product enum). */
export type AgentTimeGrain = 'DAILY' | 'WEEKLY' | 'MONTHLY';

/**
 * Time bucketing key the SDK puts on data payloads.
 * Derived from AgentTimeGrain: DAILY→day, WEEKLY→week, MONTHLY→month.
 */
export type DataTimeGrain = 'day' | 'week' | 'month';

/** Metric identity used in both planes. */
export type AnalyticsMetric = {
  /** Stable machine key — must match warehouse / metrics catalog (e.g. `revenue`). */
  metric_name: string;
  /** Human label shown in legends / axes (e.g. `Revenue`). */
  metric_label: string;
};

/** Optional equality filter applied inside a data query. */
export type AnalyticsDimensionFilter = {
  key: string;
  value: string;
};

/* =============================================================================
 * PART 1 — Prompt → Blocks
 * Endpoint: POST /api/analytics/query
 * LibreChat today: packages/data-provider analyticsQueryRequest / analyticsResponse
 * ============================================================================= */

/**
 * Request body for the analytics agent.
 *
 * Today LibreChat sends only `{ prompt }`. Optional fields below are reserved
 * so the real agent can be conversational / multi-turn without a breaking change.
 */
export type AnalyticsQueryRequest = {
  /** Natural-language analytics question from the user. */
  prompt: string;

  /**
   * Optional conversation context for multi-turn (recommended for production).
   * LibreChat can start sending these without changing the response shape.
   */
  conversation_id?: string;
  /** Prior agent turns (text only) — oldest → newest. */
  history?: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
  /** Opaque tenant / workspace scoping if the agent is multi-tenant. */
  tenant_id?: string;
  /** Locale hint for titles / captions (BCP-47), e.g. `en-US`. */
  locale?: string;
};

/** Narrative markdown/plain text block rendered above/between charts. */
export type AnalyticsTextBlock = {
  type: 'text';
  /** User-visible copy. Prefer short paragraphs; markdown is supported in chat. */
  text: string;
};

/**
 * Metadata-only insight block.
 * The client maps this into `da-insight-sdk` Insight props; chart points are NOT here.
 *
 * Dimension cardinality rules (validated client-side today):
 * - Trend:   metrics ≥ 1, dimensions ignored / empty
 * - Ranking: metrics ≥ 1, dimensions length === 1
 * - Pivot:   metrics ≥ 1, dimensions length === 2  [row, column]
 * - Funnel:  metrics ≥ 2 (ordered stages), dimensions length 0 or 1
 */
export type AnalyticsInsightBlock = {
  type: 'insight';
  /** Chart card title (optional). */
  title?: string;
  /** Subtitle / caption (optional). */
  caption?: string;
  insight_type: AgentInsightType;
  /** One or more metrics. Funnel: ordered conversion stages. */
  metrics: AnalyticsMetric[];
  /**
   * Dimension keys from the catalog.
   * Ranking: `[dim]`
   * Pivot:   `[rowDim, colDim]`
   * Funnel:  `[]` or `[breakdownDim]` for grouped funnel
   * Trend:   `[]`
   */
  dimensions?: string[];
  /** Inclusive window start `YYYY-MM-DD`. */
  fromTime: string;
  /** Inclusive window end `YYYY-MM-DD`. */
  toTime: string;
  timeGrain: AgentTimeGrain;
};

export type AnalyticsBlock = AnalyticsTextBlock | AnalyticsInsightBlock;

/**
 * Agent response — ordered lego list.
 * Typical shape: `[text, insight]` or `[text, insight, insight, ...]`.
 * Empty `blocks` is invalid; use a text block to explain “no answer”.
 */
export type AnalyticsQueryResponse = {
  blocks: AnalyticsBlock[];
  /**
   * Optional agent diagnostics (ignored by UI today; useful for debugging).
   */
  meta?: {
    model?: string;
    latency_ms?: number;
    warnings?: string[];
  };
};

/**
 * AgentInsightType → primary DataInsightType used when charts load.
 * (Funnel stages may issue multiple `contributor` or `trend` calls — one per metric.)
 */
export const AGENT_TO_DATA_INSIGHT: Record<AgentInsightType, DataInsightType | DataInsightType[]> = {
  Trend: 'trend',
  Ranking: 'contributor',
  Pivot: 'pivot',
  Funnel: ['contributor', 'trend'],
};

/* =============================================================================
 * PART 2a — Insight config → Data
 * Endpoint: POST /api/analytics/data
 * Client hook: dataResolver({ payload, insight_type })
 * ============================================================================= */

/**
 * Wire payload built by `da-insight-sdk` before calling dataResolver.
 * Field names are snake_ish / SDK legacy — keep them stable.
 */
export type AnalyticsDataPayload = {
  /** Window start `YYYY-MM-DD` (SDK key is lowercase). */
  fromtime: string;
  /** Window end `YYYY-MM-DD`. */
  totime: string;
  /** Metric machine key (same as block `metrics[].metric_name`). */
  metric_name: string;
  /**
   * Present on trend / contributor / funnel calls from Mixed & Funnel resolvers.
   * Absent on some Pivot/Ranking paths today — backend should treat as optional
   * and fall back to inferring grain from (totime - fromtime) if needed.
   */
  timegrain?: DataTimeGrain;
  /**
   * Dimension keys for this fetch:
   * - trend:      omitted or []
   * - contributor: [dimension]          (Ranking / Funnel-by-dim / Mixed split)
   * - pivot:       [rowDimension, colDimension]
   */
  dimensions?: string[];
  /** Extra equality filters (may be empty array). */
  filters?: AnalyticsDimensionFilter[];
};

export type AnalyticsDataRequest = {
  payload: AnalyticsDataPayload;
  insight_type: DataInsightType;
};

/**
 * Row shapes by insight_type
 * -------------------------
 *
 * trend
 *   One row per time bucket:
 *   { fromtime, totime, [metric_name]: number }
 *
 * contributor  (Ranking / dimensional split)
 *   **Wide** single-row form (what Ranking transform expects today):
 *   { fromtime, totime, [memberA]: number, [memberB]: number, ... }
 *   Member keys MUST match values returned by the dimensions endpoint
 *   for the requested dimension (order of keys does not matter).
 *
 * pivot
 *   One row per (rowMember × colMember) cell:
 *   { [rowDim]: string, [colDim]: string, [metric_name]: number }
 *   Example: { country: "IN", channel: "web", revenue: 120 }
 *
 * comparison / summary / table / xmr
 *   Reserved for SDK chart types we are not driving from the agent yet.
 *   Backend may return `{ data: [] }` for unsupported kinds.
 */
export type AnalyticsDataRow = Record<string, string | number>;

export type AnalyticsDataResponse = {
  data: AnalyticsDataRow[];
  /** Optional natural-language takeaway shown if explanation UI is enabled. */
  interpretation?: string;
  /** Optional SQL / warehouse query string for debugging / “view query”. */
  query?: string;
};

/* =============================================================================
 * PART 2b — Dimension values
 * Endpoint: POST /api/analytics/dimensions
 * Client hook: dimensionValuesResolver(dimension: string) => Promise<string[]>
 * ============================================================================= */

export type AnalyticsDimensionsRequest = {
  /** Dimension catalog key, e.g. `country`, `channel`, `location`. */
  dimension: string;
  /**
   * Optional scope — recommended so member lists match the insight window.
   * Client can start omitting these; backend may ignore until ready.
   */
  fromtime?: string;
  totime?: string;
  metric_name?: string;
  filters?: AnalyticsDimensionFilter[];
  tenant_id?: string;
};

/**
 * Ordered member values for headers / ranking segments / funnel series.
 * Order IS significant (Pivot column order, Ranking display order).
 */
export type AnalyticsDimensionsResponse = {
  dimension: string;
  values: string[];
};

/**
 * Convenience: current client mock signature is just `(dimension) => string[]`.
 * Production adapter should wrap POST /dimensions and return `.values`.
 */
export type DimensionValuesResolver = (dimension: string) => Promise<string[]>;

export type DataResolver = (args: AnalyticsDataRequest) => Promise<AnalyticsDataResponse>;

/* =============================================================================
 * Examples (for backend fixtures / contract tests)
 * ============================================================================= */

/** Example — Part 1 request */
export const EXAMPLE_QUERY_REQUEST: AnalyticsQueryRequest = {
  prompt: 'Show revenue trend monthly and a pivot by country and channel',
};

/** Example — Part 1 response */
export const EXAMPLE_QUERY_RESPONSE: AnalyticsQueryResponse = {
  blocks: [
    {
      type: 'text',
      text: 'Here is the monthly revenue trend and a country × channel pivot.',
    },
    {
      type: 'insight',
      title: 'Revenue trend',
      insight_type: 'Trend',
      metrics: [{ metric_name: 'revenue', metric_label: 'Revenue' }],
      dimensions: [],
      fromTime: '2026-01-01',
      toTime: '2026-06-30',
      timeGrain: 'MONTHLY',
    },
    {
      type: 'insight',
      title: 'Revenue pivot',
      insight_type: 'Pivot',
      metrics: [{ metric_name: 'revenue', metric_label: 'Revenue' }],
      dimensions: ['country', 'channel'],
      fromTime: '2026-01-01',
      toTime: '2026-06-30',
      timeGrain: 'MONTHLY',
    },
  ],
};

/** Example — Part 2a trend */
export const EXAMPLE_TREND_REQUEST: AnalyticsDataRequest = {
  insight_type: 'trend',
  payload: {
    fromtime: '2026-01-01',
    totime: '2026-06-30',
    metric_name: 'revenue',
    timegrain: 'month',
    filters: [],
  },
};

export const EXAMPLE_TREND_RESPONSE: AnalyticsDataResponse = {
  data: [
    { fromtime: '2026-01-01', totime: '2026-01-31', revenue: 1000 },
    { fromtime: '2026-02-01', totime: '2026-02-28', revenue: 1200 },
    { fromtime: '2026-03-01', totime: '2026-03-31', revenue: 1500 },
  ],
  interpretation: 'Revenue rose through Q1.',
};

/** Example — Part 2a contributor (Ranking) */
export const EXAMPLE_CONTRIBUTOR_REQUEST: AnalyticsDataRequest = {
  insight_type: 'contributor',
  payload: {
    fromtime: '2026-01-01',
    totime: '2026-06-30',
    metric_name: 'revenue',
    timegrain: 'month',
    dimensions: ['country'],
    filters: [],
  },
};

export const EXAMPLE_CONTRIBUTOR_RESPONSE: AnalyticsDataResponse = {
  data: [
    {
      fromtime: '2026-01-01',
      totime: '2026-06-30',
      IN: 120,
      US: 108,
      DE: 96,
      GB: 84,
    },
  ],
};

/** Example — Part 2a pivot */
export const EXAMPLE_PIVOT_REQUEST: AnalyticsDataRequest = {
  insight_type: 'pivot',
  payload: {
    fromtime: '2026-01-01',
    totime: '2026-06-30',
    metric_name: 'revenue',
    dimensions: ['country', 'channel'],
    filters: [],
  },
};

export const EXAMPLE_PIVOT_RESPONSE: AnalyticsDataResponse = {
  data: [
    { country: 'IN', channel: 'web', revenue: 120 },
    { country: 'IN', channel: 'app', revenue: 108 },
    { country: 'US', channel: 'web', revenue: 96 },
    { country: 'US', channel: 'app', revenue: 84 },
  ],
};

/** Example — Part 2b dimensions */
export const EXAMPLE_DIMENSIONS_REQUEST: AnalyticsDimensionsRequest = {
  dimension: 'country',
  fromtime: '2026-01-01',
  totime: '2026-06-30',
  metric_name: 'revenue',
};

export const EXAMPLE_DIMENSIONS_RESPONSE: AnalyticsDimensionsResponse = {
  dimension: 'country',
  values: ['IN', 'US', 'DE', 'GB'],
};

/* =============================================================================
 * HTTP status / error envelope (recommended)
 * ============================================================================= */

export type AnalyticsApiError = {
  error: string;
  code?:
    | 'INVALID_REQUEST'
    | 'UNAUTHORIZED'
    | 'FORBIDDEN'
    | 'NOT_FOUND'
    | 'UPSTREAM_ERROR'
    | 'TIMEOUT';
  details?: unknown;
};

/**
 * Suggested status codes
 * - 200: success
 * - 400: schema / validation failure
 * - 401 / 403: auth
 * - 502 / 504: warehouse / LLM upstream failure
 */

/* =============================================================================
 * LibreChat integration checklist
 * =============================================================================
 *
 * Part 1 (already wired):
 *   client → POST /api/analytics/query → LibreChat API → ANALYTICS_AGENT_URL or stub
 *   Response blocks stored on assistant message metadata.analytics.blocks
 *
 * Part 2 (client resolvers → live proxies):
 *   analyticsDataResolver            → POST /api/analytics/data
 *   createDimensionValuesResolver    → POST /api/analytics/dimensions  (return .values)
 *
 * Do NOT change AgentInsightType or block field names without a coordinated
 * client release — they are persisted in Mongo message metadata and localStorage reports.
 */
