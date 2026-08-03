/**
 * Drawer.Footer sub-component
 * @module components/drawer
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { DrawerFooterProps } from './types';
import { drawerDefaultTheme } from './types';

/**
 * Drawer.Footer component
 *
 * Container for action buttons at the bottom of the drawer.
 */
export const DrawerFooter: React.FC<DrawerFooterProps> = ({ children, className, ozid }) => {
  const theme = useTheme('drawer', drawerDefaultTheme);

  return (
    <div className={theme.footer?.({ className }) ?? className} data-ozid={ozid} data-slot="footer">
      {children}
    </div>
  );
};

DrawerFooter.displayName = 'Drawer.Footer';
