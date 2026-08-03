/**
 * Toast.Title sub-component
 * @module components/toast
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { ToastTitleProps } from './types';
import { toastDefaultTheme } from './types';

/**
 * Toast.Title component
 *
 * Title text for the toast notification
 */
export const ToastTitle: React.FC<ToastTitleProps> = ({ children, className, ozid }) => {
  const theme = useTheme('toast', toastDefaultTheme);

  return (
    <div
      className={theme.title?.({ className, feedback: 'info' }) ?? className}
      data-ozid={ozid}
      data-slot="title"
    >
      {children}
    </div>
  );
};

ToastTitle.displayName = 'Toast.Title';
