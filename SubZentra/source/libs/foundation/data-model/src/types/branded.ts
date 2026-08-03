/**
 * Branded types for type-safe primitives
 *
 * Provides nominal typing for primitive values to prevent accidental misuse.
 * Uses TypeScript's structural typing with a unique symbol brand.
 *
 * @module types/branded
 */

import { PROVISIONAL_ID_PREFIX } from '../schemas/base.schema';
import { Result } from './result';

// =============================================================================
// Validation Error
// =============================================================================

/**
 * Error thrown when a branded type validation fails
 */
export class BrandedTypeValidationError extends Error {
  readonly typeName: string;
  readonly invalidValue: unknown;

  constructor(typeName: string, invalidValue: unknown, message?: string) {
    super(message ?? `Invalid ${typeName}: ${String(invalidValue)}`);
    this.name = 'BrandedTypeValidationError';
    this.typeName = typeName;
    this.invalidValue = invalidValue;
  }
}

// =============================================================================
// Brand Utility Type
// =============================================================================

declare const __brand: unique symbol;

/**
 * Brand utility type - creates nominal types from structural types
 *
 * This allows creating type-safe wrappers around primitives that are
 * incompatible at compile time even though they have the same runtime value.
 *
 * @template T - The base type (e.g., string, number)
 * @template B - The brand identifier (a unique string literal)
 *
 * @example
 * ```typescript
 * type UserId = Brand<string, 'UserId'>;
 * type PostId = Brand<string, 'PostId'>;
 *
 * const userId = 'user_123' as UserId;
 * const postId = 'post_456' as PostId;
 *
 * function getUser(id: UserId) { ... }
 *
 * getUser(userId); // OK
 * getUser(postId); // Type error! Can't use PostId where UserId expected
 * ```
 */
export type Brand<T, B> = T & { readonly [__brand]: B };

// =============================================================================
// Branded String ID Factory
// =============================================================================

/**
 * Options for creating a branded string ID constructor via the factory.
 */
interface BrandedStringIdFactoryOptions<B extends Brand<string, string>> {
  /** The branded type name (used in error messages) */
  readonly typeName: string;
  /** Custom validator for the raw string (defaults to non-empty check) */
  readonly validate?: (value: string) => string | null;
  /** ID generation function (defaults to crypto.randomUUID()) */
  readonly generate?: () => string;
}

/**
 * Standard branded string ID constructor interface produced by the factory.
 */
interface BrandedStringIdConstructor<B extends Brand<string, string>> {
  /** Create from a trusted string */
  from: (s: string) => B;
  /** Parse an unknown value with validation */
  parse: (value: unknown) => Result<B, BrandedTypeValidationError>;
  /** Type guard */
  is: (value: unknown) => value is B;
  /** Extract the primitive string */
  unwrap: (id: B) => string;
  /** Generate a new unique ID (if generation is supported) */
  generate: () => B;
}

/**
 * Factory for creating branded string ID constructors.
 *
 * Eliminates ~40 lines of boilerplate per branded type by generating
 * standard from/parse/is/unwrap/generate methods.
 *
 * @param options - Configuration for the branded type
 * @returns A constructor object with standard branded type methods
 *
 * @example
 * ```typescript
 * type SessionId = Brand<string, 'SessionId'>;
 * const SessionId = createBrandedStringId<SessionId>({ typeName: 'SessionId' });
 *
 * const id = SessionId.generate();   // crypto.randomUUID() as SessionId
 * const parsed = SessionId.parse(x); // Result<SessionId, BrandedTypeValidationError>
 * ```
 */
const createBrandedStringId = <B extends Brand<string, string>>(
  options: BrandedStringIdFactoryOptions<B>,
): BrandedStringIdConstructor<B> => {
  const { typeName, validate, generate } = options;

  const defaultValidate = (value: string): string | null =>
    value.length === 0 ? `${typeName} cannot be empty` : null;

  const validatorFn = validate ?? defaultValidate;

  const generateFn = generate ?? (() => crypto.randomUUID());

  return {
    from: (s: string): B => s as B,

    parse: (value: unknown): Result<B, BrandedTypeValidationError> => {
      if (typeof value !== 'string') {
        return Result.err(
          new BrandedTypeValidationError(typeName, value, 'Value must be a string'),
        );
      }
      const error = validatorFn(value);
      if (error) {
        return Result.err(new BrandedTypeValidationError(typeName, value, error));
      }
      return Result.ok(value as B);
    },

    is: (value: unknown): value is B => {
      if (typeof value !== 'string') return false;
      return validatorFn(value) === null;
    },

    unwrap: (id: B): string => id as string,

    generate: (): B => generateFn() as B,
  };
};

