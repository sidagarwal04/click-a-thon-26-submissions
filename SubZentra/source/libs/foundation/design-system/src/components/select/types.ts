/**
 * Select component type definitions
 * @module components/select/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentRef,
  OIDefaultProps,
} from '../../types';

/**
 * Select variant definitions
 */
export const SelectVariants = {
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Select modifier definitions
 */
export const SelectModifiers = ['disabled'] as const;

/**
 * Select slot definitions
 */
export const SelectSlots = ['trigger', 'content', 'item'] as const;

/**
 * Select's own props
 */
export interface SelectOwnProps
  extends OIComponentOwnProps<typeof SelectVariants, typeof SelectModifiers, typeof SelectSlots> {
  /** Current value */
  value?: string;
  /** Default value (uncontrolled) */
  defaultValue?: string;
  /** Change handler */
  onValueChange?: (value: string) => void;
  /** Required attribute */
  required?: boolean;
  /** Name for form submission */
  name?: string;
  /** Open state (controlled) */
  open?: boolean;
  /** Default open state */
  defaultOpen?: boolean;
  /** Open state change handler */
  onOpenChange?: (open: boolean) => void;
  /** Children (Select subcomponents) */
  children: React.ReactNode;
}

/**
 * Select component props
 */
export type SelectProps = OIDefaultProps & SelectOwnProps;

/**
 * SelectTrigger's own props
 */
export interface SelectTriggerOwnProps {
  /** Placeholder text */
  placeholder?: string;
  /** Children content */
  children?: React.ReactNode;
}

/**
 * SelectTrigger component props
 */
export type SelectTriggerProps = OIDefaultProps &
  SelectTriggerOwnProps &
  Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, keyof SelectTriggerOwnProps | 'className'>;

/**
 * SelectTrigger component type
 */
export type SelectTriggerComponent = React.ForwardRefExoticComponent<
  SelectTriggerProps & { ref?: OIComponentRef<'button'> }
>;

/**
 * SelectContent's own props
 */
export interface SelectContentOwnProps {
  /** Position relative to trigger */
  position?: 'item-aligned' | 'popper';
  /** Side for popper position */
  side?: 'top' | 'right' | 'bottom' | 'left';
  /** Alignment for popper position */
  align?: 'start' | 'center' | 'end';
  /** Side offset */
  sideOffset?: number;
  /** Children content */
  children: React.ReactNode;
}

/**
 * SelectContent component props
 */
export type SelectContentProps = OIDefaultProps &
  SelectContentOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof SelectContentOwnProps | 'className'>;

/**
 * SelectContent component type
 */
export type SelectContentComponent = React.ForwardRefExoticComponent<
  SelectContentProps & { ref?: OIComponentRef<'div'> }
>;

/**
 * SelectItem's own props
 */
export interface SelectItemOwnProps {
  /** Value for this option */
  value: string;
  /** Disabled state */
  disabled?: boolean;
  /** Text content (for display and typeahead) */
  children: React.ReactNode;
}

/**
 * SelectItem component props
 */
export type SelectItemProps = OIDefaultProps &
  SelectItemOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof SelectItemOwnProps | 'className'>;

/**
 * SelectItem component type
 */
export type SelectItemComponent = React.ForwardRefExoticComponent<
  SelectItemProps & { ref?: OIComponentRef<'div'> }
>;

/**
 * Default theme configuration for Select
 */
export const selectDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: '',
    variants: {
      size: {
        sm: '',
        md: '',
        lg: '',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50 cursor-not-allowed',
        false: '',
      },
    },
  },
  slots: {
    trigger: {
      base: 'flex w-full items-center justify-between rounded-md border bg-background px-3 py-2 text-base transition-colors placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-border-focus disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1',
      variants: {
        size: {
          sm: 'h-8 text-sm px-2',
          md: 'h-10',
          lg: 'h-12 text-lg px-4',
        },
      },
      modifiers: {},
    },
    content: {
      base: 'relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-md border bg-background text-foreground shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
      variants: {
        size: {
          sm: '',
          md: '',
          lg: '',
        },
      },
      modifiers: {},
    },
    item: {
      base: 'relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-background-muted focus:text-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      variants: {
        size: {
          sm: 'py-1 pl-6 text-xs',
          md: 'py-1.5 pl-8 text-sm',
          lg: 'py-2 pl-10 text-base',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    size: 'md',
  },
};
