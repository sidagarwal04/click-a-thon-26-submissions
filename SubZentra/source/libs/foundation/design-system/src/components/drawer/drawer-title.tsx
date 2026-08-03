/**
 * Drawer.Title sub-component
 * @module components/drawer
 */
import React from 'react';

import { Dialog } from '@base-ui/react/dialog';

import { useTheme } from '../../theme';
import { useDrawerContext } from './drawer.context';
import type { DrawerTitleProps } from './types';
import { drawerDefaultTheme } from './types';

/**
 * Drawer.Title component
 *
 * Title text for the drawer.
 */
export const DrawerTitle: React.FC<DrawerTitleProps> = ({ children, className, ozid }) => {
  const theme = useTheme('drawer', drawerDefaultTheme);
  const { titleId } = useDrawerContext();

  return (
    <Dialog.Title
      id={titleId}
      className={theme.title?.({ className }) ?? className}
      data-ozid={ozid}
      data-slot="title"
    >
      {children}
    </Dialog.Title>
  );
};

DrawerTitle.displayName = 'Drawer.Title';
