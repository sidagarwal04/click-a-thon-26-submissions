/**
 * EmptyState.Description sub-component
 * @module components/empty-state
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { EmptyStateDescriptionProps } from './types';
import { emptyStateDefaultTheme } from './types';

/**
 * EmptyState.Description component
 *
 * Description text for the empty state
 */
export const EmptyStateDescription: React.FC<EmptyStateDescriptionProps> = ({
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('emptyState', emptyStateDefaultTheme);

  return (
    <p
      className={theme.description?.({ className, size: 'md' }) ?? className}
      data-ozid={ozid}
      data-slot="description"
    >
      {children}
    </p>
  );
};

EmptyStateDescription.displayName = 'EmptyState.Description';
