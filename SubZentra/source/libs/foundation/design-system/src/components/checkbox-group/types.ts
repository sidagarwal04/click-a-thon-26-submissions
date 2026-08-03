/**
 * CheckboxGroup component type definitions
 * @module components/checkbox-group/types
 *
 * CheckboxGroup is a standalone primitive for managing multi-selection state.
 * It is designed to be reused by MultiSelect and Menu components.
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIDefaultProps,
} from '../../types';

/**
 * CheckboxGroup variant definitions
 */
export const CheckboxGroupVariants = {
  orientation: ['vertical', 'horizontal'] as const,
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * CheckboxGroup modifier definitions
 */
export const CheckboxGroupModifiers = ['disabled'] as const;

/**
 * CheckboxGroup slot definitions
 */
export const CheckboxGroupSlots = [] as const;

/**
 * CheckboxGroup's own props
 */
export interface CheckboxGroupOwnProps
  extends OIComponentOwnProps<
    typeof CheckboxGroupVariants,
    typeof CheckboxGroupModifiers,
    typeof CheckboxGroupSlots
  > {
  /** Layout orientation */
  orientation?: (typeof CheckboxGroupVariants.orientation)[number];
  /** Size passed down to items */
  size?: (typeof CheckboxGroupVariants.size)[number];
  /** Controlled value - array of selected item values */
  value?: string[];
  /** Default value for uncontrolled usage */
  defaultValue?: string[];
  /** Callback when selection changes */
  onValueChange?: (value: string[]) => void;
  /** Disable all checkboxes in the group */
  disabled?: boolean;
  /** Accessible label for the group */
  label?: string;
  /** Group content (CheckboxGroup.Item components) */
  children?: React.ReactNode;
}

/**
 * CheckboxGroup component props
 */
export type CheckboxGroupProps = OIDefaultProps &
  CheckboxGroupOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof CheckboxGroupOwnProps | 'className'>;

/**
 * CheckboxGroup.Item props
 */
export interface CheckboxGroupItemOwnProps extends OIDefaultProps {
  /** The value of this item (used for selection) */
  value: string;
  /** Disable this specific item */
  disabled?: boolean;
  /** Item label content */
  children?: React.ReactNode;
  /** Custom className */
  className?: string;
}

export type CheckboxGroupItemProps = CheckboxGroupItemOwnProps;

/**
 * CheckboxGroup.Label props
 */
export interface CheckboxGroupLabelProps extends OIDefaultProps {
  /** Whether this label represents a "select all" toggle */
  selectAll?: boolean;
  /** Label content */
  children?: React.ReactNode;
  /** Custom className */
  className?: string;
}

/**
 * CheckboxGroup context value - shared between Root and Items
 */
export interface CheckboxGroupContextValue {
  /** Current selected values */
  value: string[];
  /** Handler to update values */
  onValueChange: (value: string[]) => void;
  /** Group-level disabled state */
  disabled?: boolean;
  /** Size variant */
  size: (typeof CheckboxGroupVariants.size)[number];
  /** Orientation */
  orientation: (typeof CheckboxGroupVariants.orientation)[number];
  /** Register an item value (for select all functionality) */
  registerItem?: (value: string) => void;
  /** Unregister an item value */
  unregisterItem?: (value: string) => void;
  /** All registered item values */
  allItemValues?: string[];
}

/**
 * CheckboxGroup component type with sub-components
 */
export interface CheckboxGroupComponent
  extends React.ForwardRefExoticComponent<
    CheckboxGroupProps & React.RefAttributes<HTMLDivElement>
  > {
  Item: React.FC<CheckboxGroupItemProps>;
  Label: React.FC<CheckboxGroupLabelProps>;
}

/**
 * Default theme configuration for CheckboxGroup
 */
export const checkboxGroupDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'flex',
    variants: {
      orientation: {
        vertical: 'flex-col gap-2',
        horizontal: 'flex-row flex-wrap gap-4',
      },
      size: {
        sm: '',
        md: '',
        lg: '',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50 pointer-events-none',
        false: '',
      },
    },
  },
  slots: {
    item: {
      base: 'flex items-center gap-2',
      variants: {
        size: {
          sm: 'text-sm',
          md: 'text-base',
          lg: 'text-lg',
        },
      },
      modifiers: {
        disabled: {
          true: 'opacity-50 cursor-not-allowed',
          false: 'cursor-pointer',
        },
      },
    },
    label: {
      base: 'font-medium text-foreground',
      variants: {
        size: {
          sm: 'text-xs',
          md: 'text-sm',
          lg: 'text-base',
        },
      },
      modifiers: {},
    },
    groupLabel: {
      base: 'flex items-center gap-2 pb-2 border-b mb-2',
      variants: {
        size: {
          sm: 'text-xs',
          md: 'text-sm',
          lg: 'text-base',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    orientation: 'vertical',
    size: 'md',
  },
};
