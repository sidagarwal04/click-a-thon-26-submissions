/**
 * Config Signature
 *
 * Stable signature generation for configs that may contain functions.
 * Functions are represented by stable in-process IDs to ensure changes in
 * function references trigger lifecycle refreshes.
 *
 * @module core/config-signature
 */

type GenericFunction = (...args: readonly unknown[]) => unknown;

const FUNCTION_IDS = new WeakMap<GenericFunction, number>();
let nextFunctionId = 1;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const isFunction = (value: unknown): value is GenericFunction => typeof value === 'function';

const getFunctionId = (value: GenericFunction): number => {
  const existingId = FUNCTION_IDS.get(value);
  if (existingId !== undefined) {
    return existingId;
  }

  const id = nextFunctionId++;
  FUNCTION_IDS.set(value, id);
  return id;
};

const normalizeValue = (value: unknown, seen: WeakSet<object>): unknown => {
  if (value === null || value === undefined) {
    return value;
  }

  if (isFunction(value)) {
    return `__fn:${getFunctionId(value)}`;
  }

  if (typeof value !== 'object') {
    return value;
  }

  if (Array.isArray(value)) {
    return value.map((item) => normalizeValue(item, seen));
  }

  if (!isRecord(value)) {
    return value;
  }

  const objectValue = value;
  if (seen.has(objectValue)) {
    return '__circular__';
  }

  seen.add(objectValue);
  const sortedKeys = Object.keys(objectValue).sort();
  const normalizedObject: Record<string, unknown> = {};
  for (const key of sortedKeys) {
    normalizedObject[key] = normalizeValue(objectValue[key], seen);
  }
  seen.delete(objectValue);

  return normalizedObject;
};

/**
 * Build a deterministic string signature for any config-like object.
 */
export const createConfigSignature = (value: unknown): string =>
  JSON.stringify(normalizeValue(value, new WeakSet<object>()));
