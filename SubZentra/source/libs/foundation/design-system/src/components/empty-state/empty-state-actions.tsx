/**
 * EmptyState.Actions sub-component
 * @module components/empty-state
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { EmptyStateActionsProps } from './types';
import { emptyStateDefaultTheme } from './types';

/**
 * EmptyState.Actions component
 *
 * Container for action buttons in the empty state
 */
export const EmptyStateActions: React.FC<EmptyStateActionsProps> = ({
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('emptyState', emptyStateDefaultTheme);

  return (
    <div
      className={theme.actions?.({ className, size: 'md' }) ?? className}
      data-ozid={ozid}
      data-slot="actions"
    >
      {children}
    </div>
  );
};

EmptyStateActions.displayName = 'EmptyState.Actions';
