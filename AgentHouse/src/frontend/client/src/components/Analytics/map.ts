import { ChartTypes, TimeGrain } from 'da-insight-sdk';
import type { AnalyticsInsightBlock } from 'librechat-data-provider';

type InsightMetric = {
  metricKey: string;
  metricLabel: string;
};

type InsightFilters = {
  [metricKey: string]: {
    showDimensionContributionIn?: string;
    showPivotIn?: { row: string; column: string };
  };
};

export type MappedInsightProps = {
  type: ChartTypes;
  title?: string;
  description?: string;
  metrics: InsightMetric[];
  timeGrain: TimeGrain;
  timeRange: number;
  filters: InsightFilters;
};

const CHART_TYPE_MAP: Record<AnalyticsInsightBlock['insight_type'], ChartTypes> = {
  Trend: ChartTypes.AREA,
  Ranking: ChartTypes.RANKING,
  Pivot: ChartTypes.PIVOT,
  Funnel: ChartTypes.FUNNEL,
};

const TIME_GRAIN_MAP: Record<AnalyticsInsightBlock['timeGrain'], TimeGrain> = {
  DAILY: TimeGrain.DAILY,
  WEEKLY: TimeGrain.WEEKLY,
  MONTHLY: TimeGrain.MONTHLY,
};

function daySpan(fromTime: string, toTime: string): number {
  const from = new Date(fromTime).getTime();
  const to = new Date(toTime).getTime();
  if (Number.isNaN(from) || Number.isNaN(to) || to < from) {
    return 180;
  }
  const days = Math.ceil((to - from) / (1000 * 60 * 60 * 24));
  return Math.max(1, days);
}

function isValidBlock(block: AnalyticsInsightBlock): boolean {
  const dims = block.dimensions ?? [];
  if (block.insight_type === 'Ranking') {
    return block.metrics.length >= 1 && dims.length === 1;
  }
  if (block.insight_type === 'Pivot') {
    return block.metrics.length >= 1 && dims.length === 2;
  }
  if (block.insight_type === 'Funnel') {
    return block.metrics.length >= 2 && dims.length <= 1;
  }
  return block.metrics.length >= 1;
}

/** Content identity for memo keys — survives shallow message/report copies. */
export function insightBlockKey(block: AnalyticsInsightBlock): string {
  const metrics = block.metrics
    .map((metric) => `${metric.metric_name}:${metric.metric_label}`)
    .join(',');
  const dimensions = (block.dimensions ?? []).join(',');
  return [
    block.insight_type,
    block.title ?? '',
    block.caption ?? '',
    block.fromTime,
    block.toTime,
    block.timeGrain,
    metrics,
    dimensions,
  ].join('|');
}

/** Map agent insight metadata to da-insight-sdk Insight props. */
export function mapBlockToInsightProps(block: AnalyticsInsightBlock): MappedInsightProps | null {
  if (!isValidBlock(block)) {
    return null;
  }

  const metrics: InsightMetric[] = block.metrics.map((metric) => ({
    metricKey: metric.metric_name,
    metricLabel: metric.metric_label,
  }));

  const filters: InsightFilters = {};
  const metricKey = metrics[0]?.metricKey;
  const dims = block.dimensions ?? [];

  if (block.insight_type === 'Ranking' && metricKey && dims[0]) {
    filters[metricKey] = { showDimensionContributionIn: dims[0] };
  }

  if (block.insight_type === 'Pivot' && metricKey && dims[0] && dims[1]) {
    filters[metricKey] = { showPivotIn: { row: dims[0], column: dims[1] } };
  }

  if (block.insight_type === 'Funnel' && dims[0]) {
    for (const metric of metrics) {
      filters[metric.metricKey] = { showDimensionContributionIn: dims[0] };
    }
  }

  return {
    type: CHART_TYPE_MAP[block.insight_type],
    title: block.title ?? undefined,
    description: block.caption ?? undefined,
    metrics,
    timeGrain: TIME_GRAIN_MAP[block.timeGrain],
    timeRange: daySpan(block.fromTime, block.toTime),
    filters,
  };
}
