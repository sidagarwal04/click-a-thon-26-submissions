/**
 * Popover.Content sub-component
 * @module components/popover
 */
import React from 'react';

import { Popover as PopoverPrimitive } from '@base-ui/react/popover';

import { useTheme } from '../../theme';
import { usePopoverContext } from './popover.context';
import type { PopoverContentProps } from './types';
import { popoverDefaultTheme } from './types';

/**
 * Arrow SVG component
 */
const ArrowSvg = (props: React.ComponentProps<'svg'>) => (
  <svg width="10" height="6" viewBox="0 0 10 6" fill="none" {...props}>
    <path d="M0 0L5 6L10 0H0Z" className="fill-current" />
  </svg>
);

/**
 * Popover.Content component
 *
 * Container for the popover content.
 */
export const PopoverContent = React.forwardRef<HTMLDivElement, PopoverContentProps>(
  function PopoverContent({ children, className, ozid, ...rest }, ref) {
    const theme = useTheme('popover', popoverDefaultTheme);
    const { maxWidth, arrow, side, align, sideOffset } = usePopoverContext();

    return (
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Positioner side={side} align={align} sideOffset={sideOffset}>
          {/* rest first: caller-supplied lang, aria and data attributes reach
              the root, but never at the cost of props managed here. */}
          <PopoverPrimitive.Popup
            {...rest}
            ref={ref}
            // arrow is a declared modifier, so the theme has to see it.
            className={theme.popup?.({ className, maxWidth, arrow }) ?? className}
            data-ozid={ozid}
            data-slot="content"
          >
            {arrow && (
              <PopoverPrimitive.Arrow className={theme.arrow?.({}) ?? ''}>
                <ArrowSvg />
              </PopoverPrimitive.Arrow>
            )}
            {children}
          </PopoverPrimitive.Popup>
        </PopoverPrimitive.Positioner>
      </PopoverPrimitive.Portal>
    );
  },
);

PopoverContent.displayName = 'Popover.Content';
