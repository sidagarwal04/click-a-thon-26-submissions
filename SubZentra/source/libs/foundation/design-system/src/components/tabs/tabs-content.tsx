/**
 * Tabs.Content sub-component
 * @module components/tabs
 */
import React from 'react';

import { Tabs as TabsPrimitive } from '@base-ui/react/tabs';

import { useTheme } from '../../theme';
import { useTabsContext } from './tabs.context';
import type { TabContentProps } from './types';
import { tabsDefaultTheme } from './types';

/**
 * Tabs.Content component
 *
 * Container for tab panel content.
 */
export const TabsContent: React.FC<TabContentProps> = ({
  value,
  forceMount,
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('tabs', tabsDefaultTheme);
  const { size } = useTabsContext();

  return (
    <TabsPrimitive.Panel
      value={value}
      keepMounted={forceMount}
      className={theme.content?.({ className, size }) ?? className}
      data-ozid={ozid}
      data-slot="content"
    >
      {children}
    </TabsPrimitive.Panel>
  );
};

TabsContent.displayName = 'Tabs.Content';