// =============================================================================
// Time-related Branded Types
// =============================================================================

/**
 * Duration in milliseconds
 *
 * Use this type for durations, timeouts, and intervals.
 * Prevents accidentally mixing milliseconds with seconds or other units.
 *
 * @example
 * ```typescript
 * const timeout = Milliseconds.from(5000); // 5 seconds
 * const halfSecond = Milliseconds.from(500);
 *
 * function sleep(duration: Milliseconds): Promise<void> { ... }
 * ```
 */
export type Milliseconds = Brand<number, 'Milliseconds'>;

/**
 * Unix timestamp in milliseconds
 *
 * Use this type for points in time (timestamps).
 * Prevents accidentally mixing timestamps with durations.
 *
 * @example
 * ```typescript
 * const now = Timestamp.now();
 * const createdAt = Timestamp.from(Date.now());
 *
 * function formatDate(timestamp: Timestamp): string { ... }
 * ```
 */
export type Timestamp = Brand<number, 'Timestamp'>;

// =============================================================================
// Type Constructors
// =============================================================================

/**
 * Milliseconds constructor functions
 */
export const Milliseconds = {
  /**
   * Convert a number to Milliseconds
   *
   * @param n - Number of milliseconds
   * @returns Branded Milliseconds value
   *
   * @example
   * ```typescript
   * const timeout = Milliseconds.from(1000); // 1 second
   * ```
   */
  from: (n: number): Milliseconds => n as Milliseconds,

  /**
   * Parse an unknown value to Milliseconds with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing Milliseconds or validation error
   *
   * @example
   * ```typescript
   * const result = Milliseconds.parse(userInput);
   * if (result.ok) {
   *   console.log('Valid:', result.value);
   * }
   * ```
   */
  parse: (value: unknown): Result<Milliseconds, BrandedTypeValidationError> => {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return Result.err(
        new BrandedTypeValidationError('Milliseconds', value, 'Value must be a finite number'),
      );
    }
    if (value < 0) {
      return Result.err(
        new BrandedTypeValidationError('Milliseconds', value, 'Milliseconds cannot be negative'),
      );
    }
    return Result.ok(value as Milliseconds);
  },

  /**
   * Type guard to check if a value is Milliseconds
   *
   * @param value - Value to check
   * @returns True if value is a valid Milliseconds
   */
  is: (value: unknown): value is Milliseconds => {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0;
  },

  /**
   * Extract the primitive number from Milliseconds
   *
   * @param ms - Milliseconds value
   * @returns The underlying number
   */
  unwrap: (ms: Milliseconds): number => ms as number,

  /**
   * Create Milliseconds from seconds
   *
   * @param seconds - Number of seconds
   * @returns Branded Milliseconds value
   *
   * @example
   * ```typescript
   * const timeout = Milliseconds.fromSeconds(5); // 5000ms
   * ```
   */
  fromSeconds: (seconds: number): Milliseconds => (seconds * 1000) as Milliseconds,

  /**
   * Create Milliseconds from minutes
   *
   * @param minutes - Number of minutes
   * @returns Branded Milliseconds value
   *
   * @example
   * ```typescript
   * const timeout = Milliseconds.fromMinutes(5); // 300000ms
   * ```
   */
  fromMinutes: (minutes: number): Milliseconds => (minutes * 60 * 1000) as Milliseconds,

  /**
   * Convert Milliseconds to seconds
   *
   * @param ms - Milliseconds value
   * @returns Number of seconds
   */
  toSeconds: (ms: Milliseconds): number => ms / 1000,

  /**
   * Convert Milliseconds to minutes
   *
   * @param ms - Milliseconds value
   * @returns Number of minutes
   */
  toMinutes: (ms: Milliseconds): number => ms / 60000,
};

