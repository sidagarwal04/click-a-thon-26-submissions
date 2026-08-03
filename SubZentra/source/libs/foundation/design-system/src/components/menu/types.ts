/**
 * Menu component type definitions
 * @module components/menu/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentSlotProps,
  OIDefaultProps,
} from '../../types';

/**
 * Menu variant definitions
 */
export const MenuVariants = {
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Menu modifier definitions
 */
export const MenuModifiers = [] as const;

/**
 * Menu slot definitions
 * - start: icon or element before item text
 * - end: shortcut or element after item text
 */
export const MenuSlots = ['start', 'end'] as const;

/**
 * Menu's own props
 */
export interface MenuOwnProps extends OIDefaultProps {
  /** Menu size */
  size?: (typeof MenuVariants.size)[number];
  /** Controlled open state */
  open?: boolean;
  /** Default open state */
  defaultOpen?: boolean;
  /** Called when open state changes */
  onOpenChange?: (open: boolean) => void;
  /** Called when menu selection is cleared */
  onClear?: () => void;
  /** Menu children */
  children?: React.ReactNode;
}

/**
 * Menu component props
 */
export type MenuProps = MenuOwnProps;

/**
 * Menu Trigger props
 */
export interface MenuTriggerProps extends OIDefaultProps {
  /** Disable the trigger */
  disabled?: boolean;
  /** Trigger children */
  children?: React.ReactNode;
}

/**
 * Menu Content props
 */
// Menu's own root renders no DOM node, so Content is the component's real root
// element and carries the root-element contract.
export interface MenuContentProps
  extends OIDefaultProps,
    Omit<React.HTMLAttributes<HTMLDivElement>, 'className'> {
  /** Side offset */
  sideOffset?: number;
  /** Align offset */
  alignOffset?: number;
  /** Side */
  side?: 'top' | 'right' | 'bottom' | 'left';
  /** Align */
  align?: 'start' | 'center' | 'end';
  /** Content children */
  children?: React.ReactNode;
}

/**
 * Menu Item props
 */
export interface MenuItemProps extends OIDefaultProps {
  /** Item is disabled */
  disabled?: boolean;
  /** Called when item is selected */
  onSelect?: () => void;
  /** Close menu on select */
  closeOnSelect?: boolean;
  /** Start slot (icon) */
  start?: OIComponentSlotProps;
  /** End slot (shortcut) */
  end?: OIComponentSlotProps;
  /** Item children */
  children?: React.ReactNode;
}

/**
 * Menu Checkbox Item props
 */
export interface MenuCheckboxItemProps extends OIDefaultProps {
  /** Checked state */
  checked?: boolean;
  /** Called when checked changes */
  onCheckedChange?: (checked: boolean) => void;
  /** Item is disabled */
  disabled?: boolean;
  /** Close menu on select */
  closeOnSelect?: boolean;
  /** Item children */
  children?: React.ReactNode;
}

/**
 * Menu Radio Group props
 */
export interface MenuRadioGroupProps extends OIDefaultProps {
  /** Value */
  value?: string;
  /** Called when value changes */
  onValueChange?: (value: string) => void;
  /** Group children */
  children?: React.ReactNode;
}

/**
 * Menu Radio Item props
 */
export interface MenuRadioItemProps extends OIDefaultProps {
  /** Value */
  value: string;
  /** Item is disabled */
  disabled?: boolean;
  /** Close menu on select */
  closeOnSelect?: boolean;
  /** Item children */
  children?: React.ReactNode;
}

/**
 * Menu Group props
 */
export interface MenuGroupProps extends OIDefaultProps {
  /** Group children */
  children?: React.ReactNode;
}

/**
 * Menu Group Label props
 */
export interface MenuGroupLabelProps extends OIDefaultProps {
  /** Label children */
  children?: React.ReactNode;
}

/**
 * Menu Separator props
 */
export type MenuSeparatorProps = OIDefaultProps;

/**
 * Menu Sub props
 */
export interface MenuSubProps extends OIDefaultProps {
  /** Controlled open state */
  open?: boolean;
  /** Default open state */
  defaultOpen?: boolean;
  /** Called when open state changes */
  onOpenChange?: (open: boolean) => void;
  /** Sub menu children */
  children?: React.ReactNode;
}

/**
 * Menu Sub Trigger props
 */
export interface MenuSubTriggerProps extends OIDefaultProps {
  /** Disable the trigger */
  disabled?: boolean;
  /** Start slot (icon) */
  start?: OIComponentSlotProps;
  /** Trigger children */
  children?: React.ReactNode;
}

/**
 * Menu Sub Content props
 */
export interface MenuSubContentProps extends OIDefaultProps {
  /** Content children */
  children?: React.ReactNode;
}

/**
 * Menu component type with sub-components
 */
export interface MenuComponent {
  (props: MenuProps): React.ReactNode;
  displayName?: string;
  Trigger: React.FC<MenuTriggerProps>;
  Content: React.ForwardRefExoticComponent<
    MenuContentProps & React.RefAttributes<HTMLDivElement>
  >;
  Item: React.FC<MenuItemProps>;
  CheckboxItem: React.FC<MenuCheckboxItemProps>;
  RadioGroup: React.FC<MenuRadioGroupProps>;
  RadioItem: React.FC<MenuRadioItemProps>;
  Group: React.FC<MenuGroupProps>;
  GroupLabel: React.FC<MenuGroupLabelProps>;
  Separator: React.FC<MenuSeparatorProps>;
  Sub: React.FC<MenuSubProps>;
  SubTrigger: React.FC<MenuSubTriggerProps>;
  SubContent: React.FC<MenuSubContentProps>;
}

/**
 * Menu context value
 */
export interface MenuContextValue {
  size: (typeof MenuVariants.size)[number];
  onClear?: () => void;
}

/**
 * Default theme configuration for Menu
 */
export const menuDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: '',
    variants: {
      size: {
        sm: '',
        md: '',
        lg: '',
      },
    },
    modifiers: {},
  },
  slots: {
    positioner: {
      base: 'z-50 outline-none',
      variants: {},
      modifiers: {},
    },
    popup: {
      base: 'min-w-[8rem] overflow-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md origin-[var(--transform-origin)] transition-all duration-150 data-[starting-style]:opacity-0 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[ending-style]:scale-95',
      variants: {},
      modifiers: {},
    },
    item: {
      base: 'relative flex cursor-pointer select-none items-center rounded-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground',
      variants: {
        size: {
          sm: 'px-2 py-1 text-xs gap-1.5',
          md: 'px-2 py-1.5 text-sm gap-2',
          lg: 'px-3 py-2 text-base gap-2.5',
        },
      },
      modifiers: {},
    },
    itemStart: {
      base: 'shrink-0 text-muted-foreground',
      variants: {
        size: {
          sm: 'h-3 w-3',
          md: 'h-4 w-4',
          lg: 'h-5 w-5',
        },
      },
      modifiers: {},
    },
    itemEnd: {
      base: 'ml-auto text-xs text-muted-foreground',
      variants: {},
      modifiers: {},
    },
    checkboxItem: {
      base: 'relative flex cursor-pointer select-none items-center rounded-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground',
      variants: {
        size: {
          sm: 'py-1 pl-6 pr-2 text-xs',
          md: 'py-1.5 pl-8 pr-2 text-sm',
          lg: 'py-2 pl-10 pr-3 text-base',
        },
      },
      modifiers: {},
    },
    checkboxIndicator: {
      base: 'absolute flex items-center justify-center',
      variants: {
        size: {
          sm: 'left-1.5 h-3 w-3',
          md: 'left-2 h-3.5 w-3.5',
          lg: 'left-3 h-4 w-4',
        },
      },
      modifiers: {},
    },
    radioItem: {
      base: 'relative flex cursor-pointer select-none items-center rounded-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground',
      variants: {
        size: {
          sm: 'py-1 pl-6 pr-2 text-xs',
          md: 'py-1.5 pl-8 pr-2 text-sm',
          lg: 'py-2 pl-10 pr-3 text-base',
        },
      },
      modifiers: {},
    },
    radioIndicator: {
      base: 'absolute flex items-center justify-center',
      variants: {
        size: {
          sm: 'left-1.5 h-3 w-3',
          md: 'left-2 h-3.5 w-3.5',
          lg: 'left-3 h-4 w-4',
        },
      },
      modifiers: {},
    },
    group: {
      base: '',
      variants: {},
      modifiers: {},
    },
    groupLabel: {
      base: 'px-2 py-1.5 text-xs font-semibold text-muted-foreground',
      variants: {},
      modifiers: {},
    },
    separator: {
      base: '-mx-1 my-1 h-px bg-border',
      variants: {},
      modifiers: {},
    },
    subTrigger: {
      base: 'flex cursor-pointer select-none items-center rounded-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[open]:bg-accent',
      variants: {
        size: {
          sm: 'px-2 py-1 text-xs gap-1.5',
          md: 'px-2 py-1.5 text-sm gap-2',
          lg: 'px-3 py-2 text-base gap-2.5',
        },
      },
      modifiers: {},
    },
    subTriggerIcon: {
      base: 'ml-auto',
      variants: {
        size: {
          sm: 'h-3 w-3',
          md: 'h-4 w-4',
          lg: 'h-5 w-5',
        },
      },
      modifiers: {},
    },
    subContent: {
      base: 'min-w-[8rem] overflow-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-lg origin-[var(--transform-origin)] transition-all duration-150 data-[starting-style]:opacity-0 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[ending-style]:scale-95',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    size: 'md',
  },
};
