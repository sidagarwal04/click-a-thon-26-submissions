/**
 * Mutation Queue Service
 *
 * Service for managing the mutation queue in the database.
 * Implements MutationQueueOperations interface with fixed idempotency.
 *
 * @module services/mutation-queue
 */

import Dexie from 'dexie';

import {
  MUTATION_STATUS,
  type CreateMutationOptions,
  type MutationQueueEntry,
  type MutationStatus,
} from '@open-zentra/foundation-data-model';

import { createDuplicateEntryError } from '../errors/database-errors';
import type { MutationQueueOperations } from '../tables/mutation-queue';
import { generateIdempotencyKey as generateIdempotencyKeyUtil } from '../utils/hash';
import { assertValid } from '../validation/assert-valid';
import { mutationQueueEntrySchema } from '../validation/schemas';
import { BaseService } from './base';

/**
 * Extended CreateMutationOptions with optional idempotency key
 */
export interface ExtendedCreateMutationOptions extends CreateMutationOptions {
  /** Custom idempotency key (if not provided, will be generated from payload) */
  idempotencyKey?: string;
}

/**
 * Mutation Queue Service
 * Implements MutationQueueOperations with fixed idempotency key generation
 */
export class MutationQueueService extends BaseService implements MutationQueueOperations {
  /**
   * Validate and insert a mutation with idempotency protection in one transaction.
   */
  private insertWithIdempotencyCheck = async (
    entry: MutationQueueEntry,
    throwOnDuplicate: boolean,
  ): Promise<boolean> => {
    assertValid(mutationQueueEntrySchema, entry, 'MutationQueueEntry');

    return this.db.transaction('rw', this.db.mutations, async () => {
      const existing = await this.db.mutations
        .where('idempotencyKey')
        .equals(entry.idempotencyKey)
        .first();

      if (existing) {
        this.log('Duplicate mutation ignored:', entry.idempotencyKey);
        if (throwOnDuplicate) {
          throw createDuplicateEntryError(entry.idempotencyKey, 'mutation');
        }
        return false;
      }

      await this.db.mutations.add(entry);
      this.log('Mutation added:', entry.id);
      return true;
    });
  };

  /**
   * Generate idempotency key for a mutation
   * Uses the shared utility from utils/hash.ts
   */
  generateIdempotencyKey = (options: ExtendedCreateMutationOptions): string => {
    return generateIdempotencyKeyUtil({
      tableName: options.tableName,
      entityId: options.entityId,
      payload: options.payload,
      customKey: options.idempotencyKey,
    });
  };

  /**
   * Add a mutation to the queue
   * Checks for duplicate idempotency keys
   * Uses transaction to prevent race conditions (TOCTOU)
   */
  add = async (entry: MutationQueueEntry): Promise<void> => {
    await this.insertWithIdempotencyCheck(entry, true);
  };

  /**
   * Add a mutation, silently ignoring duplicates
   * Uses transaction to prevent race conditions (TOCTOU)
   */
  addIfNotExists = async (entry: MutationQueueEntry): Promise<boolean> => {
    return this.insertWithIdempotencyCheck(entry, false);
  };

  /**
   * Get mutation by ID
   */
  get = async (id: string): Promise<MutationQueueEntry | undefined> => {
    return this.db.mutations.get(id);
  };

  /**
   * Update mutation status
   */
  updateStatus = async (
    id: string,
    status: MutationStatus,
    updates?: Partial<MutationQueueEntry>,
  ): Promise<void> => {
    await this.db.mutations.update(id, { status, ...updates });
    this.log('Mutation status updated:', id, status);
  };