/**
 * Timestamp constructor functions
 */
export const Timestamp = {
  /**
   * Get current timestamp
   *
   * @returns Current time as branded Timestamp
   *
   * @example
   * ```typescript
   * const now = Timestamp.now();
   * ```
   */
  now: (): Timestamp => Date.now() as Timestamp,

  /**
   * Convert a number to Timestamp
   *
   * @param n - Unix timestamp in milliseconds
   * @returns Branded Timestamp value
   *
   * @example
   * ```typescript
   * const ts = Timestamp.from(1704067200000);
   * ```
   */
  from: (n: number): Timestamp => n as Timestamp,

  /**
   * Parse an unknown value to Timestamp with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing Timestamp or validation error
   */
  parse: (value: unknown): Result<Timestamp, BrandedTypeValidationError> => {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return Result.err(
        new BrandedTypeValidationError('Timestamp', value, 'Value must be a finite number'),
      );
    }
    if (value < 0) {
      return Result.err(
        new BrandedTypeValidationError('Timestamp', value, 'Timestamp cannot be negative'),
      );
    }
    return Result.ok(value as Timestamp);
  },

  /**
   * Type guard to check if a value is Timestamp
   *
   * @param value - Value to check
   * @returns True if value is a valid Timestamp
   */
  is: (value: unknown): value is Timestamp => {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0;
  },

  /**
   * Extract the primitive number from Timestamp
   *
   * @param ts - Timestamp value
   * @returns The underlying number
   */
  unwrap: (ts: Timestamp): number => ts as number,

  /**
   * Create Timestamp from Date object
   *
   * @param date - Date object
   * @returns Branded Timestamp value
   *
   * @example
   * ```typescript
   * const ts = Timestamp.fromDate(new Date('2024-01-01'));
   * ```
   */
  fromDate: (date: Date): Timestamp => date.getTime() as Timestamp,

  /**
   * Convert Timestamp to Date object
   *
   * @param ts - Timestamp value
   * @returns Date object
   *
   * @example
   * ```typescript
   * const date = Timestamp.toDate(ts);
   * ```
   */
  toDate: (ts: Timestamp): Date => new Date(ts),

  /**
   * Calculate difference between two timestamps
   *
   * @param a - First timestamp
   * @param b - Second timestamp
   * @returns Difference in milliseconds
   */
  diff: (a: Timestamp, b: Timestamp): Milliseconds => Math.abs(a - b) as Milliseconds,
};

// =============================================================================
// ID-related Branded Types
// =============================================================================

/**
 * Mutation ID - unique identifier for a mutation in the queue
 *
 * Prevents accidentally mixing mutation IDs with other ID types.
 *
 * @example
 * ```typescript
 * const mutationId = MutationId.from(crypto.randomUUID());
 * function processMutation(id: MutationId) { ... }
 * ```
 */
export type MutationId = Brand<string, 'MutationId'>;

/**
 * Entity ID - unique identifier for an entity
 *
 * Prevents accidentally mixing entity IDs with other ID types.
 *
 * @example
 * ```typescript
 * const entityId = EntityId.from('user_123');
 * function getEntity(id: EntityId) { ... }
 * ```
 */
export type EntityId = Brand<string, 'EntityId'>;

/**
 * Tab ID - unique identifier for a browser tab
 *
 * Used in cross-tab synchronization to identify tabs.
 *
 * @example
 * ```typescript
 * const tabId = TabId.generate();
 * function sendToTab(id: TabId, message: string) { ... }
 * ```
 */
export type TabId = Brand<string, 'TabId'>;

/**
 * Provisional ID - client-generated ID before server sync
 *
 * Used to identify entities created offline before they have a server ID.
 *
 * @example
 * ```typescript
 * const provisionalId = ProvisionalId.generate();
 * function isProvisional(id: string): id is ProvisionalId { ... }
 * ```
 */
export type ProvisionalId = Brand<string, 'ProvisionalId'>;

// =============================================================================
// ID Type Constructors
// =============================================================================

/**
 * MutationId constructor functions
 */
