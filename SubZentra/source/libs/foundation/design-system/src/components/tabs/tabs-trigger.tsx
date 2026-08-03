/**
 * Tabs.Trigger sub-component
 * @module components/tabs
 */
import React from 'react';

import { Tabs as TabsPrimitive } from '@base-ui/react/tabs';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { useTabsContext } from './tabs.context';
import type { TabTriggerProps } from './types';
import { tabsDefaultTheme } from './types';

/**
 * Tabs.Trigger component
 *
 * Button that activates a tab panel.
 */
export const TabsTrigger: React.FC<TabTriggerProps> = ({
  value,
  disabled,
  start,
  end,
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('tabs', tabsDefaultTheme);
  const { size, variant, fullWidth } = useTabsContext();

  return (
    <TabsPrimitive.Tab
      value={value}
      disabled={disabled}
      className={theme.trigger?.({ className, size, variant, fullWidth }) ?? className}
      data-ozid={ozid}
      data-slot="trigger"
    >
      {/* Start slot */}
      {start && (
        <Slot
          baseOzid={ozid}
          className={theme.triggerStart?.({ size }) ?? ''}
          slotName="start"
          slot={start}
          component="span"
          aria-hidden="true"
        />
      )}

      {children}

      {/* End slot */}
      {end && (
        <Slot
          baseOzid={ozid}
          className={theme.triggerEnd?.({ size }) ?? ''}
          slotName="end"
          slot={end}
          component="span"
        />
      )}
    </TabsPrimitive.Tab>
  );
};

TabsTrigger.displayName = 'Tabs.Trigger';
