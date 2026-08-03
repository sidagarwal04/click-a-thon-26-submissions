/**
 * useDLAnalyticsMutation - DuckDB mutation hook for write operations
 *
 * TanStack Mutation hook for DuckDB write operations (INSERT, UPDATE, DELETE, DDL).
 * Supports table locking for concurrent query safety.
 *
 * @module hooks/use-dl-analytics-mutation
 */

import { useCallback } from 'react';

import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query';

import {
  buildCreateViewSql,
  buildDropViewSql,
  escapeString,
  validateIdentifier,
  type DuckDBResult,
} from '@open-zentra/foundation-bridge';

import { useDataLayerInternals } from '../provider/data-layer-internals-context';
import { getAnalyticsRouterOrThrow } from '../utils/analytics-runtime';
import { createScopedErrorHandler } from '../utils/error-handler';
import { invalidateQueries } from '../utils/mutation-helpers';

// =============================================================================
// Error Handling
// =============================================================================

const handleAnalyticsMutationError = createScopedErrorHandler('useDLAnalyticsMutation');

// =============================================================================
// File Path Validation
// =============================================================================

/**
 * Valid file path pattern for OPFS/local files
 * Allows: alphanumeric, underscores, hyphens, dots, forward slashes
 * Prevents: path traversal (../), null bytes, and other dangerous characters
 */
const FILE_PATH_PATTERN = /^(?!.*\.\.)[a-zA-Z0-9_\-./]+$/;

/**
 * Maximum file path length
 */
const MAX_FILE_PATH_LENGTH = 1024;

/**
 * Validate a file path for use in SQL queries
 *
 * @param filePath - The file path to validate
 * @returns The validated file path
 * @throws Error if the file path is invalid
 */
const validateFilePath = (filePath: string): string => {
  if (!filePath || filePath.length === 0) {
    throw new Error('File path cannot be empty');
  }

  if (filePath.length > MAX_FILE_PATH_LENGTH) {
    throw new Error(`File path exceeds maximum length of ${MAX_FILE_PATH_LENGTH}`);
  }

  if (!FILE_PATH_PATTERN.test(filePath)) {
    throw new Error(
      'Invalid file path: must contain only alphanumeric characters, underscores, hyphens, dots, and forward slashes. Path traversal (..) is not allowed.',
    );
  }

  // Additional check for path traversal
  if (filePath.includes('..')) {
    throw new Error('Path traversal (..) is not allowed in file paths');
  }

  return filePath;
};

// =============================================================================
// Types
// =============================================================================

/**
 * Options for useDLAnalyticsMutation hook
 */
export interface UseDLAnalyticsMutationOptions<TVariables = unknown> {
  /** SQL query or function that generates SQL from variables */
  readonly sql: string | ((variables: TVariables) => string);
  /** Query keys to invalidate on success */
  readonly invalidateKeys?: QueryKey[];
  /** Called on mutation success */
  readonly onSuccess?: (result: DuckDBResult, variables: TVariables) => void | Promise<void>;
  /** Called on mutation error */
  readonly onError?: (error: Error, variables: TVariables) => void | Promise<void>;
}

/**
 * Result from useDLAnalyticsMutation hook
 */
export interface DLAnalyticsMutationResult<TVariables> {
  /** Whether DuckDB is available */
  readonly isAvailable: boolean;
  /** The mutation result data */
  readonly data: DuckDBResult | undefined;
  /** Whether mutation is pending */
  readonly isPending: boolean;
  /** Whether mutation is successful */
  readonly isSuccess: boolean;
  /** Whether mutation has error */
  readonly isError: boolean;
  /** Whether mutation is idle */
  readonly isIdle: boolean;
  /** Error if any */
  readonly error: Error | null;
  /** Mutate function */
  readonly mutate: (variables: TVariables) => void;
  /** Mutate async function */
  readonly mutateAsync: (variables: TVariables) => Promise<DuckDBResult>;
  /** Reset mutation state */
  readonly reset: () => void;
}

