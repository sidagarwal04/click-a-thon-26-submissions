/**
 * OpenZentra Design System - Test Utilities
 * @module test
 */

// Component test harness
export {
  describeComponent,
  testModifiers,
  testVariants,
  ensureVariantsStructure,
  type DescribeComponentOptions,
} from './describe-component';

// Slot test utilities
export { describeSlot, type DescribeSlotOptions } from './describe-slot';

// Focusable behavior tests
export { describeFocusable } from './describe-focusable';

// Test state management
export {
  setTestingComponentState,
  getTestingComponentState,
  resetTestingComponentState,
} from './test-state';

// Random value generators
export { randomString, randomNumber, randomElement, randomBoolean } from './random';

// Theme-aware render
export {
  renderWithTheme,
  createThemeRenderer,
  type RenderWithThemeOptions,
} from './render-with-theme';
