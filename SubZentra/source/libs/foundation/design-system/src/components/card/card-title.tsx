/**
 * Card.Title sub-component
 * @module components/card
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { CardTitleProps } from './types';
import { cardDefaultTheme } from './types';

/**
 * Card.Title component
 *
 * The label for a card's contents.
 */
export const CardTitle: React.FC<CardTitleProps> = ({ children, className, ozid }) => {
  const theme = useTheme('card', cardDefaultTheme);

  return (
    <h2 className={theme.title?.({ className }) ?? className} data-ozid={ozid} data-slot="title">
      {children}
    </h2>
  );
};

CardTitle.displayName = 'Card.Title';
