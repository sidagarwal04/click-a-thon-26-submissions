/**
 * Shared query execution error types for foundation libraries.
 *
 * These errors are defined at the data-model layer so every execution layer
 * (bridge, query-engine, data-layer) shares the same hierarchy.
 *
 * @module errors/query-errors
 */

import type { Milliseconds, QueryId } from '../types/branded';
import { FOUNDATION_ERROR_CODE } from './error-codes';
import { FoundationError } from './foundation-error';

/**
 * Reason for query cancellation.
 */
export const CANCELLATION_REASON = {
  USER: 'user',
  SHUTDOWN: 'shutdown',
  TIMEOUT: 'timeout',
} as const;

/**
 * Cancellation reason type.
 */
export type CancellationReasonKind = (typeof CANCELLATION_REASON)[keyof typeof CANCELLATION_REASON];

/**
 * Error thrown when a query exceeds its timeout.
 */
export class QueryTimeoutError extends FoundationError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_QUERY_TIMEOUT;

  constructor(readonly queryId: QueryId, readonly timeoutMs: Milliseconds, readonly sql?: string) {
    super(`Query ${queryId} timed out after ${timeoutMs}ms`, {
      queryId,
      timeoutMs,
      sql: sql?.slice(0, 100),
    });
  }
}

/**
 * Error thrown when a query is cancelled.
 */
export class QueryCancelledError extends FoundationError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_QUERY_CANCELLED;

  constructor(
    readonly queryId: QueryId,
    readonly reason: CancellationReasonKind = CANCELLATION_REASON.USER,
  ) {
    super(`Query ${queryId} was cancelled (${reason})`, {
      queryId,
      reason,
    });
  }
}

/**
 * Error thrown when query execution fails.
 */
export class QueryExecutionError extends FoundationError {
  readonly code = FOUNDATION_ERROR_CODE.QUERY_EXECUTION_FAILED;

  constructor(readonly queryId: QueryId, readonly sql: string, cause: Error) {
    super(
      `Query ${queryId} execution failed: ${cause.message}`,
      {
        queryId,
        sql: sql.slice(0, 200),
      },
      cause,
    );
  }
}
