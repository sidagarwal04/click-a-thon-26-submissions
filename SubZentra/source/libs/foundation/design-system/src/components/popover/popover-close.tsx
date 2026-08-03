/**
 * Popover.Close sub-component
 * @module components/popover
 */
import React from 'react';

import { Popover as PopoverPrimitive } from '@base-ui/react/popover';

import { Icon } from '@open-zentra/foundation-icons';

import { useTheme } from '../../theme';
import type { PopoverCloseProps } from './types';
import { popoverDefaultTheme } from './types';

/**
 * Popover.Close component
 *
 * Button that closes the popover.
 */
export const PopoverClose: React.FC<PopoverCloseProps> = ({
  children,
  className,
  ozid,
  ...rest
}) => {
  const theme = useTheme('popover', popoverDefaultTheme);

  return (
    <PopoverPrimitive.Close
      className={className || theme.close?.({}) || ''}
      data-ozid={ozid}
      data-slot="close"
      aria-label="Close"
      {...rest}
    >
      {children || <Icon name="x" size="xs" />}
    </PopoverPrimitive.Close>
  );
};

PopoverClose.displayName = 'Popover.Close';
