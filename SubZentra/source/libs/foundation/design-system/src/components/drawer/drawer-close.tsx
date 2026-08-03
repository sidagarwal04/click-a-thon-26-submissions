/**
 * Drawer.Close sub-component
 * @module components/drawer
 */
import React from 'react';

import { Dialog } from '@base-ui/react/dialog';

import { Icon } from '@open-zentra/foundation-icons';

import { useTheme } from '../../theme';
import type { DrawerCloseProps } from './types';
import { drawerDefaultTheme } from './types';

/**
 * Drawer.Close component
 *
 * Button that closes the drawer.
 */
export const DrawerClose: React.FC<DrawerCloseProps> = ({ children, className, ozid, ...rest }) => {
  const theme = useTheme('drawer', drawerDefaultTheme);

  return (
    <Dialog.Close
      className={className || theme.close?.({}) || ''}
      data-ozid={ozid}
      data-slot="close"
      aria-label="Close"
      {...rest}
    >
      {children || <Icon name="x" size="sm" />}
    </Dialog.Close>
  );
};

DrawerClose.displayName = 'Drawer.Close';
