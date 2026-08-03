/**
 * Skeleton component
 * @module components/skeleton
 */
import React from 'react';

import { useTheme } from '../../theme';
import { cn } from '../../utils/cn';
import type { SkeletonComponent, SkeletonProps } from './types';
import { skeletonDefaultTheme } from './types';

const RADIUS_MAP = {
  none: 'rounded-none',
  sm: 'rounded-sm',
  md: 'rounded-md',
  lg: 'rounded-lg',
  full: 'rounded-full',
} as const;

/**
 * Skeleton component
 *
 * A placeholder component for loading states that mimics content shape.
 *
 * @example
 * // Text line skeleton
 * <Skeleton width="200px" height="16px" />
 *
 * @example
 * // Avatar skeleton
 * <Skeleton width={48} height={48} radius="full" />
 *
 * @example
 * // Card skeleton
 * <div aria-busy="true">
 *   <Skeleton width="100%" height="200px" radius="lg" />
 *   <Skeleton width="60%" height="24px" />
 *   <Skeleton width="100%" height="16px" />
 * </div>
 */
export const Skeleton: SkeletonComponent = React.forwardRef(function Skeleton<
  T extends React.ElementType = 'div',
>(
  {
    component,
    className,
    ozid,
    animated = true,
    width,
    height,
    radius = 'md',
    style,
    ...rest
  }: SkeletonProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('skeleton', skeletonDefaultTheme);
  const Element = component ?? 'div';

  const combinedStyle: React.CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
    ...style,
  };

  return (
    <Element
      ref={ref}
      className={cn(theme.root({ animated }), RADIUS_MAP[radius], className)}
      data-ozid={ozid}
      style={combinedStyle}
      aria-hidden="true"
      {...rest}
    />
  );
}) as SkeletonComponent;

(Skeleton as React.FC).displayName = 'Skeleton';
