/**
 * Toast.Actions sub-component
 * @module components/toast
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { ToastActionsProps } from './types';
import { toastDefaultTheme } from './types';

/**
 * Toast.Actions component
 *
 * Container for action buttons in the toast
 */
export const ToastActions: React.FC<ToastActionsProps> = ({ children, className, ozid }) => {
  const theme = useTheme('toast', toastDefaultTheme);

  return (
    <div
      className={theme.actions?.({ className }) ?? className}
      data-ozid={ozid}
      data-slot="actions"
    >
      {children}
    </div>
  );
};

ToastActions.displayName = 'Toast.Actions';
