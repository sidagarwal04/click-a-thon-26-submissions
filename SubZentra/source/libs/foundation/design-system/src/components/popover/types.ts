/**
 * Popover component type definitions
 * @module components/popover/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIDefaultProps,
} from '../../types';

/**
 * Popover variant definitions
 */
export const PopoverVariants = {
  maxWidth: ['320', '480', '720', 'auto'] as const,
} as const;

/**
 * Popover modifier definitions
 */
export const PopoverModifiers = ['arrow'] as const;

/**
 * Popover slot definitions
 */
export const PopoverSlots = [] as const;

/**
 * Popover's own props
 */
export interface PopoverOwnProps
  extends OIComponentOwnProps<
    typeof PopoverVariants,
    typeof PopoverModifiers,
    typeof PopoverSlots
  > {
  /** Maximum width of the popover */
  maxWidth?: (typeof PopoverVariants.maxWidth)[number];
  /** Show arrow pointer */
  arrow?: boolean;
  /** Side to position the popover */
  side?: 'top' | 'right' | 'bottom' | 'left';
  /** Alignment along the side */
  align?: 'start' | 'center' | 'end';
  /** Offset from the trigger */
  sideOffset?: number;
  /** Whether the popover is open (controlled) */
  open?: boolean;
  /** Default open state (uncontrolled) */
  defaultOpen?: boolean;
  /** Callback when open state changes */
  onOpenChange?: (open: boolean) => void;
  /** Popover content (typically Popover.Trigger and Popover.Content) */
  children?: React.ReactNode;
}

/**
 * Popover component props
 */
export type PopoverProps = OIDefaultProps & PopoverOwnProps;

// Sub-component props
export interface PopoverTriggerProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

// Popover's own root renders no DOM node, so Content is the component's real
// root element and carries the root-element contract.
export interface PopoverContentProps
  extends OIDefaultProps,
    Omit<React.HTMLAttributes<HTMLDivElement>, 'className'> {
  children?: React.ReactNode;
  className?: string;
}

export interface PopoverCloseProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

/**
 * Popover context value
 */
export interface PopoverContextValue {
  maxWidth: (typeof PopoverVariants.maxWidth)[number];
  arrow: boolean;
  side: 'top' | 'right' | 'bottom' | 'left';
  align: 'start' | 'center' | 'end';
  sideOffset: number;
}

/**
 * Popover component type with sub-components
 */
export interface PopoverComponent {
  (props: PopoverProps): React.ReactNode;
  displayName?: string;
  Trigger: React.FC<PopoverTriggerProps>;
  Content: React.ForwardRefExoticComponent<
    PopoverContentProps & React.RefAttributes<HTMLDivElement>
  >;
  Close: React.FC<PopoverCloseProps>;
}

/**
 * Default theme configuration for Popover
 */
export const popoverDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: '',
    variants: {
      maxWidth: {
        '320': '',
        '480': '',
        '720': '',
        auto: '',
      },
    },
    modifiers: {
      arrow: {
        true: '',
        false: '',
      },
    },
  },
  slots: {
    popup: {
      base: 'z-50 rounded-lg border bg-popover p-4 text-popover-foreground shadow-md outline-none transition-all origin-[var(--transform-origin)] data-[starting-style]:opacity-0 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[ending-style]:scale-95',
      variants: {
        maxWidth: {
          '320': 'max-w-xs',
          '480': 'max-w-md',
          '720': 'max-w-2xl',
          auto: '',
        },
      },
      modifiers: {},
    },
    arrow: {
      base: 'fill-popover',
      variants: {},
      modifiers: {},
    },
    close: {
      base: 'absolute right-2 top-2 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    maxWidth: '320',
  },
};
