/**
 * Badge component
 * @module components/badge
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { BadgeComponent, BadgeProps } from './types';
import { badgeDefaultTheme } from './types';

/**
 * Badge component
 *
 * A small label for highlighting status, counts, or categories.
 *
 * @example
 * <Badge intent="success">Active</Badge>
 *
 * @example
 * <Badge intent="danger" size="sm">3</Badge>
 */
export const Badge = React.forwardRef(function Badge<T extends React.ElementType = 'span'>(
  { component, className, children, ozid, intent = 'default', size = 'md', ...rest }: BadgeProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('badge', badgeDefaultTheme);
  const Element = component ?? 'span';

  return (
    <Element
      ref={ref}
      className={theme.root({ className, intent, size })}
      data-ozid={ozid}
      {...rest}
    >
      {children}
    </Element>
  );
}) as BadgeComponent;

Badge.displayName = 'Badge';
