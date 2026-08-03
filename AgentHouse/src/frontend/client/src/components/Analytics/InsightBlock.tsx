import { memo, useEffect, useMemo, useState } from 'react';
import { ChartTypes, Insight } from 'da-insight-sdk';
import type { AnalyticsInsightBlock } from 'librechat-data-provider';
import { insightBlockKey, mapBlockToInsightProps } from './map';
import { analyticsDataResolver, createDimensionValuesResolver } from './resolvers';
import { cn } from '~/utils';
import 'da-insight-sdk/dist/styles.css';

type InsightBlockProps = {
  block: AnalyticsInsightBlock;
};

const CHARTS_NEEDING_HEIGHT = new Set<ChartTypes>([
  ChartTypes.LINE,
  ChartTypes.BAR,
  ChartTypes.AREA,
  ChartTypes.MIXED,
  ChartTypes.FUNNEL,
  ChartTypes.PIVOT,
  ChartTypes.RANKING,
]);

/** Stable options — Insight clears data whenever metrics/filters identities churn. */
const INSIGHT_OPTIONS = {
  className: 'h-full',
  hideCard: true,
  theme: 'dark' as const,
};

/**
 * Pin SDK payload dates to the agent block window (SDK otherwise recomputes from today).
 */
function createPinnedDataResolver(block: AnalyticsInsightBlock) {
  return async (args: { payload: object; insight_type: string }) => {
    const payload = {
      ...(args.payload as Record<string, unknown>),
      fromtime: block.fromTime,
      totime: block.toTime,
    };
    return analyticsDataResolver({ payload, insight_type: args.insight_type });
  };
}

/**
 * Expand-in reveal so chat layout does not dump ~h-72 in a single paint.
 */
function InsightBlock({ block }: InsightBlockProps) {
  const blockKey = insightBlockKey(block);
  const props = useMemo(() => mapBlockToInsightProps(block), [blockKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const dataResolver = useMemo(() => createPinnedDataResolver(block), [blockKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const dimensionValuesResolver = useMemo(
    () =>
      createDimensionValuesResolver({
        fromtime: block.fromTime,
        totime: block.toTime,
        metric_name: block.metrics[0]?.metric_name,
      }),
    [blockKey], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setExpanded(false);
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => setExpanded(true));
    });
    return () => cancelAnimationFrame(id);
  }, [blockKey]);

  if (!props) {
    return (
      <p className="text-sm text-text-secondary" role="status">
        Unable to render insight
      </p>
    );
  }

  const needsFixedHeight = CHARTS_NEEDING_HEIGHT.has(props.type);

  return (
    <div
      className={cn(
        'grid w-full transition-[grid-template-rows,opacity] duration-300 ease-out',
        expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
      )}
    >
      <div className="min-h-0 overflow-hidden">
        <div
          className={cn('w-full', needsFixedHeight ? 'h-72' : 'min-h-[10rem]')}
          role="figure"
          aria-label={block.title || 'Analytics insight'}
        >
          <Insight
            type={props.type}
            title={props.title}
            description={props.description}
            metrics={props.metrics}
            timeGrain={props.timeGrain}
            timeRange={props.timeRange}
            filters={props.filters}
            dataResolver={dataResolver}
            dimensionValuesResolver={dimensionValuesResolver}
            options={INSIGHT_OPTIONS}
          />
        </div>
      </div>
    </div>
  );
}

export default memo(
  InsightBlock,
  (prev, next) => insightBlockKey(prev.block) === insightBlockKey(next.block),
);
