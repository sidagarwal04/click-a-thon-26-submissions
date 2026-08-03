/**
 * Core component type definitions for the OpenZentra Design System
 * @module types/component
 */

import type { ClassValue } from './cva';
import type { PolymorphicProps, PolymorphicRef } from './polymorphic';
import type { PropsOf, Resolve } from './utils';

const OI_COMPONENT_RESERVED_PROP = {
  COMPONENT: 'component',
  REF: 'ref',
} as const;

type OIComponentReservedProp =
  (typeof OI_COMPONENT_RESERVED_PROP)[keyof typeof OI_COMPONENT_RESERVED_PROP];

/**
 * Base props that every OpenZentra component inherits
 */
export interface OIDefaultProps {
  /** Custom className to merge with component styles */
  className?: string;
  /** Open Zentra ID - renders as data-ozid for testing/analytics */
  ozid?: string;
}

/**
 * ClassName configuration for slot overrides
 */
export type OIComponentClassName =
  | {
      className?: never;
      overrideClassName?: never;
    }
  | {
      className: string;
      /**
       * Use `overrideClassName` to override the default className of the slot.
       */
      overrideClassName?: never;
    }
  | {
      className?: never;
      /**
       * Use `overrideClassName` to override the default className of the slot.
       */
      overrideClassName: string;
    };

/**
 * Props that can be passed to a slot
 */
export type OIComponentSlotProps =
  | React.ReactNode
  | (OIComponentClassName &
      (
        | {
            component: React.ElementType;
            children?: React.ReactNode;
          }
        | {
            component?: React.ElementType;
            children?: React.ReactNode;
          }
        | {
            component?: React.ElementType;
            children: React.ReactNode;
          }
      ));

/**
 * Variant configuration type
 * Maps variant names to arrays of possible values
 */
export type OIComponentVariants = Record<string, readonly string[]>;

/**
 * Modifier configuration type (boolean props)
 */
export type OIComponentModifiers = readonly string[];

/**
 * Slot object configuration
 */
export type OIComponentSlotObject = { allowOverride: boolean; name: string };

/**
 * Slot can be a string or a slot object
 */
export type OIComponentSlot = string | OIComponentSlotObject;

/**
 * Array of slots
 */
export type OIComponentSlots = readonly OIComponentSlot[];

/** Transforms string slots into normalized slot object */
type NormalizeSlot<T> = T extends string ? { allowOverride: true; name: T } : T;

/** Transforms any string array elements to normalized slot object */
export type NormalizeSlots<T> = T extends readonly (infer U)[] ? NormalizeSlot<U>[] : never;

/** Extracts overridable slot names from normalized slots */
export type OverridableSlots<T> = T extends (infer U)[]
  ? U extends { allowOverride: true; name: string }
    ? U['name']
    : never
  : never;

/** Extracts slot names from normalized slots */
export type SlotNames<T> = T extends (infer U)[]
  ? U extends OIComponentSlotObject
    ? U['name']
    : U
  : never;

/**
 * Generates variant's and modifier's props for the component
 */
export type OIComponentOwnProps<
  Variants extends OIComponentVariants = OIComponentVariants,
  Modifiers extends OIComponentModifiers = [],
  Slots extends OIComponentSlots = [],
  AdditionalProps = object,
> = Resolve<
  {
    [V in keyof Variants]?: Variants[V][number];
  } & {
    [M in Modifiers[number]]?: boolean;
  } & {
    [S in OverridableSlots<NormalizeSlots<Slots>>]?: OIComponentSlotProps;
  } & AdditionalProps &
    OIDefaultProps
>;

/**
 * Generates theme configuration for specific component.
 * `Name` is used as a reference in `useTheme()` and as a prop name for `ThemeProvider`.
 */
export type OIComponentThemeConfig<
  Name extends string,
  Variants extends OIComponentVariants = OIComponentVariants,
  Modifiers extends OIComponentModifiers = [],
  Slots extends OIComponentSlots = [],
> = {
  name: Name;
  root: {
    [V in keyof Variants]: {
      [K in Variants[V][number]]: ClassValue;
    };
  } & {
    [M in Modifiers[number]]: {
      true: ClassValue;
      false: ClassValue;
    };
  };
  slots: {
    [S in NormalizeSlots<Slots>[number]['name']]: {
      [V in keyof Variants]: {
        [K in Variants[V][number]]: ClassValue;
      };
    } & {
      [M in Modifiers[number]]: {
        true: ClassValue;
        false: ClassValue;
      };
    };
  };
};

export type GetOIComponentThemeConfig<T> = T extends OIComponentThemeConfig<
  infer Name,
  infer Variants,
  infer Modifiers,
  infer Slots
>
  ? OIComponentThemeConfig<Name, Variants, Modifiers, Slots>
  : never;

export type GetSlots<T> = T extends OIComponentThemeConfig<
  infer _Name,
  infer _Variants,
  infer _Modifiers,
  infer Slots
>
  ? SlotNames<NormalizeSlots<Slots>>
  : never;

/** The ref type for OIComponent */
export type OIComponentRef<T extends React.ElementType> = React.ComponentPropsWithRef<T>['ref'];

/** Returns type-safe polymorphic OIComponentProps */
export type OIComponentProps<T extends React.ElementType = React.ElementType, TProps = object> = {
  component?: T;
} & TProps &
  Omit<PropsOf<T>, keyof TProps | OIComponentReservedProp> & { ref?: OIComponentRef<T> };

/**
 * Type for component that supports polymorphism via `component` prop
 */
export type OIPolymorphicComponent<TDefaultElement extends React.ElementType, TProps = object> = <
  T extends React.ElementType = TDefaultElement,
>(
  props: PolymorphicProps<T, TProps & OIDefaultProps>,
) => React.ReactNode;

/**
 * Type for component with forwardRef and polymorphism
 */
export type OIPolymorphicForwardRefComponent<
  TDefaultElement extends React.ElementType,
  TProps = object,
> = <T extends React.ElementType = TDefaultElement>(
  props: PolymorphicProps<T, TProps & OIDefaultProps> & { ref?: PolymorphicRef<T> },
) => React.ReactNode;

/**
 * Interaction event for analytics tracking
 */
export interface InteractionEvent {
  componentName: string;
  action: string;
  ozid?: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

/**
 * Component analytics configuration
 */
export interface ComponentAnalytics {
  onMount?: (componentName: string, ozid?: string) => void;
  onUnmount?: (componentName: string, ozid?: string) => void;
  onInteraction?: (event: InteractionEvent) => void;
  onError?: (error: Error, componentName: string, ozid?: string) => void;
}
