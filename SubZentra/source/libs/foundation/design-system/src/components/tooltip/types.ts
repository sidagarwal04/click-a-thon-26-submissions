/**
 * Tooltip component type definitions
 * @module components/tooltip/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentSlotProps,
  OIDefaultProps,
} from '../../types';

/**
 * Tooltip variant definitions
 */
export const TooltipVariants = {
  side: ['top', 'right', 'bottom', 'left'] as const,
  align: ['start', 'center', 'end'] as const,
} as const;

/**
 * Tooltip modifier definitions
 */
export const TooltipModifiers = ['arrow', 'raw'] as const;

/**
 * Tooltip slot definitions
 * - arrow: not overridable (internal implementation)
 * - content: the main tooltip content
 * - shortcut: keyboard shortcut display
 */
export const TooltipSlots = [
  { allowOverride: false, name: 'arrow' },
  'content',
  'shortcut',
] as const;

/**
 * Tooltip's own props
 */
export interface TooltipOwnProps extends OIDefaultProps {
  /** Tooltip content - can be a ReactNode or slot configuration */
  content: OIComponentSlotProps;
  /** Keyboard shortcut to display - can be a ReactNode or slot configuration */
  shortcut?: OIComponentSlotProps;
  /** Preferred side */
  side?: (typeof TooltipVariants.side)[number];
  /** Alignment on the side */
  align?: (typeof TooltipVariants.align)[number];
  /** Show arrow pointer */
  arrow?: boolean;
  /** Raw mode (no styling) */
  raw?: boolean;
  /** Delay before showing (ms) */
  delayDuration?: number;
  /** Offset from trigger */
  sideOffset?: number;
  /** Controlled open state */
  open?: boolean;
  /** Default open state */
  defaultOpen?: boolean;
  /** Called when open state changes */
  onOpenChange?: (open: boolean) => void;
  /** Tooltip trigger children */
  children?: React.ReactNode;
}

/**
 * Tooltip component props
 */
export type TooltipProps = TooltipOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof TooltipOwnProps | 'className'>;

/**
 * Tooltip component type
 */
export type TooltipComponent = React.ForwardRefExoticComponent<
  TooltipProps & React.RefAttributes<HTMLDivElement>
>;

/**
 * Default theme configuration for Tooltip
 */
export const tooltipDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'z-50 flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs bg-foreground text-background shadow-md origin-[var(--transform-origin)] transition-all duration-150 data-[starting-style]:opacity-0 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[ending-style]:scale-95',
    variants: {
      side: {
        top: '',
        right: '',
        bottom: '',
        left: '',
      },
      align: {
        start: '',
        center: '',
        end: '',
      },
    },
    modifiers: {
      arrow: {
        true: '',
        false: '',
      },
      raw: {
        true: 'bg-transparent text-inherit shadow-none px-0 py-0',
        false: '',
      },
    },
  },
  slots: {
    positioner: {
      base: 'z-50 outline-none',
      variants: {},
      modifiers: {},
    },
    content: {
      base: 'max-w-xs',
      variants: {},
      modifiers: {
        raw: {
          true: '',
          false: '',
        },
      },
    },
    shortcut: {
      base: 'ml-auto pl-2 text-[10px] opacity-60 tracking-widest',
      variants: {},
      modifiers: {},
    },
    arrow: {
      base: 'fill-foreground',
      variants: {
        side: {
          top: 'bottom-[-6px] rotate-180',
          right: 'left-[-10px] -rotate-90',
          bottom: 'top-[-6px]',
          left: 'right-[-10px] rotate-90',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    side: 'top',
    align: 'center',
  },
};
