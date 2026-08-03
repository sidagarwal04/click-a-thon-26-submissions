/**
 * Helpers for resolving provisional IDs inside mutation payloads.
 * @module core/payload-id-resolution
 */

import { isProvisionalId } from '@open-zentra/foundation-data-model';

const isPlainObjectRecord = (value: unknown): value is Record<string, unknown> => {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return false;
  }

  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
};

/**
 * Resolve provisional IDs recursively in a JSON-like payload.
 */
const resolveValue = (
  value: unknown,
  resolveId: (provisionalId: string) => string | undefined,
): unknown => {
  if (typeof value === 'string' && isProvisionalId(value)) {
    return resolveId(value) ?? value;
  }

  if (Array.isArray(value)) {
    return value.map((item) => resolveValue(item, resolveId));
  }

  if (isPlainObjectRecord(value)) {
    const resolvedRecord: Record<string, unknown> = {};
    for (const [key, nestedValue] of Object.entries(value)) {
      resolvedRecord[key] = resolveValue(nestedValue, resolveId);
    }
    return resolvedRecord;
  }

  return value;
};

/**
 * Resolve provisional IDs recursively in an object payload.
 */
export const resolvePayloadProvisionalIds = <TPayload extends Record<string, unknown>>(
  payload: TPayload,
  resolveId: (provisionalId: string) => string | undefined,
): TPayload => {
  return resolveValue(payload, resolveId) as TPayload;
};