export const MutationId = {
  /**
   * Create MutationId from string (trusted input)
   */
  from: (s: string): MutationId => s as MutationId,

  /**
   * Parse an unknown value to MutationId with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing MutationId or validation error
   */
  parse: (value: unknown): Result<MutationId, BrandedTypeValidationError> => {
    if (typeof value !== 'string') {
      return Result.err(
        new BrandedTypeValidationError('MutationId', value, 'Value must be a string'),
      );
    }
    if (value.length === 0) {
      return Result.err(
        new BrandedTypeValidationError('MutationId', value, 'MutationId cannot be empty'),
      );
    }
    return Result.ok(value as MutationId);
  },

  /**
   * Type guard to check if a value is MutationId
   */
  is: (value: unknown): value is MutationId => {
    return typeof value === 'string' && value.length > 0;
  },

  /**
   * Extract the primitive string from MutationId
   */
  unwrap: (id: MutationId): string => id as string,

  /**
   * Generate a new MutationId
   */
  generate: (): MutationId => crypto.randomUUID() as MutationId,
};

/**
 * EntityId constructor functions
 */
export const EntityId = {
  /**
   * Create EntityId from string (trusted input)
   */
  from: (s: string): EntityId => s as EntityId,

  /**
   * Parse an unknown value to EntityId with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing EntityId or validation error
   */
  parse: (value: unknown): Result<EntityId, BrandedTypeValidationError> => {
    if (typeof value !== 'string') {
      return Result.err(
        new BrandedTypeValidationError('EntityId', value, 'Value must be a string'),
      );
    }
    if (value.length === 0) {
      return Result.err(
        new BrandedTypeValidationError('EntityId', value, 'EntityId cannot be empty'),
      );
    }
    return Result.ok(value as EntityId);
  },

  /**
   * Type guard to check if a value is EntityId
   */
  is: (value: unknown): value is EntityId => {
    return typeof value === 'string' && value.length > 0;
  },

  /**
   * Extract the primitive string from EntityId
   */
  unwrap: (id: EntityId): string => id as string,
};

/**
 * TabId constructor functions
 */
export const TabId = {
  /**
   * Create TabId from string (trusted input)
   */
  from: (s: string): TabId => s as TabId,

  /**
   * Parse an unknown value to TabId with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing TabId or validation error
   */
  parse: (value: unknown): Result<TabId, BrandedTypeValidationError> => {
    if (typeof value !== 'string') {
      return Result.err(new BrandedTypeValidationError('TabId', value, 'Value must be a string'));
    }
    if (value.length === 0) {
      return Result.err(new BrandedTypeValidationError('TabId', value, 'TabId cannot be empty'));
    }
    return Result.ok(value as TabId);
  },

  /**
   * Type guard to check if a value is TabId
   */
  is: (value: unknown): value is TabId => {
    return typeof value === 'string' && value.length > 0;
  },

  /**
   * Extract the primitive string from TabId
   */
  unwrap: (id: TabId): string => id as string,

  /**
   * Generate a new TabId
   */
  generate: (): TabId => crypto.randomUUID() as TabId,
};

/**
 * ProvisionalId constructor functions
 */
export const ProvisionalId = {
  /**
   * Create ProvisionalId from string (trusted input)
   */
  from: (s: string): ProvisionalId => s as ProvisionalId,

  /**
   * Parse an unknown value to ProvisionalId with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing ProvisionalId or validation error
   */
  parse: (value: unknown): Result<ProvisionalId, BrandedTypeValidationError> => {
    if (typeof value !== 'string') {
      return Result.err(
        new BrandedTypeValidationError('ProvisionalId', value, 'Value must be a string'),
      );
    }
    if (!value.startsWith(PROVISIONAL_ID_PREFIX)) {
      return Result.err(
        new BrandedTypeValidationError(
          'ProvisionalId',
          value,
          `ProvisionalId must start with "${PROVISIONAL_ID_PREFIX}"`,
        ),
      );
    }
    return Result.ok(value as ProvisionalId);
  },

  /**
   * Type guard to check if a value is ProvisionalId
   */
  is: (value: unknown): value is ProvisionalId => {
    return typeof value === 'string' && value.startsWith(PROVISIONAL_ID_PREFIX);
  },

  /**
   * Extract the primitive string from ProvisionalId
   */
  unwrap: (id: ProvisionalId): string => id as string,

  /**
   * Generate a new ProvisionalId
   */
  generate: (): ProvisionalId => `${PROVISIONAL_ID_PREFIX}${crypto.randomUUID()}` as ProvisionalId,

  /**
   * Get the prefix used for provisional IDs
   */
  prefix: PROVISIONAL_ID_PREFIX,
};

