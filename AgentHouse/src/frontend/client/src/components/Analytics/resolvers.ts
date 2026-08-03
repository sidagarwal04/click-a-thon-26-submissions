import { dataService } from 'librechat-data-provider';
import type {
  AnalyticsDataInsightType,
  AnalyticsDataRequest,
  AnalyticsDimensionFilter,
} from 'librechat-data-provider';

type DataResolverArgs = {
  payload: object;
  insight_type: string;
};

type DataResolverResponse = {
  data: Array<Record<string, string | number>>;
  interpretation?: string;
  query?: string;
};

type DimensionContext = {
  fromtime?: string;
  totime?: string;
  metric_name?: string;
};

function asRecord(payload: object): Record<string, unknown> {
  return payload as Record<string, unknown>;
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function asStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const values = value.filter((item): item is string => typeof item === 'string');
  return values.length > 0 ? values : undefined;
}

function asFilters(value: unknown): AnalyticsDimensionFilter[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const filters: AnalyticsDimensionFilter[] = [];
  for (const item of value) {
    if (
      item &&
      typeof item === 'object' &&
      typeof (item as { key?: unknown }).key === 'string' &&
      typeof (item as { value?: unknown }).value === 'string'
    ) {
      filters.push({
        key: (item as { key: string }).key,
        value: (item as { value: string }).value,
      });
    }
  }
  return filters.length > 0 ? filters : undefined;
}

function normalizeDataRows(
  rows: Array<Record<string, string | number | null>>,
): Array<Record<string, string | number>> {
  return rows.map((row) => {
    const next: Record<string, string | number> = {};
    for (const [key, value] of Object.entries(row)) {
      if (value !== null) {
        next[key] = value;
      }
    }
    return next;
  });
}

/**
 * Live dataResolver for da-insight-sdk — POST /api/analytics/data via LibreChat.
 */
export async function analyticsDataResolver({
  payload,
  insight_type,
}: DataResolverArgs): Promise<DataResolverResponse> {
  const fields = asRecord(payload);
  const fromtime = asString(fields.fromtime);
  const totime = asString(fields.totime);
  const metric_name = asString(fields.metric_name);

  if (!fromtime || !totime || !metric_name) {
    throw new Error('Analytics data payload missing fromtime, totime, or metric_name');
  }

  if (insight_type !== 'trend' && insight_type !== 'contributor' && insight_type !== 'pivot') {
    return { data: [] };
  }

  const tg = asString(fields.timegrain);
  const timegrain =
    tg === 'day' || tg === 'week' || tg === 'month' ? tg : undefined;

  const request: AnalyticsDataRequest = {
    insight_type: insight_type as AnalyticsDataInsightType,
    payload: {
      fromtime,
      totime,
      metric_name,
      timegrain,
      dimensions: asStringArray(fields.dimensions),
      filters: asFilters(fields.filters),
    },
  };

  const response = await dataService.fetchAnalyticsData(request);
  return {
    data: normalizeDataRows(response.data),
    interpretation: response.interpretation ?? undefined,
    query: response.query ?? undefined,
  };
}

/**
 * Live dimensionValuesResolver — POST /api/analytics/dimensions via LibreChat.
 * Optional context pins the window/metric to the insight block.
 */
export function createDimensionValuesResolver(context: DimensionContext = {}) {
  return async function analyticsDimensionValuesResolver(dimension: string): Promise<string[]> {
    const response = await dataService.fetchAnalyticsDimensions({
      dimension,
      fromtime: context.fromtime,
      totime: context.totime,
      metric_name: context.metric_name,
    });
    return response.values;
  };
}