/**
 * Analytics mutation hook for DuckDB write operations
 *
 * @example
 * ```tsx
 * // Create a view
 * const createView = useDLAnalyticsMutation({
 *   sql: `CREATE OR REPLACE VIEW daily_stats AS
 *         SELECT DATE_TRUNC('day', timestamp) as date, COUNT(*) as count
 *         FROM events GROUP BY date`,
 *   invalidateKeys: [['analytics', 'views']],
 * });
 *
 * // Insert data with variables
 * const insertEvents = useDLAnalyticsMutation<void, { events: Event[] }>({
 *   sql: (vars) => {
 *     const values = vars.events.map(e =>
 *       `('${e.id}', '${e.type}', '${e.timestamp}')`
 *     ).join(',');
 *     return `INSERT INTO events (id, type, timestamp) VALUES ${values}`;
 *   },
 *   invalidateKeys: [['analytics', 'events']],
 * });
 *
 * // Usage
 * createView.mutate();
 * insertEvents.mutate({ events: [...] });
 * ```
 */
export const useDLAnalyticsMutation = <TVariables = void>(
  options: UseDLAnalyticsMutationOptions<TVariables>,
): DLAnalyticsMutationResult<TVariables> => {
  const queryClient = useQueryClient();
  const { duckdbRouter, analyticsEnabled, initializeAnalytics } = useDataLayerInternals();

  const isDuckDBAvailable = analyticsEnabled;

  const { sql, onSuccess, onError, invalidateKeys = [] } = options;

  // Mutation function
  const mutationFn = useCallback(
    async (variables: TVariables): Promise<DuckDBResult> => {
      const router = await getAnalyticsRouterOrThrow({
        duckdbRouter,
        initializeAnalytics,
      });

      // Get SQL (either string or function)
      const sqlToExecute = typeof sql === 'function' ? sql(variables) : sql;

      return router.query(sqlToExecute);
    },
    [duckdbRouter, initializeAnalytics, sql],
  );

  // TanStack mutation
  const mutationResult = useMutation<DuckDBResult, Error, TVariables>({
    mutationFn,

    onSuccess: async (data, variables) => {
      // Invalidate related queries
      if (invalidateKeys.length > 0) {
        await invalidateQueries(queryClient, invalidateKeys);
      }

      if (onSuccess) {
        try {
          await onSuccess(data, variables);
        } catch (callbackError) {
          handleAnalyticsMutationError(callbackError, {
            severity: 'error',
            data: { context: 'onSuccess callback' },
          });
        }
      }
    },

    onError: async (error, variables) => {
      handleAnalyticsMutationError(error, { severity: 'error' });
      if (onError) {
        try {
          await onError(error, variables);
        } catch (callbackError) {
          handleAnalyticsMutationError(callbackError, {
            severity: 'error',
            data: { context: 'onError callback' },
          });
        }
      }
    },
  });

  return {
    isAvailable: isDuckDBAvailable,
    data: mutationResult.data,
    isPending: mutationResult.isPending,
    isSuccess: mutationResult.isSuccess,
    isError: mutationResult.isError,
    isIdle: mutationResult.isIdle,
    error: mutationResult.error,
    mutate: mutationResult.mutate,
    mutateAsync: mutationResult.mutateAsync,
    reset: mutationResult.reset,
  };
};

/**
 * Hook for creating DuckDB views
 *
 * Uses SQL identifier validation to prevent SQL injection.
 *
 * @example
 * ```tsx
 * const { mutate } = useCreateAnalyticsView();
 * mutate({ name: 'daily_stats', sql: 'SELECT * FROM events', replace: true });
 * ```
 */
export const useCreateAnalyticsView = (): DLAnalyticsMutationResult<{
  name: string;
  sql: string;
  replace?: boolean;
}> => {
  return useDLAnalyticsMutation<{ name: string; sql: string; replace?: boolean }>({
    sql: (vars) => {
      // Validate view name to prevent SQL injection
      const validatedName = validateIdentifier(vars.name);
      return buildCreateViewSql(validatedName, vars.sql, vars.replace !== false);
    },
    invalidateKeys: [['analytics', 'views']],
  });
};

