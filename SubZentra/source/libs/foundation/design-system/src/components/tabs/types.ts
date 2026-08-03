/**
 * Tabs component type definitions
 * @module components/tabs/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentSlotProps,
  OIDefaultProps,
} from '../../types';

/**
 * Tabs variant definitions
 */
export const TabsVariants = {
  size: ['sm', 'md', 'lg'] as const,
  variant: ['default', 'pills', 'underline'] as const,
} as const;

/**
 * Tabs modifier definitions
 */
export const TabsModifiers = ['fullWidth'] as const;

/**
 * Tabs slot definitions
 * - start: icon or element before tab text
 * - end: badge or element after tab text
 */
export const TabsSlots = ['start', 'end'] as const;

/**
 * Tabs's own props
 */
export interface TabsOwnProps extends OIDefaultProps {
  /** Tabs size */
  size?: (typeof TabsVariants.size)[number];
  /** Tabs variant */
  variant?: (typeof TabsVariants.variant)[number];
  /** Full width tabs */
  fullWidth?: boolean;
  /** Controlled value */
  value?: string;
  /** Default value */
  defaultValue?: string;
  /** Called when value changes */
  onValueChange?: (value: string) => void;
  /** Tabs children */
  children?: React.ReactNode;
}

/**
 * Tabs component props
 */
export type TabsProps = TabsOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof TabsOwnProps | 'className'>;

/**
 * Tabs List props
 */
export interface TabsListProps extends OIDefaultProps {
  /** List children */
  children?: React.ReactNode;
}

/**
 * Tab Trigger props
 */
export interface TabTriggerProps extends OIDefaultProps {
  /** Tab value */
  value: string;
  /** Disable the tab */
  disabled?: boolean;
  /** Start slot (icon) */
  start?: OIComponentSlotProps;
  /** End slot (badge) */
  end?: OIComponentSlotProps;
  /** Tab children */
  children?: React.ReactNode;
}

/**
 * Tab Content props
 */
export interface TabContentProps extends OIDefaultProps {
  /** Tab value */
  value: string;
  /** Keep mounted when inactive */
  forceMount?: boolean;
  /** Content children */
  children?: React.ReactNode;
}

/**
 * Tabs component type with sub-components
 */
export interface TabsComponent
  extends React.ForwardRefExoticComponent<TabsProps & React.RefAttributes<HTMLDivElement>> {
  List: React.FC<TabsListProps>;
  Trigger: React.FC<TabTriggerProps>;
  Content: React.FC<TabContentProps>;
}

/**
 * Tabs context value
 */
export interface TabsContextValue {
  size: (typeof TabsVariants.size)[number];
  variant: (typeof TabsVariants.variant)[number];
  fullWidth?: boolean;
}

/**
 * Default theme configuration for Tabs
 */
export const tabsDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'flex flex-col',
    variants: {
      size: {
        sm: '',
        md: '',
        lg: '',
      },
      variant: {
        default: '',
        pills: '',
        underline: '',
      },
    },
    modifiers: {
      fullWidth: {
        true: 'w-full',
        false: '',
      },
    },
  },
  slots: {
    list: {
      base: 'inline-flex items-center',
      variants: {
        variant: {
          default: 'h-10 rounded-md bg-muted p-1 text-muted-foreground',
          pills: 'gap-1',
          underline: 'gap-4 border-b border-border',
        },
      },
      modifiers: {
        fullWidth: {
          true: 'w-full',
          false: '',
        },
      },
    },
    trigger: {
      base: 'inline-flex items-center justify-center whitespace-nowrap font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
      variants: {
        size: {
          sm: 'text-xs px-2 py-1 gap-1',
          md: 'text-sm px-3 py-1.5 gap-1.5',
          lg: 'text-base px-4 py-2 gap-2',
        },
        variant: {
          default:
            'rounded-sm data-[selected]:bg-background data-[selected]:text-foreground data-[selected]:shadow-sm',
          pills:
            'rounded-full bg-transparent hover:bg-muted data-[selected]:bg-primary data-[selected]:text-primary-foreground',
          underline:
            'border-b-2 border-transparent pb-3 -mb-px data-[selected]:border-primary data-[selected]:text-foreground rounded-none',
        },
      },
      modifiers: {
        fullWidth: {
          true: 'flex-1',
          false: '',
        },
      },
    },
    triggerStart: {
      base: 'shrink-0',
      variants: {
        size: {
          sm: 'h-3 w-3',
          md: 'h-4 w-4',
          lg: 'h-5 w-5',
        },
      },
      modifiers: {},
    },
    triggerEnd: {
      base: 'shrink-0',
      variants: {
        size: {
          sm: 'h-3 w-3',
          md: 'h-4 w-4',
          lg: 'h-5 w-5',
        },
      },
      modifiers: {},
    },
    content: {
      base: 'mt-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
      variants: {
        size: {
          sm: 'text-sm',
          md: 'text-base',
          lg: 'text-lg',
        },
      },
      modifiers: {},
    },
    indicator: {
      base: 'absolute bottom-0 h-0.5 bg-primary transition-all duration-200',
      variants: {
        variant: {
          default: 'hidden',
          pills: 'hidden',
          underline: '',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    size: 'md',
    variant: 'default',
  },
};
