/**
 * Popover.Trigger sub-component
 * @module components/popover
 */
import React from 'react';

import { Popover as PopoverPrimitive } from '@base-ui/react/popover';

import type { PopoverTriggerProps } from './types';

/**
 * Popover.Trigger component
 *
 * Element that opens the popover when clicked.
 */
export const PopoverTrigger: React.FC<PopoverTriggerProps> = ({
  children,
  className,
  ozid,
  ...rest
}) => {
  return (
    <PopoverPrimitive.Trigger className={className} data-ozid={ozid} data-slot="trigger" {...rest}>
      {children}
    </PopoverPrimitive.Trigger>
  );
};

PopoverTrigger.displayName = 'Popover.Trigger';
