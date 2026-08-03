/**
 * Accordion component type definitions
 * @module components/accordion/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentSlotProps,
  OIDefaultProps,
} from '../../types';

/**
 * Accordion variant definitions
 */
export const AccordionVariants = {
  variant: ['default', 'bordered', 'separated'] as const,
} as const;

/**
 * Accordion modifier definitions
 */
export const AccordionModifiers = ['disabled'] as const;

/**
 * Accordion slot definitions
 */
export const AccordionSlots = ['icon'] as const;

/**
 * Accordion's own props
 */
export interface AccordionOwnProps
  extends OIComponentOwnProps<
    typeof AccordionVariants,
    typeof AccordionModifiers,
    typeof AccordionSlots
  > {
  /** Visual variant */
  variant?: (typeof AccordionVariants.variant)[number];
  /** Whether to allow multiple items open simultaneously */
  multiple?: boolean;
  /** Controlled open items */
  value?: string[];
  /** Default open items */
  defaultValue?: string[];
  /** Callback when open items change */
  onValueChange?: (value: string[]) => void;
  /** Disable all accordion items */
  disabled?: boolean;
  /** Accordion items */
  children?: React.ReactNode;
}

/**
 * Accordion component props
 */
export type AccordionProps = OIDefaultProps &
  AccordionOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof AccordionOwnProps | 'className'>;

// Sub-component props
export interface AccordionItemProps extends OIDefaultProps {
  value: string;
  disabled?: boolean;
  children?: React.ReactNode;
  className?: string;
}

export interface AccordionTriggerProps extends OIDefaultProps {
  /** Custom icon slot */
  icon?: OIComponentSlotProps;
  children?: React.ReactNode;
  className?: string;
}

export interface AccordionContentProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

/**
 * Accordion context value
 */
export interface AccordionContextValue {
  variant: (typeof AccordionVariants.variant)[number];
  disabled?: boolean;
}

/**
 * Accordion component type with sub-components
 */
export interface AccordionComponent
  extends React.ForwardRefExoticComponent<
    AccordionProps & React.RefAttributes<HTMLDivElement>
  > {
  Item: React.FC<AccordionItemProps>;
  Trigger: React.FC<AccordionTriggerProps>;
  Content: React.FC<AccordionContentProps>;
}

/**
 * Default theme configuration for Accordion
 */
export const accordionDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'w-full',
    variants: {
      variant: {
        default: '',
        bordered: 'rounded-lg border',
        separated: 'space-y-2',
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
      base: 'border-b last:border-b-0',
      variants: {
        variant: {
          default: '',
          bordered: 'px-4',
          separated: 'border rounded-lg px-4',
        },
      },
      modifiers: {
        disabled: {
          true: 'opacity-50',
          false: '',
        },
      },
    },
    trigger: {
      base: 'flex flex-1 items-center justify-between py-4 font-medium transition-all hover:underline [&[data-panel-open]>svg]:rotate-180',
      variants: {},
      modifiers: {
        disabled: {
          true: 'pointer-events-none opacity-50',
          false: '',
        },
      },
    },
    icon: {
      base: 'h-4 w-4 shrink-0 transition-transform duration-200',
      variants: {},
      modifiers: {},
    },
    content: {
      base: 'overflow-hidden text-sm transition-all data-[ending-style]:h-0 data-[starting-style]:h-0',
      variants: {},
      modifiers: {},
    },
    contentInner: {
      base: 'pb-4 pt-0',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    variant: 'default',
  },
};
