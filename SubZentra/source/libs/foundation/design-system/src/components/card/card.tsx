/**
 * Card component
 * @module components/card
 */
import React from 'react';

import { useTheme } from '../../theme';
import { CardHeader } from './card-header';
import { CardTitle } from './card-title';
import type { CardComponent, CardProps } from './types';
import { cardDefaultTheme } from './types';

/**
 * Card component
 *
 * A bordered surface that groups related content into one panel.
 *
 * @example
 * <Card>
 *   <Card.Header icon={<ShieldIcon />}>
 *     <Card.Title>Security protocols</Card.Title>
 *   </Card.Header>
 *   <p>Require biometric trace for all critical analysis executions.</p>
 * </Card>
 *
 * @example
 * // Accent border for the card that carries the page's primary signal
 * <Card emphasis padding="sm">…</Card>
 */
const CardRoot = React.forwardRef(function Card<T extends React.ElementType = 'section'>(
  { component, className, children, ozid, padding = 'md', emphasis, ...rest }: CardProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('card', cardDefaultTheme);
  const Element = component ?? 'section';

  return (
    <Element
      ref={ref}
      className={theme.root({ className, padding, emphasis })}
      data-ozid={ozid}
      {...rest}
    >
      {children}
    </Element>
  );
}) as unknown as CardComponent;

CardRoot.displayName = 'Card';
CardRoot.Header = CardHeader;
CardRoot.Title = CardTitle;

export const Card = CardRoot;
