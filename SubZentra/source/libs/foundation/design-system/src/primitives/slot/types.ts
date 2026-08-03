/**
 * Slot component type definitions
 * @module primitives/slot/types
 */

import type {
  OIComponentSlotProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

export type SlotDefaultElement = 'div';

export interface SlotOwnProps {
  baseOzid?: string;
  ozid?: string;
  slotName?: string;
  slot?: OIComponentSlotProps;
  children?: React.ReactNode;
}

export type SlotProps<T extends React.ElementType = SlotDefaultElement> =
  PolymorphicProps<T, SlotOwnProps>;

export type SlotRef<T extends React.ElementType = SlotDefaultElement> =
  PolymorphicRef<T>;

export interface SlotComponent {
  <T extends React.ElementType = SlotDefaultElement>(
    props: SlotProps<T> & { ref?: SlotRef<T> },
  ): React.ReactNode;
  displayName?: string;
}
