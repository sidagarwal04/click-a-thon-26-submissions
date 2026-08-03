/**
 * Toast.Body sub-component
 * @module components/toast
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { ToastBodyProps } from './types';
import { toastDefaultTheme } from './types';

/**
 * Toast.Body component
 *
 * Container for custom body content in the toast
 */
export const ToastBody: React.FC<ToastBodyProps> = ({ children, className, ozid }) => {
  const theme = useTheme('toast', toastDefaultTheme);

  return (
    <div className={theme.body?.({ className }) ?? className} data-ozid={ozid} data-slot="body">
      {children}
    </div>
  );
};

ToastBody.displayName = 'Toast.Body';