// =============================================================================
// Bridge-related Branded Types (centralized from foundation-bridge)
// =============================================================================

/**
 * Query ID - unique identifier for a database query
 *
 * Used to track and cancel queries in the DuckDB bridge layer.
 *
 * @example
 * ```typescript
 * const queryId = QueryId.create();
 * function cancelQuery(id: QueryId) { ... }
 * ```
 */
export type QueryId = Brand<string, 'QueryId'>;

/**
 * Worker ID - unique identifier for a worker instance
 *
 * Used to identify workers in the DuckDB worker pool.
 *
 * @example
 * ```typescript
 * const workerId = WorkerId.create(0);
 * function getWorker(id: WorkerId) { ... }
 * ```
 */
export type WorkerId = Brand<string, 'WorkerId'>;

/**
 * SQL Table Name - validated table name for SQL operations
 *
 * Used to ensure table names are validated before use in SQL queries.
 * Named SqlTableName to distinguish from the query-keys TableName (entity union type).
 *
 * @example
 * ```typescript
 * const tableName = SqlTableName.from('users');
 * function queryTable(name: SqlTableName) { ... }
 * ```
 */
export type SqlTableName = Brand<string, 'SqlTableName'>;

/**
 * SQL Identifier - sanitized SQL identifier
 *
 * Used for column names, aliases, and other SQL identifiers that have been
 * validated and sanitized to prevent SQL injection.
 *
 * @example
 * ```typescript
 * const column = SqlIdentifier.from('user_name');
 * function selectColumn(col: SqlIdentifier) { ... }
 * ```
 */
export type SqlIdentifier = Brand<string, 'SqlIdentifier'>;

// =============================================================================
// Bridge Type Constructors
// =============================================================================

/**
 * QueryId constructor functions
 *
 * Built using the branded ID factory with standardized crypto.randomUUID() generation.
 * Includes a legacy `create()` alias for backward compatibility.
 */
export const QueryId = {
  ...createBrandedStringId<QueryId>({
    typeName: 'QueryId',
    generate: () => `q_${crypto.randomUUID()}`,
  }),

  /**
   * Create a new unique QueryId (legacy alias for generate())
   *
   * @param prefix - Optional prefix for the ID (default: 'q')
   * @returns A new unique QueryId
   *
   * @example
   * ```typescript
   * const id = QueryId.create();       // 'q_<uuid>'
   * const id2 = QueryId.generate();    // 'q_<uuid>'
   * ```
   */
  create: (prefix = 'q'): QueryId => `${prefix}_${crypto.randomUUID()}` as QueryId,
};

/**
 * WorkerId constructor functions
 */
export const WorkerId = {
  /**
   * Create a new WorkerId with index
   *
   * @param index - Worker index number
   * @returns Branded WorkerId
   *
   * @example
   * ```typescript
   * const id = WorkerId.create(0); // 'worker_0'
   * ```
   */
  create: (index: number): WorkerId => `worker_${index}` as WorkerId,

  /**
   * Convert a string to WorkerId (trusted input)
   *
   * @param s - String to convert
   * @returns Branded WorkerId
   */
  from: (s: string): WorkerId => s as WorkerId,

  /**
   * Parse an unknown value to WorkerId with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing WorkerId or validation error
   */
  parse: (value: unknown): Result<WorkerId, BrandedTypeValidationError> => {
    if (typeof value !== 'string') {
      return Result.err(
        new BrandedTypeValidationError('WorkerId', value, 'Value must be a string'),
      );
    }
    if (!value.startsWith('worker_')) {
      return Result.err(
        new BrandedTypeValidationError('WorkerId', value, 'WorkerId must start with "worker_"'),
      );
    }
    return Result.ok(value as WorkerId);
  },

  /**
   * Type guard to check if a value is WorkerId
   */
  is: (value: unknown): value is WorkerId => {
    return typeof value === 'string' && value.startsWith('worker_');
  },

  /**
   * Extract the primitive string from WorkerId
   */
  unwrap: (id: WorkerId): string => id as string,

  /**
   * Extract the index number from WorkerId
   */
  getIndex: (id: WorkerId): number => {
    const match = (id as string).match(/^worker_(\d+)$/);
    return match ? parseInt(match[1], 10) : -1;
  },
};

