/**
 * Base Service Class
 *
 * Abstract base class for all database services.
 * Provides shared functionality following DRY principle.
 *
 * ## Return Type Convention
 *
 * Services follow a consistent return type convention for "not found" scenarios:
 *
 * - `null` - Used when a specific lookup fails after a successful query.
 *   Example: QueryCacheService.get() returns null when a cache entry doesn't exist
 *   but the query completed successfully.
 *
 * - `undefined` - Used for optional values and generic key-value lookups.
 *   Example: SyncStateService.get() returns undefined when a key doesn't exist,
 *   MutationQueueService.get() returns undefined when a mutation ID doesn't exist.
 *
 * This convention aligns with JavaScript semantics where:
 * - `null` explicitly represents "no value" (intentional absence)
 * - `undefined` represents "value not set" (optional/missing)
 *
 * @module services/base
 */

import {
  createDebugLogger,
  getErrorMessage,
  type Logger,
} from '@open-zentra/foundation-utils';

import type { DatabaseConfig } from '../core/config';
import type { InsightsDatabase } from '../core/database';

/**
 * Abstract base service with shared utilities
 *
 * All services should follow the return type convention documented above.
 */
export abstract class BaseService {
  protected readonly db: InsightsDatabase;
  protected readonly config: DatabaseConfig;
  protected readonly logger: Logger;

  constructor(db: InsightsDatabase, config: DatabaseConfig) {
    this.db = db;
    this.config = config;
    // Use createDebugLogger from foundation-utils for consistent logging
    this.logger = createDebugLogger(this.constructor.name, config.debug);
  }

  /**
   * Shared logging utility using foundation-utils logger
   */
  protected log = (message: string, ...args: unknown[]): void => {
    this.logger.debug(message, ...args);
  };

  /**
   * Shared error handler (DRY)
   * Logs the error and re-throws
   */
  protected handleError = (operation: string, error: unknown): never => {
    const message = getErrorMessage(error);
    this.logger.error(`Error in ${operation}:`, message);
    throw error;
  };

  /**
   * Get the service name for logging
   */
  protected get serviceName(): string {
    return this.constructor.name;
  }
}
