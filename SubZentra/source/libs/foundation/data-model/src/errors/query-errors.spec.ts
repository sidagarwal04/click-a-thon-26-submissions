/**
 * Query Errors Tests
 *
 * Tests for query-specific error classes.
 */

import { describe, expect, it } from 'vitest';

import { Milliseconds, QueryId } from '../types/branded';
import { ERROR_CATEGORY, FOUNDATION_ERROR_CODE } from './error-codes';
import { FoundationError } from './foundation-error';
import {
  CANCELLATION_REASON,
  QueryCancelledError,
  QueryExecutionError,
  QueryTimeoutError,
} from './query-errors';

// =============================================================================
// CANCELLATION_REASON
// =============================================================================

describe('CANCELLATION_REASON', () => {
  it('should define all cancellation reasons', () => {
    expect(CANCELLATION_REASON.USER).toBe('user');
    expect(CANCELLATION_REASON.SHUTDOWN).toBe('shutdown');
    expect(CANCELLATION_REASON.TIMEOUT).toBe('timeout');
  });

  it('should have exactly 3 entries', () => {
    expect(Object.keys(CANCELLATION_REASON)).toHaveLength(3);
  });
});

// =============================================================================
// QueryTimeoutError
// =============================================================================

describe('QueryTimeoutError', () => {
  const queryId = QueryId.from('q-timeout-1');
  const timeoutMs = Milliseconds.from(5000);

  it('should extend FoundationError', () => {
    const error = new QueryTimeoutError(queryId, timeoutMs);
    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(FoundationError);
  });

  it('should set correct error code', () => {
    const error = new QueryTimeoutError(queryId, timeoutMs);
    expect(error.code).toBe(FOUNDATION_ERROR_CODE.BRIDGE_QUERY_TIMEOUT);
  });

  it('should include queryId and timeoutMs in message', () => {
    const error = new QueryTimeoutError(queryId, timeoutMs);
    expect(error.message).toContain('q-timeout-1');
    expect(error.message).toContain('5000');
  });

  it('should store queryId and timeoutMs as properties', () => {
    const error = new QueryTimeoutError(queryId, timeoutMs);
    expect(error.queryId).toBe(queryId);
    expect(error.timeoutMs).toBe(timeoutMs);
  });

  it('should truncate SQL in context', () => {
    const longSql = 'SELECT ' + 'x'.repeat(200);
    const error = new QueryTimeoutError(queryId, timeoutMs, longSql);
    expect(error.context.sql).toBeDefined();
    expect((error.context.sql as string).length).toBeLessThanOrEqual(100);
  });

  it('should be categorized as transient', () => {
    const error = new QueryTimeoutError(queryId, timeoutMs);
    expect(error.category).toBe(ERROR_CATEGORY.TRANSIENT);
    expect(error.isRetryable).toBe(true);
  });
});

// =============================================================================
// QueryCancelledError
// =============================================================================

describe('QueryCancelledError', () => {
  const queryId = QueryId.from('q-cancel-1');

  it('should extend FoundationError', () => {
    const error = new QueryCancelledError(queryId);
    expect(error).toBeInstanceOf(FoundationError);
  });

  it('should set correct error code', () => {
    const error = new QueryCancelledError(queryId);
    expect(error.code).toBe(FOUNDATION_ERROR_CODE.BRIDGE_QUERY_CANCELLED);
  });

  it('should default reason to user', () => {
    const error = new QueryCancelledError(queryId);
    expect(error.reason).toBe(CANCELLATION_REASON.USER);
    expect(error.message).toContain('user');
  });

  it('should accept custom reason', () => {
    const error = new QueryCancelledError(queryId, CANCELLATION_REASON.SHUTDOWN);
    expect(error.reason).toBe(CANCELLATION_REASON.SHUTDOWN);
    expect(error.message).toContain('shutdown');
  });

  it('should be categorized as permanent', () => {
    const error = new QueryCancelledError(queryId);
    expect(error.category).toBe(ERROR_CATEGORY.PERMANENT);
    expect(error.isRetryable).toBe(false);
  });

  it('should not be reported (shouldReport = false)', () => {
    const error = new QueryCancelledError(queryId);
    expect(error.shouldReport).toBe(false);
  });
});

// =============================================================================
// QueryExecutionError
// =============================================================================

describe('QueryExecutionError', () => {
  const queryId = QueryId.from('q-exec-1');
  const sql = 'SELECT * FROM users WHERE id = 1';
  const cause = new Error('DuckDB: syntax error');

  it('should extend FoundationError', () => {
    const error = new QueryExecutionError(queryId, sql, cause);
    expect(error).toBeInstanceOf(FoundationError);
  });

  it('should set correct error code', () => {
    const error = new QueryExecutionError(queryId, sql, cause);
    expect(error.code).toBe(FOUNDATION_ERROR_CODE.QUERY_EXECUTION_FAILED);
  });

  it('should include cause message in error message', () => {
    const error = new QueryExecutionError(queryId, sql, cause);
    expect(error.message).toContain('DuckDB: syntax error');
  });

  it('should store cause', () => {
    const error = new QueryExecutionError(queryId, sql, cause);
    expect(error.cause).toBe(cause);
  });

  it('should truncate SQL in context to 200 chars', () => {
    const longSql = 'SELECT ' + 'x'.repeat(300);
    const error = new QueryExecutionError(queryId, longSql, cause);
    expect((error.context.sql as string).length).toBeLessThanOrEqual(200);
  });
});
