/**
 * Validation assertion helpers.
 * @module validation/assert-valid
 */

import type { z } from 'zod';

import { createValidationError } from '../errors/database-errors';

/**
 * Validate with a Zod schema and throw a typed database validation error.
 */
export const assertValid = <T>(schema: z.ZodSchema<T>, value: unknown, entityName: string): T => {
  const result = schema.safeParse(value);
  if (!result.success) {
    throw createValidationError(entityName, result.error.message);
  }
  return result.data;
};
