/**
 * Tabs.List sub-component
 * @module components/tabs
 */
import React from 'react';

import { Tabs as TabsPrimitive } from '@base-ui/react/tabs';

import { useTheme } from '../../theme';
import { useTabsContext } from './tabs.context';
import type { TabsListProps } from './types';
import { tabsDefaultTheme } from './types';

/**
 * Tabs.List component
 *
 * Container for tab triggers.
 */
export const TabsList: React.FC<TabsListProps> = ({ children, className, ozid }) => {
  const theme = useTheme('tabs', tabsDefaultTheme);
  const { variant, fullWidth } = useTabsContext();

  return (
    <TabsPrimitive.List
      className={theme.list?.({ className, variant, fullWidth }) ?? className}
      data-ozid={ozid}
      data-slot="list"
    >
      {children}
    </TabsPrimitive.List>
  );
};

TabsList.displayName = 'Tabs.List';
