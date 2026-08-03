/**
 * Loader component
 * @module components/loader
 */
import React from 'react';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { Skeleton } from '../skeleton';
import { Spinner } from '../spinner';
import type { LoaderComponent, LoaderProps } from './types';
import { loaderDefaultTheme } from './types';

/**
 * Dots loading animation component
 */
const DotsIndicator = ({ dotClassName }: { dotClassName: string }) => (
  <div className="flex items-center gap-1">
    {[0, 1, 2].map((i) => (
      <span key={i} className={dotClassName} style={{ animationDelay: `${i * 0.15}s` }} />
    ))}
  </div>
);

/**
 * Loader component
 *
 * A versatile loading indicator with multiple variants and overlay support.
 *
 * @example
 * // Basic spinner
 * <Loader />
 *
 * @example
 * // With label
 * <Loader label="Loading..." />
 *
 * @example
 * // Full screen overlay
 * <Loader fullScreen loading={isLoading} />
 *
 * @example
 * // Wrap content - shows children when not loading
 * <Loader loading={isLoading}>
 *   <Content />
 * </Loader>
 *
 * @example
 * // Different variants
 * <Loader variant="dots" />
 * <Loader variant="skeleton" />
 */
export const Loader = React.forwardRef(function Loader<T extends React.ElementType = 'div'>(
  {
    component,
    className,
    ozid,
    size = 'md',
    variant = 'spinner',
    fullScreen,
    overlay,
    inline,
    loading = true,
    label,
    indicator,
    'aria-label': ariaLabel,
    children,
    ...rest
  }: LoaderProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('loader', loaderDefaultTheme);
  const Element = component ?? 'div';

  // When not loading, render children
  if (!loading && children) {
    return <>{children}</>;
  }

  // Don't render anything if not loading and no children
  if (!loading) {
    return null;
  }

  const renderIndicator = () => {
    // Custom indicator via slot
    if (indicator) {
      return (
        <Slot
          baseOzid={ozid}
          className={theme.indicator?.({ size }) ?? ''}
          slotName="indicator"
          slot={indicator}
          component="span"
        />
      );
    }

    // Built-in variants
    switch (variant) {
      case 'dots':
        return <DotsIndicator dotClassName={theme.dot?.({ size }) ?? ''} />;
      case 'skeleton':
        return (
          <div className="space-y-2">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-4 w-44" />
          </div>
        );
      case 'spinner':
      default:
        return <Spinner size={size} aria-hidden="true" />;
    }
  };

  const loaderContent = (
    <Element
      ref={ref}
      className={theme.root({ className, size, variant, fullScreen, overlay, inline })}
      data-ozid={ozid}
      role="status"
      aria-busy="true"
      aria-live="polite"
      aria-label={ariaLabel || (typeof label === 'string' ? label : 'Loading')}
      {...rest}
    >
      {renderIndicator()}

      {label && (
        <Slot
          baseOzid={ozid}
          className={theme.label?.({ size }) ?? ''}
          slotName="label"
          slot={label}
          component="span"
        >
          {typeof label === 'string' ? label : null}
        </Slot>
      )}
    </Element>
  );

  // Wrap with relative container for overlay mode
  if (overlay && children) {
    return (
      <div className={theme.wrapper?.({ overlay }) ?? 'relative'}>
        {children}
        {loaderContent}
      </div>
    );
  }

  return loaderContent;
}) as LoaderComponent;

Loader.displayName = 'Loader';
