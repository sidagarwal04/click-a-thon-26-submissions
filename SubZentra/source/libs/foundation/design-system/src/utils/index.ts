/**
 * OpenZentra Design System - Utilities
 * @module utils
 */

// Class name utilities
export { cn, type ClassValue } from './cn';

// Open Zentra ID utilities
export {
  OZID_SEPARATOR,
  slotOzid,
  isValidOzid,
  parseSlotOzid,
  createOzidGenerator,
  type WithOzid,
  type WithBaseOzid,
} from './ozid';

// Slot utilities
export {
  normalizeSlot,
  normalizeSlots,
  getSlotNames,
  getOverridableSlotNames,
  isReactNode,
  isSlotConfig,
  getSlotChildren,
  getSlotComponent,
  getSlotClassName,
} from './slot-helpers';

// Accessibility utilities
export {
  generateA11yId,
  resetA11yIdCounter,
  visuallyHiddenStyles,
  visuallyHiddenClasses,
  shouldShowFocusRing,
  A11yKeys,
  type A11yKey,
  isKey,
  type FocusableElement,
  focusableSelector,
  getFocusableElements,
  trapFocus,
  announceToScreenReader,
  type DisableableProps,
  getDisabledState,
} from './a11y';

// Polymorphic utilities
export {
  getDisplayName,
  createPolymorphicComponent,
  type ExtractPolymorphicProps,
  type ExtractPolymorphicRef,
} from './polymorphic';
