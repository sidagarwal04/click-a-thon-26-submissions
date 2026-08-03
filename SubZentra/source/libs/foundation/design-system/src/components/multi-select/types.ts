/**
 * MultiSelect component type definitions
 * @module components/multi-select/types
 *
 * MultiSelect uses CheckboxGroup internally for selection management.
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentSlotProps,
  OIDefaultProps,
} from '../../types';

/**
 * MultiSelect variant definitions
 */
export const MultiSelectVariants = {
  size: ['sm', 'md', 'lg'] as const,
  feedback: ['default', 'success', 'warning', 'error'] as const,
} as const;

/**
 * MultiSelect modifier definitions
 */
export const MultiSelectModifiers = ['disabled', 'readOnly', 'showCounter'] as const;

/**
 * MultiSelect slot definitions
 */
export const MultiSelectSlots = ['start', 'end', 'placeholder'] as const;

/**
 * MultiSelect option type
 */
export interface MultiSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

/**
 * MultiSelect's own props
 */
export interface MultiSelectOwnProps
  extends OIComponentOwnProps<
    typeof MultiSelectVariants,
    typeof MultiSelectModifiers,
    typeof MultiSelectSlots
  > {
  /** Size variant */
  size?: (typeof MultiSelectVariants.size)[number];
  /** Feedback/validation state */
  feedback?: (typeof MultiSelectVariants.feedback)[number];
  /** Disable the entire select */
  disabled?: boolean;
  /** Read-only mode */
  readOnly?: boolean;
  /** Show counter badge */
  showCounter?: boolean;
  /** Controlled selected values */
  value?: string[];
  /** Default selected values */
  defaultValue?: string[];
  /** Callback when selection changes */
  onValueChange?: (value: string[]) => void;
  /** Options to display */
  options: MultiSelectOption[];
  /** Placeholder text */
  placeholder?: string;
  /** Start slot (icon) */
  start?: OIComponentSlotProps;
  /** End slot */
  end?: OIComponentSlotProps;
  /** Search placeholder */
  searchPlaceholder?: string;
  /** Enable search */
  searchable?: boolean;
  /** Max height of dropdown */
  maxHeight?: number;
  /** Close dropdown on select */
  closeOnSelect?: boolean;
  /** Label for accessibility */
  label?: string;
}

/**
 * MultiSelect component props
 */
export type MultiSelectProps = OIDefaultProps &
  MultiSelectOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof MultiSelectOwnProps | 'className'>;

/**
 * MultiSelect component type
 */
export type MultiSelectComponent = React.ForwardRefExoticComponent<
  MultiSelectProps & React.RefAttributes<HTMLDivElement>
>;

/**
 * Default theme configuration for MultiSelect
 */
export const multiSelectDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'relative inline-block w-full',
    variants: {
      size: {
        sm: '',
        md: '',
        lg: '',
      },
      feedback: {
        default: '',
        success: '',
        warning: '',
        error: '',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50 pointer-events-none',
        false: '',
      },
      readOnly: {
        true: 'pointer-events-none',
        false: '',
      },
      showCounter: {
        true: '',
        false: '',
      },
    },
  },
  slots: {
    trigger: {
      base: 'flex w-full items-center justify-between rounded-md border bg-background px-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
      variants: {
        size: {
          sm: 'h-8 text-sm gap-1',
          md: 'h-10 text-sm gap-2',
          lg: 'h-12 text-base gap-2',
        },
        feedback: {
          default: 'border-input hover:border-input/80',
          success: 'border-green-500',
          warning: 'border-yellow-500',
          error: 'border-red-500',
        },
      },
      modifiers: {
        disabled: {
          true: 'cursor-not-allowed bg-muted',
          false: 'cursor-pointer',
        },
      },
    },
    triggerContent: {
      base: 'flex-1 truncate',
      variants: {},
      modifiers: {},
    },
    placeholder: {
      base: 'text-muted-foreground',
      variants: {},
      modifiers: {},
    },
    counter: {
      base: 'ml-1 shrink-0 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground',
      variants: {
        size: {
          sm: 'px-1.5 py-0 text-[10px]',
          md: 'px-2 py-0.5 text-xs',
          lg: 'px-2.5 py-1 text-xs',
        },
      },
      modifiers: {},
    },
    icon: {
      base: 'h-4 w-4 shrink-0 opacity-50 transition-transform',
      variants: {},
      modifiers: {},
    },
    content: {
      base: 'z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md',
      variants: {},
      modifiers: {},
    },
    search: {
      base: 'flex items-center border-b px-3',
      variants: {
        size: {
          sm: 'h-8',
          md: 'h-9',
          lg: 'h-10',
        },
      },
      modifiers: {},
    },
    searchInput: {
      base: 'flex-1 bg-transparent outline-none placeholder:text-muted-foreground',
      variants: {
        size: {
          sm: 'text-xs',
          md: 'text-sm',
          lg: 'text-sm',
        },
      },
      modifiers: {},
    },
    list: {
      base: 'p-1',
      variants: {},
      modifiers: {},
    },
    item: {
      base: 'relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      variants: {
        size: {
          sm: 'text-xs py-1',
          md: 'text-sm py-1.5',
          lg: 'text-base py-2',
        },
      },
      modifiers: {},
    },
    itemIndicator: {
      base: 'absolute left-2 flex h-3.5 w-3.5 items-center justify-center',
      variants: {},
      modifiers: {},
    },
    empty: {
      base: 'py-6 text-center text-sm text-muted-foreground',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    size: 'md',
    feedback: 'default',
  },
};
