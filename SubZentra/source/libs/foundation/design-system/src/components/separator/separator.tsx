/**
 * Separator component
 * @module components/separator
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { SeparatorComponent, SeparatorProps } from './types';
import { separatorDefaultTheme } from './types';

/**
 * Separator component
 *
 * A semantic separator element for visually dividing content.
 *
 * @example
 * // Horizontal separator (default)
 * <Separator />
 *
 * @example
 * // Vertical separator
 * <Separator orientation="vertical" />
 *
 * @example
 * // Decorative separator (no ARIA semantics)
 * <Separator decorative />
 */
export const Separator = React.forwardRef(function Separator<T extends React.ElementType = 'div'>(
  {
    component,
    className,
    ozid,
    orientation = 'horizontal',
    decorative = false,
    ...rest
  }: SeparatorProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('separator', separatorDefaultTheme);
  const Element = component ?? 'div';

  // Determine ARIA attributes based on whether separator is decorative
  const ariaOrientation: 'vertical' | undefined =
    orientation === 'vertical' ? 'vertical' : undefined;
  const semanticProps = decorative
    ? { role: 'none' as const }
    : { role: 'separator' as const, 'aria-orientation': ariaOrientation };

  return (
    <Element
      ref={ref}
      className={theme.root({ className, orientation, decorative })}
      data-ozid={ozid}
      data-orientation={orientation}
      {...semanticProps}
      {...rest}
    />
  );
}) as SeparatorComponent;

Separator.displayName = 'Separator';
