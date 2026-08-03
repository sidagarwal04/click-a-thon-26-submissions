/**
 * Drawer component type definitions
 * @module components/drawer/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIDefaultProps,
} from '../../types';

/**
 * Drawer variant definitions
 */
export const DrawerVariants = {
  direction: ['left', 'right', 'top', 'bottom'] as const,
  size: ['auto', '1/3', '1/2', '2/3', 'full'] as const,
} as const;

/**
 * Drawer modifier definitions
 */
export const DrawerModifiers = [] as const;

/**
 * Drawer slot definitions
 */
export const DrawerSlots = [] as const;

/**
 * Drawer's own props
 */
export interface DrawerOwnProps
  extends OIComponentOwnProps<typeof DrawerVariants, typeof DrawerModifiers, typeof DrawerSlots> {
  /** Direction the drawer slides in from */
  direction?: (typeof DrawerVariants.direction)[number];
  /** Size of the drawer */
  size?: (typeof DrawerVariants.size)[number];
  /** Whether the drawer is open (controlled) */
  open?: boolean;
  /** Default open state (uncontrolled) */
  defaultOpen?: boolean;
  /** Callback when open state changes */
  onOpenChange?: (open: boolean) => void;
  /** Whether to close on outside click */
  closeOnOutsideClick?: boolean;
  /** Whether to close on escape key */
  closeOnEscape?: boolean;
  /** Drawer content (typically Drawer.Trigger and Drawer.Content) */
  children?: React.ReactNode;
}

/**
 * Drawer component props
 */
export type DrawerProps = OIDefaultProps & DrawerOwnProps;

// Sub-component props
export interface DrawerTriggerProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

// Drawer's own root renders no DOM node, so Content is the component's real
// root element and carries the root-element contract.
export interface DrawerContentProps
  extends OIDefaultProps,
    Omit<React.HTMLAttributes<HTMLDivElement>, 'className'> {
  children?: React.ReactNode;
  className?: string;
}

export interface DrawerHeaderProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface DrawerTitleProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface DrawerDescriptionProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface DrawerBodyProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface DrawerFooterProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface DrawerCloseProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

/**
 * Drawer context value
 */
export interface DrawerContextValue {
  direction: (typeof DrawerVariants.direction)[number];
  size: (typeof DrawerVariants.size)[number];
  titleId: string;
  descriptionId: string;
}

/**
 * Drawer component type with sub-components
 */
export interface DrawerComponent {
  (props: DrawerProps): React.ReactNode;
  displayName?: string;
  Trigger: React.FC<DrawerTriggerProps>;
  Content: React.ForwardRefExoticComponent<
    DrawerContentProps & React.RefAttributes<HTMLDivElement>
  >;
  Header: React.FC<DrawerHeaderProps>;
  Title: React.FC<DrawerTitleProps>;
  Description: React.FC<DrawerDescriptionProps>;
  Body: React.FC<DrawerBodyProps>;
  Footer: React.FC<DrawerFooterProps>;
  Close: React.FC<DrawerCloseProps>;
}

/**
 * Default theme configuration for Drawer
 */
export const drawerDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: '',
    variants: {
      direction: {
        left: '',
        right: '',
        top: '',
        bottom: '',
      },
      size: {
        auto: '',
        '1/3': '',
        '1/2': '',
        '2/3': '',
        full: '',
      },
    },
    modifiers: {},
  },
  slots: {
    backdrop: {
      base: 'fixed inset-0 z-50 bg-black/50 backdrop-blur-sm transition-opacity data-[starting-style]:opacity-0 data-[ending-style]:opacity-0',
      variants: {},
      modifiers: {},
    },
    popup: {
      base: 'fixed z-50 bg-background border shadow-lg transition-transform duration-300 ease-in-out flex flex-col',
      variants: {
        direction: {
          left: 'inset-y-0 left-0 border-r data-[starting-style]:-translate-x-full data-[ending-style]:-translate-x-full',
          right:
            'inset-y-0 right-0 border-l data-[starting-style]:translate-x-full data-[ending-style]:translate-x-full',
          top: 'inset-x-0 top-0 border-b data-[starting-style]:-translate-y-full data-[ending-style]:-translate-y-full',
          bottom:
            'inset-x-0 bottom-0 border-t data-[starting-style]:translate-y-full data-[ending-style]:translate-y-full',
        },
        size: {
          auto: '',
          '1/3': '',
          '1/2': '',
          '2/3': '',
          full: '',
        },
      },
      modifiers: {},
    },
    header: {
      base: 'flex flex-col gap-1.5 border-b px-6 py-4',
      variants: {},
      modifiers: {},
    },
    title: {
      base: 'text-lg font-semibold leading-none tracking-tight',
      variants: {},
      modifiers: {},
    },
    description: {
      base: 'text-sm text-muted-foreground',
      variants: {},
      modifiers: {},
    },
    body: {
      base: 'flex-1 overflow-auto px-6 py-4',
      variants: {},
      modifiers: {},
    },
    footer: {
      base: 'flex items-center justify-end gap-2 border-t px-6 py-4',
      variants: {},
      modifiers: {},
    },
    close: {
      base: 'absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    direction: 'right',
    size: '1/3',
  },
};
