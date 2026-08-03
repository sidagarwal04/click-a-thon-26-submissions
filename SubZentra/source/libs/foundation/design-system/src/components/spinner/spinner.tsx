/**
 * Spinner component - Loading indicator
 * @module components/spinner
 */

import React from 'react';

import { useTheme } from '../../theme';
import type { SpinnerComponent, SpinnerProps } from './types';
import { spinnerDefaultTheme } from './types';

/**
 * Spinner component
 *
 * A loading indicator with accessible labeling for screen readers.
 *
 * @example
 * <Spinner />
 *
 * @example
 * <Spinner size="lg" aria-label="Loading content" />
 *
 * @example
 * // With custom component
 * <Spinner component="div" />
 */
export const Spinner: SpinnerComponent = React.forwardRef(function Spinner<
  T extends React.ElementType = 'span',
>(
  {
    component,
    className,
    ozid,
    size = 'md',
    'aria-label': ariaLabel = 'Loading',
    ...rest
  }: SpinnerProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('spinner', spinnerDefaultTheme);
  const Element = component ?? 'span';

  return (
    <Element
      ref={ref}
      role="status"
      aria-label={ariaLabel}
      aria-live="polite"
      className={theme.root({ className, size })}
      data-ozid={ozid}
      {...rest}
    />
  );
}) as SpinnerComponent;

(Spinner as React.FC).displayName = 'Spinner';