// Regular expression for valid SQL identifiers (alphanumeric and underscore, not starting with number)
const SQL_IDENTIFIER_PATTERN = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

/**
 * SqlTableName constructor functions
 */
export const SqlTableName = {
  /**
   * Convert a string to SqlTableName (trusted input)
   *
   * @param s - String to convert (should be pre-validated)
   * @returns Branded SqlTableName
   *
   * @example
   * ```typescript
   * const name = SqlTableName.from('users');
   * ```
   */
  from: (s: string): SqlTableName => s as SqlTableName,

  /**
   * Parse an unknown value to SqlTableName with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing SqlTableName or validation error
   */
  parse: (value: unknown): Result<SqlTableName, BrandedTypeValidationError> => {
    if (typeof value !== 'string') {
      return Result.err(
        new BrandedTypeValidationError('SqlTableName', value, 'Value must be a string'),
      );
    }
    if (value.length === 0) {
      return Result.err(
        new BrandedTypeValidationError('SqlTableName', value, 'SqlTableName cannot be empty'),
      );
    }
    if (!SQL_IDENTIFIER_PATTERN.test(value)) {
      return Result.err(
        new BrandedTypeValidationError(
          'SqlTableName',
          value,
          'SqlTableName must be a valid SQL identifier (alphanumeric and underscore, not starting with number)',
        ),
      );
    }
    return Result.ok(value as SqlTableName);
  },

  /**
   * Type guard to check if a value is SqlTableName
   */
  is: (value: unknown): value is SqlTableName => {
    return typeof value === 'string' && value.length > 0 && SQL_IDENTIFIER_PATTERN.test(value);
  },

  /**
   * Extract the primitive string from SqlTableName
   */
  unwrap: (name: SqlTableName): string => name as string,
};

/**
 * SqlIdentifier constructor functions
 */
export const SqlIdentifier = {
  /**
   * Convert a string to SqlIdentifier (trusted input)
   *
   * @param s - String to convert (should be pre-validated)
   * @returns Branded SqlIdentifier
   *
   * @example
   * ```typescript
   * const col = SqlIdentifier.from('user_name');
   * ```
   */
  from: (s: string): SqlIdentifier => s as SqlIdentifier,

  /**
   * Parse an unknown value to SqlIdentifier with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing SqlIdentifier or validation error
   */
  parse: (value: unknown): Result<SqlIdentifier, BrandedTypeValidationError> => {
    if (typeof value !== 'string') {
      return Result.err(
        new BrandedTypeValidationError('SqlIdentifier', value, 'Value must be a string'),
      );
    }
    if (value.length === 0) {
      return Result.err(
        new BrandedTypeValidationError('SqlIdentifier', value, 'SqlIdentifier cannot be empty'),
      );
    }
    if (!SQL_IDENTIFIER_PATTERN.test(value)) {
      return Result.err(
        new BrandedTypeValidationError(
          'SqlIdentifier',
          value,
          'SqlIdentifier must be a valid SQL identifier (alphanumeric and underscore, not starting with number)',
        ),
      );
    }
    return Result.ok(value as SqlIdentifier);
  },

  /**
   * Type guard to check if a value is SqlIdentifier
   */
  is: (value: unknown): value is SqlIdentifier => {
    return typeof value === 'string' && value.length > 0 && SQL_IDENTIFIER_PATTERN.test(value);
  },

  /**
   * Extract the primitive string from SqlIdentifier
   */
  unwrap: (id: SqlIdentifier): string => id as string,
};

// =============================================================================
// Query Engine Branded Types (centralized from foundation-query-engine)
// =============================================================================

/**
 * Member reference in format "table.member" - references a measure or dimension
 *
 * Used in the query engine's semantic layer to reference measures and dimensions
 * in a type-safe manner.
 *
 * @example
 * ```typescript
 * const ref = MemberRef.create('orders', 'total_amount');
 * // Result: 'orders.total_amount' as MemberRef
 *
 * const parsed = MemberRef.parse(ref);
 * // Result: { table: 'orders', member: 'total_amount' }
 * ```
 */
