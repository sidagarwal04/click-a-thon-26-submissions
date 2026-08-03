/**
 * Open Zentra ID (ozid) utilities
 * Provides consistent ID generation for testing, analytics, and debugging
 * @module utils/ozid
 */

/**
 * Separator used between base ozid and slot name
 */
export const OZID_SEPARATOR = '__';

/**
 * Generates a slot-specific ozid from a base ozid
 *
 * @example
 * slotOzid('checkout-submit', 'startIcon') // => 'checkout-submit__startIcon'
 * slotOzid('form-field', 'label') // => 'form-field__label'
 *
 * @param baseOzid - The base ozid of the parent component
 * @param slotName - The name of the slot
 * @returns Combined ozid for the slot, or undefined if baseOzid is not provided
 */
export function slotOzid(baseOzid: string | undefined, slotName: string): string | undefined {
  if (!baseOzid) return undefined;
  return `${baseOzid}${OZID_SEPARATOR}${slotName}`;
}

/**
 * Validates if a string is a valid ozid format
 * Valid ozids start with a letter and contain only alphanumeric characters and hyphens
 *
 * @example
 * isValidOzid('checkout-submit') // => true
 * isValidOzid('123-invalid') // => false
 * isValidOzid('valid_id') // => false (underscore not allowed except in slot separator)
 *
 * @param ozid - The ozid to validate
 * @returns true if the ozid is valid
 */
export function isValidOzid(ozid: string): boolean {
  // Must start with a letter, then alphanumeric and hyphens
  // Allow double underscore for slot ozids
  return /^[a-z][a-z0-9-]*(__[a-z][a-z0-9-]*)?$/i.test(ozid);
}

/**
 * Parses a slot ozid into its base and slot parts
 *
 * @example
 * parseSlotOzid('checkout-submit__startIcon')
 * // => { base: 'checkout-submit', slot: 'startIcon' }
 *
 * parseSlotOzid('checkout-submit')
 * // => { base: 'checkout-submit', slot: undefined }
 *
 * @param ozid - The ozid to parse
 * @returns Object with base and slot parts
 */
export function parseSlotOzid(ozid: string): { base: string; slot?: string } {
  const parts = ozid.split(OZID_SEPARATOR);
  return {
    base: parts[0],
    slot: parts[1],
  };
}

/**
 * Creates a ozid generator for a component, useful for consistent ID generation
 *
 * @example
 * const id = createOzidGenerator('modal');
 * id('trigger') // => 'modal__trigger'
 * id('content') // => 'modal__content'
 *
 * @param baseOzid - The base ozid for the component
 * @returns Function that generates slot ozids
 */
export function createOzidGenerator(baseOzid: string | undefined) {
  return (slotName: string): string | undefined => slotOzid(baseOzid, slotName);
}

/**
 * Type for props that include ozid
 */
export interface WithOzid {
  /** Open Zentra ID for testing and analytics */
  ozid?: string;
}

/**
 * Type for slot props that include baseOzid
 */
export interface WithBaseOzid {
  /** Base Open Zentra ID from parent component */
  baseOzid?: string;
}
