/**
 * Drawer.Header sub-component
 * @module components/drawer
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { DrawerHeaderProps } from './types';
import { drawerDefaultTheme } from './types';

/**
 * Drawer.Header component
 *
 * Container for the drawer header (title, description, close button).
 */
export const DrawerHeader: React.FC<DrawerHeaderProps> = ({ children, className, ozid }) => {
  const theme = useTheme('drawer', drawerDefaultTheme);

  return (
    <div className={theme.header?.({ className }) ?? className} data-ozid={ozid} data-slot="header">
      {children}
    </div>
  );
};

DrawerHeader.displayName = 'Drawer.Header';