export type MemberRef = Brand<string, 'MemberRef'>;

/**
 * Execution identifier for tracking query execution
 *
 * Used to uniquely identify query executions for logging, cancellation,
 * and performance tracking.
 *
 * @example
 * ```typescript
 * const execId = ExecutionId.create();
 * function trackExecution(id: ExecutionId) { ... }
 * ```
 */
export type ExecutionId = Brand<string, 'ExecutionId'>;

// =============================================================================
// Query Engine Type Constructors
// =============================================================================

/**
 * MemberRef constructor functions
 */
export const MemberRef = {
  /**
   * Create a MemberRef from table and member names
   *
   * @param table - Table name
   * @param member - Member name (measure or dimension)
   * @returns Branded MemberRef in format "table.member"
   *
   * @example
   * ```typescript
   * const ref = MemberRef.create('orders', 'total_amount');
   * // Result: 'orders.total_amount'
   * ```
   */
  create: (table: string, member: string): MemberRef => `${table}.${member}` as MemberRef,

  /**
   * Convert a string to MemberRef (trusted input)
   *
   * @param s - String in format "table.member"
   * @returns Branded MemberRef
   */
  from: (s: string): MemberRef => s as MemberRef,

  /**
   * Parse a MemberRef into its components
   *
   * @param ref - MemberRef to parse
   * @returns Object with table and member properties
   *
   * @example
   * ```typescript
   * const { table, member } = MemberRef.parse('orders.total_amount' as MemberRef);
   * // Result: { table: 'orders', member: 'total_amount' }
   * ```
   */
  parse: (ref: MemberRef): { table: string; member: string } => {
    const idx = (ref as string).indexOf('.');
    if (idx === -1) {
      return { table: '', member: ref as string };
    }
    return { table: (ref as string).slice(0, idx), member: (ref as string).slice(idx + 1) };
  },

  /**
   * Parse an unknown value to MemberRef with validation
   *
   * @param value - Unknown value to parse
   * @returns Result containing MemberRef or validation error
   */
  tryParse: (value: unknown): Result<MemberRef, BrandedTypeValidationError> => {
    if (typeof value !== 'string') {
      return Result.err(
        new BrandedTypeValidationError('MemberRef', value, 'Value must be a string'),
      );
    }
    if (!MemberRef.isValid(value)) {
      return Result.err(
        new BrandedTypeValidationError(
          'MemberRef',
          value,
          'MemberRef must be in format "table.member"',
        ),
      );
    }
    return Result.ok(value as MemberRef);
  },

  /**
   * Check if a string is a valid MemberRef format
   *
   * @param s - String to check
   * @returns True if the string is in valid "table.member" format
   */
  isValid: (s: string): boolean => {
    const idx = s.indexOf('.');
    return idx > 0 && idx < s.length - 1;
  },

  /**
   * Type guard to check if a value is MemberRef
   *
   * @param value - Value to check
   * @returns True if value is a valid MemberRef
   */
  is: (value: unknown): value is MemberRef => {
    return typeof value === 'string' && MemberRef.isValid(value);
  },

  /**
   * Extract the primitive string from MemberRef
   *
   * @param ref - MemberRef value
   * @returns The underlying string
   */
  unwrap: (ref: MemberRef): string => ref as string,
};

/**
 * ExecutionId constructor functions
 *
 * Built using the branded ID factory with standardized crypto.randomUUID() generation.
 * Includes a legacy `create()` alias for backward compatibility.
 */
export const ExecutionId = {
  ...createBrandedStringId<ExecutionId>({
    typeName: 'ExecutionId',
    generate: () => `exec_${crypto.randomUUID()}`,
  }),

  /**
   * Create a new unique ExecutionId (legacy alias for generate())
   *
   * @returns A new unique ExecutionId
   *
   * @example
   * ```typescript
   * const id = ExecutionId.create();   // 'exec_<uuid>'
   * const id2 = ExecutionId.generate(); // 'exec_<uuid>'
   * ```
   */
  create: (): ExecutionId => `exec_${crypto.randomUUID()}` as ExecutionId,
};