  /**
   * Get all pending mutations in order
   */
  getPending = async (): Promise<MutationQueueEntry[]> => {
    const [pending, offlineQueued] = await Promise.all([
      this.db.mutations
        .where('[status+timestamp]')
        .between(
          [MUTATION_STATUS.PENDING, Dexie.minKey],
          [MUTATION_STATUS.PENDING, Dexie.maxKey],
          true,
          true,
        )
        .toArray(),
      this.db.mutations
        .where('[status+timestamp]')
        .between(
          [MUTATION_STATUS.OFFLINE_QUEUED, Dexie.minKey],
          [MUTATION_STATUS.OFFLINE_QUEUED, Dexie.maxKey],
          true,
          true,
        )
        .toArray(),
    ]);
    return [...pending, ...offlineQueued].sort((a, b) => a.timestamp - b.timestamp);
  };

  /**
   * Get mutations by status
   */
  getByStatus = async (status: MutationStatus): Promise<MutationQueueEntry[]> => {
    return this.db.mutations.where('status').equals(status).toArray();
  };

  /**
   * Delete completed mutations
   */
  deleteCompleted = async (): Promise<number> => {
    const count = await this.db.mutations
      .where('status')
      .equals(MUTATION_STATUS.COMPLETED)
      .delete();
    if (count > 0) {
      this.log(`Deleted ${count} completed mutations`);
    }
    return count;
  };

  /**
   * Delete mutation by ID
   */
  delete = async (id: string): Promise<void> => {
    await this.db.mutations.delete(id);
    this.log('Mutation deleted:', id);
  };

  /**
   * Count mutations by status
   */
  countByStatus = async (status: MutationStatus): Promise<number> => {
    return this.db.mutations.where('status').equals(status).count();
  };

  /**
   * Mark all pending mutations as offline queued
   */
  markAllOfflineQueued = async (): Promise<number> => {
    const count = await this.db.mutations
      .where('status')
      .equals(MUTATION_STATUS.PENDING)
      .modify({ status: MUTATION_STATUS.OFFLINE_QUEUED });
    this.log(`Marked ${count} mutations as offline queued`);
    return count;
  };

  /**
   * Find mutation by idempotency key
   */
  findByIdempotencyKey = async (key: string): Promise<MutationQueueEntry | undefined> => {
    return this.db.mutations.where('idempotencyKey').equals(key).first();
  };

  /**
   * Get total count of mutations
   */
  count = async (): Promise<number> => {
    return this.db.mutations.count();
  };

  /**
   * Clear all mutations
   */
  clear = async (): Promise<void> => {
    await this.db.mutations.clear();
    this.log('Mutation queue cleared');
  };

  // =========================================================================
  // Bulk Operations
  // =========================================================================

  /**
   * Get multiple mutations by IDs in a single operation
   *
   * Returns entries in the same order as the input IDs.
   * Missing entries are represented as undefined in the result array.
   *
   * @param ids - Array of mutation IDs to retrieve
   * @returns Array of mutation entries (undefined for missing entries)
   */
  bulkGet = async (ids: string[]): Promise<(MutationQueueEntry | undefined)[]> => {
    if (ids.length === 0) return [];

    const entries = await this.db.mutations.bulkGet(ids);
    this.log(`Bulk get ${ids.length} mutations, found ${entries.filter(Boolean).length}`);
    return entries;
  };

  /**
   * Add multiple mutations in a single operation
   * Validates all entries before adding
   */
  bulkAdd = async (entries: MutationQueueEntry[]): Promise<void> => {
    if (entries.length === 0) return;

    // Validate all entries first
    for (const entry of entries) {
      assertValid(mutationQueueEntrySchema, entry, 'MutationQueueEntry');
    }

    await this.db.mutations.bulkAdd(entries);
    this.log(`Bulk added ${entries.length} mutations`);
  };

  /**
   * Delete multiple mutations by IDs
   */
  bulkDelete = async (ids: string[]): Promise<number> => {
    if (ids.length === 0) return 0;

    const existing = await this.db.mutations.bulkGet(ids);
    const existingCount = existing.filter((entry) => entry !== undefined).length;

    await this.db.mutations.bulkDelete(ids);
    this.log(`Bulk deleted ${existingCount} mutations`);
    return existingCount;
  };
}
