/**
 * Popover component
 * @module components/popover
 */
import { useMemo } from 'react';

import { Popover as PopoverPrimitive } from '@base-ui/react/popover';

import { PopoverClose } from './popover-close';
import { PopoverContent } from './popover-content';
import { PopoverTrigger } from './popover-trigger';
import { PopoverContext } from './popover.context';
import type { PopoverComponent, PopoverContextValue } from './types';

/**
 * Popover component
 *
 * A floating popup anchored to a trigger element.
 *
 * @example
 * <Popover>
 *   <Popover.Trigger asChild>
 *     <Button>Open Popover</Button>
 *   </Popover.Trigger>
 *   <Popover.Content>
 *     <h4 className="font-semibold">Popover Title</h4>
 *     <p className="text-sm text-muted-foreground">
 *       Popover content goes here.
 *     </p>
 *   </Popover.Content>
 * </Popover>
 */
const PopoverRoot: PopoverComponent = ({
  maxWidth = '320',
  arrow = false,
  side = 'bottom',
  align = 'center',
  sideOffset = 8,
  open,
  defaultOpen,
  onOpenChange,
  children,
}) => {
  // Context value for sub-components
  const contextValue: PopoverContextValue = useMemo(
    () => ({
      maxWidth,
      arrow,
      side,
      align,
      sideOffset,
    }),
    [maxWidth, arrow, side, align, sideOffset],
  );

  return (
    <PopoverContext.Provider value={contextValue}>
      <PopoverPrimitive.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
        {children}
      </PopoverPrimitive.Root>
    </PopoverContext.Provider>
  );
};

// Attach sub-components
PopoverRoot.displayName = 'Popover';
PopoverRoot.Trigger = PopoverTrigger;
PopoverRoot.Content = PopoverContent;
PopoverRoot.Close = PopoverClose;

export const Popover = PopoverRoot;
