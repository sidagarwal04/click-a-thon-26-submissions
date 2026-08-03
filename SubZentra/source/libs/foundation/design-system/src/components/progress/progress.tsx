/**
 * Progress component
 * @module components/progress
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { OIComponentRef } from '../../types';
import type { ProgressComponent, ProgressProps } from './types';
import { progressDefaultTheme } from './types';

/**
 * Progress component
 *
 * A progress bar for showing completion status with accessible labeling.
 *
 * @example
 * // Determinate progress
 * <Progress value={60} aria-label="Upload progress" />
 *
 * @example
 * // Indeterminate loading
 * <Progress indeterminate aria-label="Loading" />
 *
 * @example
 * // With intent
 * <Progress value={100} intent="success" aria-label="Complete" />
 */
export const Progress: ProgressComponent = React.forwardRef<HTMLDivElement, ProgressProps>(
  function Progress(
    {
      className,
      ozid,
      value = 0,
      max = 100,
      intent = 'primary',
      size = 'md',
      indeterminate,
      indicator,
      'aria-label': ariaLabel,
      'aria-labelledby': ariaLabelledBy,
      ...rest
    },
    ref: OIComponentRef<'div'>,
  ) {
    const theme = useTheme('progress', progressDefaultTheme);

    // Clamp value between 0 and max
    const clampedValue = Math.min(Math.max(value, 0), max);
    const percentage = (clampedValue / max) * 100;

    return (
      <div
        ref={ref}
        role="progressbar"
        aria-valuenow={indeterminate ? undefined : clampedValue}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        className={theme.root({ className, intent, size, indeterminate })}
        data-ozid={ozid}
        {...rest}
      >
        <div
          className={theme.indicator?.({ intent, size, indeterminate }) ?? ''}
          style={{
            width: indeterminate ? '50%' : `${percentage}%`,
          }}
          data-ozid={ozid ? `${ozid}__indicator` : undefined}
        />
      </div>
    );
  },
) as ProgressComponent;

Progress.displayName = 'Progress';
