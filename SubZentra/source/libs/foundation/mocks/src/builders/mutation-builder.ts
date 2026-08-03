/**
 * Mutation Builder for Testing
 *
 * Provides a fluent API for building test Mutation objects.
 *
 * @module builders/mutation-builder
 */

import {
  EntityId,
  MutationId,
  ProvisionalId,
  Timestamp,
  type JsonSerializable,
} from '@open-zentra/foundation-data-model';

// =============================================================================
// Types
// =============================================================================

/**
 * Mutation type enum
 */
export const MUTATION_TYPE = {
  CREATE: 'create',
  UPDATE: 'update',
  DELETE: 'delete',
} as const;

export type MutationType = (typeof MUTATION_TYPE)[keyof typeof MUTATION_TYPE];

/**
 * Mutation status enum
 */
export const MUTATION_STATUS = {
  PENDING: 'pending',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export type MutationStatus = (typeof MUTATION_STATUS)[keyof typeof MUTATION_STATUS];

/**
 * Test mutation object
 */
export interface TestMutation<TData = JsonSerializable> {
  readonly id: MutationId;
  readonly type: MutationType;
  readonly tableName: string;
  readonly entityId: EntityId | ProvisionalId;
  readonly data: TData;
  readonly status: MutationStatus;
  readonly retryCount: number;
  readonly maxRetries: number;
  readonly createdAt: Timestamp;
  readonly updatedAt: Timestamp;
  readonly completedAt?: Timestamp;
  readonly error?: string;
}

/**
 * Mutation metadata for tracking
 */
export interface MutationMeta {
  readonly source: 'user' | 'sync' | 'system';
  readonly priority: number;
  readonly dependencies?: readonly MutationId[];
}

// =============================================================================
// Mutation Builder
// =============================================================================

/**
 * Builder for creating test Mutation objects
 *
 * @example
 * ```typescript
 * const mutation = MutationBuilder.create()
 *   .ofType('create')
 *   .forTable('users')
 *   .withData({ name: 'John', email: 'john@example.com' })
 *   .build();
 * ```
 */
export class MutationBuilder<TData = JsonSerializable> {
  private _id: MutationId;
  private _type: MutationType = MUTATION_TYPE.CREATE;
  private _tableName = 'test_table';
  private _entityId: EntityId | ProvisionalId;
  private _data: TData = {} as TData;
  private _status: MutationStatus = MUTATION_STATUS.PENDING;
  private _retryCount = 0;
  private _maxRetries = 3;
  private _createdAt: Timestamp;
  private _updatedAt: Timestamp;
  private _completedAt?: Timestamp;
  private _error?: string;

  private constructor() {
    this._id = MutationId.generate();
    this._entityId = ProvisionalId.generate();
    this._createdAt = Timestamp.now();
    this._updatedAt = this._createdAt;
  }

  /**
   * Create a new MutationBuilder
   */
  static create<TData = JsonSerializable>(): MutationBuilder<TData> {
    return new MutationBuilder<TData>();
  }

  /**
   * Set the mutation ID
   */
  withId(id?: MutationId): this {
    this._id = id ?? MutationId.generate();
    return this;
  }

  /**
   * Set the mutation type
   */
  ofType(type: MutationType): this {
    this._type = type;
    return this;
  }

  /**
   * Set as a create mutation
   */
  asCreate(): this {
    this._type = MUTATION_TYPE.CREATE;
    return this;
  }

  /**
   * Set as an update mutation
   */
  asUpdate(): this {
    this._type = MUTATION_TYPE.UPDATE;
    return this;
  }

  /**
   * Set as a delete mutation
   */
  asDelete(): this {
    this._type = MUTATION_TYPE.DELETE;
    return this;
  }

  /**
   * Set the target table
   */
  forTable(tableName: string): this {
    this._tableName = tableName;
    return this;
  }

  /**
   * Set the entity ID
   */
  forEntity(id: EntityId | ProvisionalId | string): this {
    if (typeof id === 'string') {
      this._entityId = EntityId.from(id);
    } else {
      this._entityId = id;
    }
    return this;
  }

  /**
   * Set the mutation data
   */
  withData(data: TData): this {
    this._data = data;
    return this;
  }

  /**
   * Set the mutation status
   */
  withStatus(status: MutationStatus): this {
    this._status = status;
    return this;
  }

  /**
   * Mark as pending
   */
  asPending(): this {
    this._status = MUTATION_STATUS.PENDING;
    return this;
  }

  /**
   * Mark as in progress
   */
  asInProgress(): this {
    this._status = MUTATION_STATUS.IN_PROGRESS;
    return this;
  }

  /**
   * Mark as completed
   */
  asCompleted(): this {
    this._status = MUTATION_STATUS.COMPLETED;
    this._completedAt = Timestamp.now();
    return this;
  }

  /**
   * Mark as failed
   */
  asFailed(error: string): this {
    this._status = MUTATION_STATUS.FAILED;
    this._error = error;
    return this;
  }

  /**
   * Set retry configuration
   */
  withRetries(count: number, max = 3): this {
    this._retryCount = count;
    this._maxRetries = max;
    return this;
  }

  /**
   * Set timestamps
   */
  withTimestamps(created: Timestamp, updated?: Timestamp): this {
    this._createdAt = created;
    this._updatedAt = updated ?? created;
    return this;
  }

  /**
   * Build the test mutation
   */
  build(): TestMutation<TData> {
    return {
      id: this._id,
      type: this._type,
      tableName: this._tableName,
      entityId: this._entityId,
      data: this._data,
      status: this._status,
      retryCount: this._retryCount,
      maxRetries: this._maxRetries,
      createdAt: this._createdAt,
      updatedAt: this._updatedAt,
      completedAt: this._completedAt,
      error: this._error,
    };
  }
}

/**
 * Create a quick test mutation with minimal configuration
 *
 * @example
 * ```typescript
 * const mutation = quickMutation({
 *   type: 'create',
 *   tableName: 'users',
 *   data: { name: 'John' }
 * });
 * ```
 */
export function quickMutation<TData = JsonSerializable>(
  overrides: Partial<TestMutation<TData>> = {},
): TestMutation<TData> {
  const now = Timestamp.now();
  return {
    id: overrides.id ?? MutationId.generate(),
    type: overrides.type ?? MUTATION_TYPE.CREATE,
    tableName: overrides.tableName ?? 'test_table',
    entityId: overrides.entityId ?? ProvisionalId.generate(),
    data: overrides.data ?? ({} as TData),
    status: overrides.status ?? MUTATION_STATUS.PENDING,
    retryCount: overrides.retryCount ?? 0,
    maxRetries: overrides.maxRetries ?? 3,
    createdAt: overrides.createdAt ?? now,
    updatedAt: overrides.updatedAt ?? now,
    completedAt: overrides.completedAt,
    error: overrides.error,
  };
}
