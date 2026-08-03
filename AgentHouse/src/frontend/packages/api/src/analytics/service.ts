import { logger } from '@librechat/data-schemas';
import {
  analyticsDataRequestSchema,
  analyticsDataResponseSchema,
  analyticsDimensionsRequestSchema,
  analyticsDimensionsResponseSchema,
  analyticsQueryRequestSchema,
  analyticsResponseSchema,
} from 'librechat-data-provider';
import type {
  AnalyticsDataRequest,
  AnalyticsDataResponse,
  AnalyticsDimensionsRequest,
  AnalyticsDimensionsResponse,
  AnalyticsQueryRequest,
  AnalyticsResponse,
} from 'librechat-data-provider';

function backendBaseUrl(): string | undefined {
  const base = process.env.ANALYTICS_BACKEND_BASE_URL?.trim();
  if (base) {
    return base.replace(/\/$/, '');
  }
  // Legacy: full URL to /query endpoint
  const legacy = process.env.ANALYTICS_AGENT_URL?.trim();
  if (!legacy) {
    return undefined;
  }
  return legacy.replace(/\/api\/analytics\/query\/?$/i, '').replace(/\/$/, '');
}

function timeoutMs(): number {
  return Number(process.env.ANALYTICS_AGENT_TIMEOUT_MS) || 60000;
}

async function postJson<T>(
  path: string,
  body: unknown,
  parse: (value: unknown) => { success: true; data: T } | { success: false; error: unknown },
  label: string,
): Promise<T> {
  const base = backendBaseUrl();
  if (!base) {
    throw new Error('ANALYTICS_BACKEND_BASE_URL is not configured');
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs());

  try {
    const response = await fetch(`${base}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const text = await response.text().catch(() => '');
    let json: unknown = undefined;
    if (text) {
      try {
        json = JSON.parse(text);
      } catch {
        json = undefined;
      }
    }

    if (!response.ok) {
      const detail =
        typeof json === 'object' && json && 'detail' in json
          ? JSON.stringify((json as { detail: unknown }).detail).slice(0, 300)
          : text.slice(0, 300);
      throw new Error(`${label} upstream ${response.status}${detail ? `: ${detail}` : ''}`);
    }

    const parsed = parse(json);
    if (!parsed.success) {
      logger.error(`[analytics] ${label} invalid payload`, parsed.error);
      throw new Error(`${label} response failed schema validation`);
    }
    return parsed.data;
  } finally {
    clearTimeout(timer);
  }
}

function unavailableQueryResponse(reason: string): AnalyticsResponse {
  return {
    blocks: [
      {
        type: 'text',
        text: `Analytics is temporarily unavailable. ${reason}`,
      },
    ],
  };
}

/**
 * Prompt → metadata-only blocks via shared backend.
 * Fail-safe: returns a text-only block (no fake insights) if upstream is down.
 */
export async function resolveAnalyticsQuery(
  request: AnalyticsQueryRequest,
): Promise<AnalyticsResponse> {
  if (!backendBaseUrl()) {
    return unavailableQueryResponse('Backend URL is not configured.');
  }

  try {
    return await postJson(
      '/api/analytics/query',
      request,
      (value) => analyticsResponseSchema.safeParse(value),
      'query',
    );
  } catch (error) {
    logger.error('[analytics] Query upstream failed — returning text fallback', error);
    const message = error instanceof Error ? error.message : 'Unknown error';
    return unavailableQueryResponse(message);
  }
}

export async function resolveAnalyticsData(
  request: AnalyticsDataRequest,
): Promise<AnalyticsDataResponse> {
  return postJson(
    '/api/analytics/data',
    request,
    (value) => analyticsDataResponseSchema.safeParse(value),
    'data',
  );
}

export async function resolveAnalyticsDimensions(
  request: AnalyticsDimensionsRequest,
): Promise<AnalyticsDimensionsResponse> {
  return postJson(
    '/api/analytics/dimensions',
    request,
    (value) => analyticsDimensionsResponseSchema.safeParse(value),
    'dimensions',
  );
}

export function parseAnalyticsQueryBody(body: unknown): AnalyticsQueryRequest {
  return analyticsQueryRequestSchema.parse(body);
}

export function parseAnalyticsDataBody(body: unknown): AnalyticsDataRequest {
  return analyticsDataRequestSchema.parse(body);
}

export function parseAnalyticsDimensionsBody(body: unknown): AnalyticsDimensionsRequest {
  return analyticsDimensionsRequestSchema.parse(body);
}