/**
 * Hook for dropping DuckDB views
 *
 * Uses SQL identifier validation to prevent SQL injection.
 *
 * @example
 * ```tsx
 * const { mutate } = useDropAnalyticsView();
 * mutate({ name: 'daily_stats', ifExists: true });
 * ```
 */
export const useDropAnalyticsView = (): DLAnalyticsMutationResult<{
  name: string;
  ifExists?: boolean;
}> => {
  return useDLAnalyticsMutation<{ name: string; ifExists?: boolean }>({
    sql: (vars) => {
      // Validate view name to prevent SQL injection
      const validatedName = validateIdentifier(vars.name);
      return buildDropViewSql(validatedName, vars.ifExists !== false);
    },
    invalidateKeys: [['analytics', 'views']],
  });
};

/**
 * Hook for executing raw DuckDB SQL
 *
 * WARNING: This hook executes raw SQL without validation.
 * Use with caution and ensure the SQL is properly sanitized before calling.
 *
 * @example
 * ```tsx
 * const { mutate } = useExecuteAnalyticsSql();
 * // IMPORTANT: Ensure SQL is validated before execution
 * mutate({ sql: 'SELECT COUNT(*) FROM events' });
 * ```
 */
export const useExecuteAnalyticsSql = (): DLAnalyticsMutationResult<{ sql: string }> => {
  return useDLAnalyticsMutation<{ sql: string }>({
    sql: (vars) => vars.sql,
  });
};

/**
 * Hook for loading Parquet files into DuckDB
 *
 * Validates table name and file path to prevent SQL injection.
 *
 * @example
 * ```tsx
 * const { mutate } = useLoadParquetFile();
 * mutate({ tableName: 'events', filePath: 'data/events.parquet', createOrReplace: true });
 * ```
 */
export const useLoadParquetFile = (): DLAnalyticsMutationResult<{
  tableName: string;
  filePath: string;
  createOrReplace?: boolean;
}> => {
  return useDLAnalyticsMutation<{ tableName: string; filePath: string; createOrReplace?: boolean }>(
    {
      sql: (vars) => {
        // Validate table name to prevent SQL injection
        const validatedTableName = validateIdentifier(vars.tableName);
        // Validate file path to prevent path traversal and injection
        const validatedFilePath = validateFilePath(vars.filePath);
        // Escape the file path for use in SQL string literal
        const escapedFilePath = escapeString(validatedFilePath);

        const createOrReplace =
          vars.createOrReplace !== false ? 'CREATE OR REPLACE TABLE' : 'CREATE TABLE';
        return `${createOrReplace} "${validatedTableName}" AS SELECT * FROM read_parquet('${escapedFilePath}')`;
      },
    },
  );
};

/**
 * Hook for copying data to Parquet format
 *
 * Validates file path to prevent path traversal and injection.
 *
 * WARNING: The query parameter is not validated. Ensure it comes from a trusted source.
 *
 * @example
 * ```tsx
 * const { mutate } = useCopyToParquet();
 * mutate({ query: 'SELECT * FROM events WHERE date > ?', filePath: 'exports/events.parquet' });
 * ```
 */
export const useCopyToParquet = (): DLAnalyticsMutationResult<{
  query: string;
  filePath: string;
}> => {
  return useDLAnalyticsMutation<{ query: string; filePath: string }>({
    sql: (vars) => {
      // Validate file path to prevent path traversal and injection
      const validatedFilePath = validateFilePath(vars.filePath);
      // Escape the file path for use in SQL string literal
      const escapedFilePath = escapeString(validatedFilePath);

      return `COPY (${vars.query}) TO '${escapedFilePath}' (FORMAT PARQUET)`;
    },
  });
};
