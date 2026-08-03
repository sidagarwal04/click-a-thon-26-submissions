/**
 * Tooltip component - Contextual information on hover
 * @module components/tooltip
 */
import React from 'react';

import { Tooltip as TooltipPrimitive } from '@base-ui/react/tooltip';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import type { TooltipProps } from './types';
import { tooltipDefaultTheme } from './types';

/**
 * Tooltip arrow - a triangular pointer shape for floating UI positioning.
 * This is a UI primitive (not a semantic icon) that connects the tooltip to its anchor.
 */
const TooltipArrowSvg = (props: React.ComponentProps<'svg'>) => (
  <svg width="20" height="10" viewBox="0 0 20 10" fill="none" {...props}>
    <path
      d="M9.66437 2.60207L4.80758 6.97318C4.07308 7.63423 3.11989 8 2.13172 8H0V10H20V8H18.5349C17.5468 8 16.5936 7.63423 15.8591 6.97318L11.0023 2.60207C10.622 2.2598 10.0447 2.25979 9.66437 2.60207Z"
      className="fill-current"
    />
    <path
      d="M8.99542 1.85876C9.75604 1.17425 10.9106 1.17422 11.6713 1.85878L16.5281 6.22989C17.0789 6.72568 17.7938 7.00001 18.5349 7.00001L15.89 7L11.0023 2.60207C10.622 2.2598 10.0447 2.2598 9.66436 2.60207L4.77734 7L2.13171 7.00001C2.87284 7.00001 3.58774 6.72568 4.13861 6.22989L8.99542 1.85876Z"
      className="fill-background"
    />
    <path
      d="M10.3333 3.34539L5.47654 7.71648C4.55842 8.54279 3.36693 9 2.13172 9H0V8H2.13172C3.11989 8 4.07308 7.63423 4.80758 6.97318L9.66437 2.60207C10.0447 2.25979 10.622 2.2598 11.0023 2.60207L15.8591 6.97318C16.5936 7.63423 17.5468 8 18.5349 8H20V9H18.5349C17.2998 9 16.1083 8.54278 15.1901 7.71648L10.3333 3.34539Z"
      className="fill-border"
    />
  </svg>
);

/**
 * Tooltip component
 *
 * A floating tooltip that appears on hover/focus.
 * Useful for providing additional context or descriptions.
 *
 * @example
 * // Basic usage
 * <Tooltip content="This is a tooltip">
 *   <Button>Hover me</Button>
 * </Tooltip>
 *
 * @example
 * // With shortcut
 * <Tooltip content="Copy" shortcut="⌘C">
 *   <IconButton aria-label="Copy"><CopyIcon /></IconButton>
 * </Tooltip>
 *
 * @example
 * // With arrow
 * <Tooltip content="With arrow" arrow>
 *   <Button>Hover me</Button>
 * </Tooltip>
 *
 * @example
 * // Position control
 * <Tooltip content="On the right" side="right" align="start">
 *   <Button>Hover me</Button>
 * </Tooltip>
 */
export const Tooltip = React.forwardRef<HTMLDivElement, TooltipProps>(function Tooltip(
  {
    children,
    ozid,
    content,
    shortcut,
    side = 'top',
    align = 'center',
    arrow = false,
    raw = false,
    delayDuration = 200,
    sideOffset = 4,
    open,
    defaultOpen,
    onOpenChange,
    className,
    ...rest
  },
  ref,
) {
  const theme = useTheme('tooltip', tooltipDefaultTheme);

  return (
    <TooltipPrimitive.Provider delay={delayDuration}>
      <TooltipPrimitive.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
        {/* The plain ozid identifies the element theme.root styles, which is
            the popup below — every other component in the library follows that
            rule, and rootInstanceOf here has always been HTMLDivElement, which
            only the popup is. The trigger takes a suffixed id. */}
        <TooltipPrimitive.Trigger
          data-ozid={ozid ? `${ozid}__trigger` : undefined}
          render={<span className="inline-flex" />}
        >
          {children}
        </TooltipPrimitive.Trigger>

        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Positioner
            sideOffset={sideOffset}
            side={side}
            align={align}
            className={theme.positioner?.({}) ?? ''}
          >
            {/* rest first: caller-supplied lang, aria and data attributes reach
                the root, but never at the cost of the props managed here. */}
            <TooltipPrimitive.Popup
              {...rest}
              ref={ref}
              className={theme.root({ className, side, align, arrow, raw })}
              data-ozid={ozid}
            >
              {/* Arrow pointer (not overridable) */}
              {arrow && (
                <TooltipPrimitive.Arrow className={theme.arrow?.({ side }) ?? ''}>
                  <TooltipArrowSvg />
                </TooltipPrimitive.Arrow>
              )}

              {/* Content slot */}
              {content && (
                <Slot
                  baseOzid={ozid}
                  className={theme.content?.({ raw }) ?? ''}
                  component="div"
                  slot={content}
                  slotName="content"
                />
              )}

              {/* Shortcut slot */}
              {shortcut && (
                <Slot
                  baseOzid={ozid}
                  className={theme.shortcut?.({}) ?? ''}
                  component="div"
                  slot={shortcut}
                  slotName="shortcut"
                />
              )}
            </TooltipPrimitive.Popup>
          </TooltipPrimitive.Positioner>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
});

Tooltip.displayName = 'Tooltip';
