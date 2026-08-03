/**
 * Card.Header sub-component
 * @module components/card
 */
import React from 'react';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import type { CardHeaderProps } from './types';
import { cardDefaultTheme } from './types';

/**
 * Card.Header component
 *
 * The header row of a card: an optional leading icon, the title, and optional
 * content pinned to the trailing edge.
 */
export const CardHeader: React.FC<CardHeaderProps> = ({
  children,
  className,
  ozid,
  icon,
  end,
}) => {
  const theme = useTheme('card', cardDefaultTheme);

  return (
    <div className={theme.header?.({ className }) ?? className} data-ozid={ozid} data-slot="header">
      {icon && (
        <Slot
          baseOzid={ozid}
          className={theme.headerIcon?.({}) ?? ''}
          slotName="headerIcon"
          slot={icon}
          component="span"
          aria-hidden="true"
        />
      )}
      {children}
      {end && (
        <Slot
          baseOzid={ozid}
          className={theme.headerEnd?.({}) ?? ''}
          slotName="headerEnd"
          slot={end}
          component="span"
        />
      )}
    </div>
  );
};

CardHeader.displayName = 'Card.Header';
