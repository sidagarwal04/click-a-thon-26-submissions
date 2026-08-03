/**
 * Drawer.Body sub-component
 * @module components/drawer
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { DrawerBodyProps } from './types';
import { drawerDefaultTheme } from './types';

/**
 * Drawer.Body component
 *
 * Scrollable container for the main drawer content.
 */
export const DrawerBody: React.FC<DrawerBodyProps> = ({ children, className, ozid }) => {
  const theme = useTheme('drawer', drawerDefaultTheme);

  return (
    <div className={theme.body?.({ className }) ?? className} data-ozid={ozid} data-slot="body">
      {children}
    </div>
  );
};

DrawerBody.displayName = 'Drawer.Body';
