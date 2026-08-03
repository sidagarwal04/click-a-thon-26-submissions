/**
 * Shared CRUD operation contracts for foundation libraries.
 *
 * @module contracts/operations
 */

/**
 * Canonical CRUD operation values.
 */
export const OPERATIONS = {
  GET: 'get',
  LIST: 'list',
  CREATE: 'create',
  UPDATE: 'update',
  DELETE: 'delete',
} as const;

/**
 * Operation type derived from `OPERATIONS`.
 */
export type Operation = (typeof OPERATIONS)[keyof typeof OPERATIONS];

/**
 * Read operations.
 */
export const READ_OPERATIONS = {
  GET: OPERATIONS.GET,
  LIST: OPERATIONS.LIST,
} as const;

/**
 * Read operation type derived from `READ_OPERATIONS`.
 */
export type ReadOperation = (typeof READ_OPERATIONS)[keyof typeof READ_OPERATIONS];

/**
 * Write operations.
 */
export const WRITE_OPERATIONS = {
  CREATE: OPERATIONS.CREATE,
  UPDATE: OPERATIONS.UPDATE,
  DELETE: OPERATIONS.DELETE,
} as const;

/**
 * Write operation type derived from `WRITE_OPERATIONS`.
 */
export type WriteOperation = (typeof WRITE_OPERATIONS)[keyof typeof WRITE_OPERATIONS];

/**
 * Check if value is a valid CRUD operation.
 */
export const isOperation = (value: unknown): value is Operation =>
  typeof value === 'string' && Object.values(OPERATIONS).includes(value as Operation);

/**
 * Check if value is a read operation.
 */
export const isReadOperation = (value: unknown): value is ReadOperation =>
  typeof value === 'string' && Object.values(READ_OPERATIONS).includes(value as ReadOperation);

/**
 * Check if value is a write operation.
 */
export const isWriteOperation = (value: unknown): value is WriteOperation =>
  typeof value === 'string' && Object.values(WRITE_OPERATIONS).includes(value as WriteOperation);

/**
 * Alias used by mutation-centric layers.
 */
export const isMutationOperation = isWriteOperation;
