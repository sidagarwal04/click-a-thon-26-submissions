/**
 * Slot helper utilities
 * @module utils/slot-helpers
 */

import type { OIComponentSlot, OIComponentSlotObject } from '../types';

/**
 * Normalizes a slot definition to a consistent object format
 *
 * @example
 * normalizeSlot('startIcon')
 * // => { name: 'startIcon', allowOverride: true }
 *
 * normalizeSlot({ name: 'indicator', allowOverride: false })
 * // => { name: 'indicator', allowOverride: false }
 *
 * @param slot - Slot definition (string or object)
 * @returns Normalized slot object
 */
export function normalizeSlot(slot: OIComponentSlot): OIComponentSlotObject {
  if (typeof slot === 'string') {
    return { name: slot, allowOverride: true };
  }
  return slot;
}

/**
 * Normalizes an array of slot definitions
 *
 * @param slots - Array of slot definitions
 * @returns Array of normalized slot objects
 */
export function normalizeSlots(slots: readonly OIComponentSlot[]): OIComponentSlotObject[] {
  return slots.map(normalizeSlot);
}

/**
 * Gets slot names from an array of slot definitions
 *
 * @param slots - Array of slot definitions
 * @returns Array of slot names
 */
export function getSlotNames(slots: readonly OIComponentSlot[]): string[] {
  return slots.map((slot) => (typeof slot === 'string' ? slot : slot.name));
}

/**
 * Gets overridable slot names from an array of slot definitions
 *
 * @param slots - Array of slot definitions
 * @returns Array of overridable slot names
 */
export function getOverridableSlotNames(slots: readonly OIComponentSlot[]): string[] {
  return normalizeSlots(slots)
    .filter((slot) => slot.allowOverride)
    .map((slot) => slot.name);
}

/**
 * Checks if a value is a valid React node that can be rendered
 *
 * @param value - Value to check
 * @returns true if the value is a valid React node
 */
export function isReactNode(value: unknown): value is React.ReactNode {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return true;
  }
  if (Array.isArray(value)) return true;
  if (typeof value === 'object' && '$$typeof' in value) return true;
  return false;
}

/**
 * Checks if a slot prop contains slot configuration (object with component/children)
 *
 * @param slotProp - Slot prop value
 * @returns true if the slot prop is a configuration object
 */
export function isSlotConfig(
  slotProp: unknown,
): slotProp is { component?: React.ElementType; children?: React.ReactNode; className?: string } {
  if (slotProp === null || slotProp === undefined) return false;
  if (typeof slotProp !== 'object') return false;
  if (Array.isArray(slotProp)) return false;
  // Check if it's a React element (not a config object)
  if ('$$typeof' in slotProp) return false;
  // It's a config object if it has component, children, or className
  return 'component' in slotProp || 'children' in slotProp || 'className' in slotProp;
}

/**
 * Extracts children from a slot prop
 *
 * @param slotProp - Slot prop value
 * @returns Children to render, or undefined
 */
export function getSlotChildren(slotProp: unknown): React.ReactNode {
  if (isSlotConfig(slotProp)) {
    return slotProp.children;
  }
  if (isReactNode(slotProp)) {
    return slotProp;
  }
  return undefined;
}

/**
 * Extracts component from a slot prop
 *
 * @param slotProp - Slot prop value
 * @param defaultComponent - Default component to use
 * @returns Component to render
 */
export function getSlotComponent<T extends React.ElementType>(
  slotProp: unknown,
  defaultComponent: T,
): React.ElementType {
  if (isSlotConfig(slotProp) && slotProp.component) {
    return slotProp.component;
  }
  return defaultComponent;
}

/**
 * Extracts className from a slot prop
 *
 * @param slotProp - Slot prop value
 * @returns className string or undefined
 */
export function getSlotClassName(slotProp: unknown): string | undefined {
  if (isSlotConfig(slotProp)) {
    return slotProp.className;
  }
  return undefined;
}
