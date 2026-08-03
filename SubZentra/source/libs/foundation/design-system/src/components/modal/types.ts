/**
 * Modal component type definitions
 * @module components/modal/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIDefaultProps,
} from '../../types';

/**
 * Modal variant definitions
 */
export const ModalVariants = {
  size: ['480', '720', '960', '1080', 'full'] as const,
} as const;

/**
 * Modal modifier definitions
 */
export const ModalModifiers = ['fillContainer', 'fitContent'] as const;

/**
 * Modal slot definitions
 */
export const ModalSlots = [] as const;

/**
 * Modal's own props
 */
export interface ModalOwnProps
  extends OIComponentOwnProps<typeof ModalVariants, typeof ModalModifiers, typeof ModalSlots> {
  /** Size of the modal */
  size?: (typeof ModalVariants.size)[number];
  /** Fill the container height */
  fillContainer?: boolean;
  /** Fit content height instead of fixed */
  fitContent?: boolean;
  /** Whether the modal is open (controlled) */
  open?: boolean;
  /** Default open state (uncontrolled) */
  defaultOpen?: boolean;
  /** Callback when open state changes */
  onOpenChange?: (open: boolean) => void;
  /** Whether to close on outside click */
  closeOnOutsideClick?: boolean;
  /** Whether to close on escape key */
  closeOnEscape?: boolean;
  /** Modal content (typically Modal.Trigger and Modal.Content) */
  children?: React.ReactNode;
}

/**
 * Modal component props
 */
export type ModalProps = OIDefaultProps & ModalOwnProps;

// Sub-component props
export interface ModalTriggerProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
  asChild?: boolean;
}

// Modal's own root renders no DOM node — it is a context provider wrapping
// Dialog.Root — so Content is the component's real root element and carries the
// root-element contract: className, ozid, ref, and arbitrary HTML attributes.
export type ModalContentProps = OIDefaultProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, 'className'> & {
    children?: React.ReactNode;
  };

export interface ModalHeaderProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface ModalTitleProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface ModalDescriptionProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface ModalBodyProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface ModalFooterProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface ModalCloseProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
  asChild?: boolean;
}

/**
 * Modal context value
 */
export interface ModalContextValue {
  size: (typeof ModalVariants.size)[number];
  fillContainer?: boolean;
  fitContent?: boolean;
  titleId: string;
  descriptionId: string;
}

/**
 * Modal component type with sub-components
 */
export interface ModalComponent {
  (props: ModalProps): React.ReactNode;
  displayName?: string;
  Trigger: React.FC<ModalTriggerProps>;
  Content: React.ForwardRefExoticComponent<
    ModalContentProps & React.RefAttributes<HTMLDivElement>
  >;
  Header: React.FC<ModalHeaderProps>;
  Title: React.FC<ModalTitleProps>;
  Description: React.FC<ModalDescriptionProps>;
  Body: React.FC<ModalBodyProps>;
  Footer: React.FC<ModalFooterProps>;
  Close: React.FC<ModalCloseProps>;
}

/**
 * Default theme configuration for Modal
 */
export const modalDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: '',
    variants: {
      size: {
        '480': '',
        '720': '',
        '960': '',
        '1080': '',
        full: '',
      },
    },
    modifiers: {
      fillContainer: {
        true: '',
        false: '',
      },
      fitContent: {
        true: '',
        false: '',
      },
    },
  },
  slots: {
    backdrop: {
      base: 'fixed inset-0 z-50 bg-black/50 backdrop-blur-sm transition-opacity data-[starting-style]:opacity-0 data-[ending-style]:opacity-0',
      variants: {},
      modifiers: {},
    },
    // `flex flex-col overflow-hidden` is what makes the height cap mean
    // anything. The popup is capped at the viewport and `Modal.Body` is
    // `flex-1 overflow-auto`, but without a flex column the body is not a flex
    // item, and without `overflow-hidden` a child that outgrows the cap simply
    // paints past it — a long modal running off the screen with nothing to
    // scroll, and its rounded corners no longer clipping.
    popup: {
      base: 'fixed left-1/2 top-1/2 z-50 flex flex-col overflow-hidden -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-background shadow-lg transition-all data-[starting-style]:opacity-0 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[ending-style]:scale-95',
      variants: {
        size: {
          '480': 'w-[480px] max-w-[calc(100vw-2rem)]',
          '720': 'w-[720px] max-w-[calc(100vw-2rem)]',
          '960': 'w-[960px] max-w-[calc(100vw-2rem)]',
          '1080': 'w-[1080px] max-w-[calc(100vw-2rem)]',
          full: 'w-[calc(100vw-2rem)] h-[calc(100vh-2rem)]',
        },
      },
      modifiers: {
        fillContainer: {
          true: 'h-[calc(100vh-4rem)] max-h-[calc(100vh-4rem)]',
          false: 'max-h-[calc(100vh-4rem)]',
        },
        fitContent: {
          true: 'h-auto',
          false: '',
        },
      },
    },
    header: {
      // `shrink-0`: with the body flexing, a long modal would otherwise
      // compress the header and footer rather than scrolling the body.
      base: 'flex shrink-0 flex-col gap-1.5 border-b px-6 py-4',
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
      base: 'flex shrink-0 items-center justify-end gap-2 border-t px-6 py-4',
      variants: {},
      modifiers: {},
    },
    close: {
      base: 'absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    size: '720',
  },
};
