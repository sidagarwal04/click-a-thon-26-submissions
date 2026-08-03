/**
 * Tabs component
 * @module components/tabs
 */
import React, { useMemo } from 'react';

import { Tabs as TabsPrimitive } from '@base-ui/react/tabs';

import { useTheme } from '../../theme';
import { TabsContent } from './tabs-content';
import { TabsList } from './tabs-list';
import { TabsTrigger } from './tabs-trigger';
import { TabsContext } from './tabs.context';
import type { TabsComponent, TabsContextValue, TabsProps } from './types';
import { tabsDefaultTheme } from './types';

/**
 * Tabs component
 *
 * A set of layered sections of content shown one at a time.
 *
 * @example
 * <Tabs defaultValue="tab1">
 *   <Tabs.List>
 *     <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
 *     <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
 *   </Tabs.List>
 *   <Tabs.Content value="tab1">Content 1</Tabs.Content>
 *   <Tabs.Content value="tab2">Content 2</Tabs.Content>
 * </Tabs>
 */
const TabsRoot = React.forwardRef<HTMLDivElement, TabsProps>(function Tabs(
  {
    ozid,
    size = 'md',
    variant = 'default',
    fullWidth,
    value,
    defaultValue,
    onValueChange,
    children,
    className,
    ...rest
  },
  ref,
) {
  const theme = useTheme('tabs', tabsDefaultTheme);

  // Context value for sub-components
  const contextValue: TabsContextValue = useMemo(
    () => ({
      size,
      variant,
      fullWidth,
    }),
    [size, variant, fullWidth],
  );

  return (
    <TabsContext.Provider value={contextValue}>
      {/* rest first: caller-supplied lang, aria and data attributes reach the
          root, but never at the cost of the props managed here. */}
      <TabsPrimitive.Root
        {...rest}
        ref={ref}
        value={value}
        defaultValue={defaultValue}
        onValueChange={(newValue) => {
          if (typeof newValue === 'string') {
            onValueChange?.(newValue);
          }
        }}
        className={theme.root?.({ className, size, variant, fullWidth }) ?? className}
        data-ozid={ozid}
      >
        {children}
      </TabsPrimitive.Root>
    </TabsContext.Provider>
  );
}) as TabsComponent;

// Attach sub-components
TabsRoot.displayName = 'Tabs';
TabsRoot.List = TabsList;
TabsRoot.Trigger = TabsTrigger;
TabsRoot.Content = TabsContent;

export const Tabs = TabsRoot;
