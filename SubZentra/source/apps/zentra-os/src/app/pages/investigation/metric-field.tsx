import { motion } from 'motion/react';

import type { MetricComparison } from '../../types';

/**
 * One governed metric, drawn as the comparison it is.
 */
export const MetricField = ({ metric }: { readonly metric: MetricComparison }) => {
  const previous = Number(metric.previous_value);
  const current = Number(metric.current_value);
  const maximum = Math.max(previous, current, 1);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-4">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
          {metric.metric.replace(/_/g, ' ')}
        </span>
        <strong className="font-mono text-lg text-foreground">
          {metric.unit === 'USD' ? '$' : ''}
          {metric.current_value}
          {metric.unit === 'percent' ? '%' : ''}
        </strong>
      </div>

      {/* `role="img"` because a bare div may not carry an accessible name:
          axe reports aria-prohibited-attr, and the label is dropped by the
          very readers it was added for. The bars are a picture of the
          comparison, so that is the honest role. */}
      <div
        className="flex flex-col gap-1"
        role="img"
        aria-label={`${metric.metric} comparison`}
      >
        <motion.span
          className="h-1.5 origin-left bg-border-emphasis"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: previous / maximum }}
          transition={{ duration: 0.28 }}
        />
        <motion.span
          className="h-1.5 origin-left bg-primary"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: current / maximum }}
          transition={{ duration: 0.32, delay: 0.08 }}
        />
      </div>

      {/* The periods come from the agent that chose the granularity. They were
          once hardcoded to June and July from the one scenario that existed,
          and captioned an October-to-November finding with the wrong months the
          first time a second scenario ran. Where the agent named no period we
          render none: a metric that cannot say what it compares says nothing
          about it. */}
      <small className="font-mono text-[10px] text-foreground-muted">
        {metric.previous_label && metric.current_label ? (
          <>
            {metric.previous_label} {metric.previous_value} → {metric.current_label}{' '}
            {metric.current_value} {metric.unit}
          </>
        ) : (
          <>
            {metric.previous_value} → {metric.current_value} {metric.unit}
          </>
        )}
      </small>
    </div>
  );
};
