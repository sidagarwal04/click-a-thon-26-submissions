/**
 * DuckDB rehydration controller
 * @module lifecycle/rehydration
 */

import {
  SYNC_STATE_KEY,
  Timestamp,
  type DuckDBViewsValue,
} from '@open-zentra/foundation-data-model';
import type { InsightsDatabase } from '@open-zentra/foundation-database';
import { getDatabase, SyncStateService } from '@open-zentra/foundation-database';
import {
  createDebugLogger,
  topologicalSort,
  type Logger,
} from '@open-zentra/foundation-utils';

import type { DuckDBRouter } from '../duckdb/router';
import type { ViewDefinition } from '../types/bridge';
import { validateIdentifier, validateViewSql } from '../utils/sql';

/**
 * Rehydration controller configuration
 */
export interface RehydrationControllerConfig {
  /** DuckDB router instance */
  router: DuckDBRouter;
  /** Database instance */
  database?: InsightsDatabase;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Rehydration state
 */
export interface RehydrationState {
  /** Is rehydration in progress */
  inProgress: boolean;
  /** Last rehydration timestamp */
  lastRehydratedAt: number | null;
  /** Number of views restored */
  viewsRestored: number;
  /** Number of files re-registered */
  filesRegistered: number;
  /** Any errors during rehydration */
  errors: string[];
}

/**
 * Rehydration controller for restoring DuckDB state after idle shutdown
 */
export class RehydrationController {
  private router: DuckDBRouter;
  private db: InsightsDatabase;
  private syncStateService: SyncStateService;
  private readonly logger: Logger;
  private state: RehydrationState = {
    inProgress: false,
    lastRehydratedAt: null,
    viewsRestored: 0,
    filesRegistered: 0,
    errors: [],
  };

  constructor(config: RehydrationControllerConfig) {
    this.router = config.router;
    this.db = config.database ?? getDatabase();
    this.syncStateService = new SyncStateService(this.db, this.db.config);
    this.logger = createDebugLogger('RehydrationController', config.debug ?? false);
  }

  /**
   * Get current rehydration state
   */
  getState(): RehydrationState {
    return { ...this.state };
  }

  /**
   * Save current DuckDB state to database
   */
  async saveState(): Promise<void> {
    this.logger.debug('Saving DuckDB state');

    try {
      // Get current views from router
      const views = this.router.getViewDefinitions();

      const viewsValue: DuckDBViewsValue = {
        views: views.map((v) => ({
          name: v.name,
          sql: v.sql,
          dependencies: [...v.dependencies], // Convert readonly to mutable
        })),
        lastUpdatedAt: Timestamp.now(),
      };

      // Save using type-safe service method
      await this.syncStateService.setDuckDBViews(viewsValue);

      this.logger.debug('Saved', views.length, 'views');
    } catch (error) {
      this.logger.debug('Error saving state:', error);
      throw error;
    }
  }

  /**
   * Load saved state from database
   */
  async loadState(): Promise<DuckDBViewsValue | null> {
    this.logger.debug('Loading saved state');

    try {
      const savedViews = await this.syncStateService.getDuckDBViews();

      if (!savedViews) {
        this.logger.debug('No saved state found');
        return null;
      }

      this.logger.debug('Loaded', savedViews.views.length, 'views from saved state');
      return savedViews;
    } catch (error) {
      this.logger.debug('Error loading state:', error);
      return null;
    }
  }

  /**
   * Rehydrate DuckDB state
   */
  async rehydrate(): Promise<RehydrationState> {
    if (this.state.inProgress) {
      this.logger.debug('Rehydration already in progress');
      return this.getState();
    }

    this.state = {
      inProgress: true,
      lastRehydratedAt: null,
      viewsRestored: 0,
      filesRegistered: 0,
      errors: [],
    };

    this.logger.debug('Starting rehydration');

    try {
      // Load saved state
      const savedState = await this.loadState();

      if (!savedState) {
        this.logger.debug('No saved state to restore');
        return this.finishRehydration();
      }

      // Get registered files from OPFS metadata
      const opfsFiles = await this.db.opfsFiles.where('isRegistered').equals(1).toArray();

      // Sort files by dependencies using shared utility
      const sortedFiles = topologicalSort(
        opfsFiles,
        (f) => f.path,
        (f) => f.dependencies ?? [],
      );

      // Re-register files
      for (const file of sortedFiles) {
        try {
          await this.router.registerFile(file.path, file.path);
          this.state.filesRegistered++;
          this.logger.debug('Re-registered file:', file.path);
        } catch (error) {
          const errorMsg = `Failed to re-register ${file.path}: ${error}`;
          this.state.errors.push(errorMsg);
          this.logger.debug(errorMsg);
        }
      }

      // Sort views by dependencies using shared utility
      const sortedViews = topologicalSort(
        savedState.views,
        (v) => v.name,
        (v) => v.dependencies,
      );

      // Recreate views (re-validate data loaded from DB to prevent stored injection)
      for (const viewDef of sortedViews) {
        try {
          const safeName = validateIdentifier(viewDef.name);
          validateViewSql(viewDef.sql);
          const safeDeps = viewDef.dependencies.map(validateIdentifier);

          const view: ViewDefinition = {
            name: safeName,
            sql: viewDef.sql,
            dependencies: safeDeps,
            createdAt: Timestamp.now(),
          };

          await this.router.createView(view);
          this.state.viewsRestored++;
          this.logger.debug('Recreated view:', view.name);
        } catch (error) {
          const errorMsg = `Failed to recreate view ${viewDef.name}: ${error}`;
          this.state.errors.push(errorMsg);
          this.logger.debug(errorMsg);
        }
      }

      return this.finishRehydration();
    } catch (error) {
      this.state.errors.push(`Rehydration error: ${error}`);
      return this.finishRehydration();
    }
  }

  /**
   * Finish rehydration and update state
   */
  private finishRehydration(): RehydrationState {
    this.state.inProgress = false;
    this.state.lastRehydratedAt = Timestamp.now();

    this.logger.debug('Rehydration complete:', {
      viewsRestored: this.state.viewsRestored,
      filesRegistered: this.state.filesRegistered,
      errors: this.state.errors.length,
    });

    return this.getState();
  }

  /**
   * Clear saved state
   */
  async clearState(): Promise<void> {
    await this.syncStateService.delete(SYNC_STATE_KEY.DUCKDB_VIEWS);
    this.logger.debug('Cleared saved state');
  }
}

/**
 * Create a rehydration controller
 */
export const createRehydrationController = (
  config: RehydrationControllerConfig,
): RehydrationController => new RehydrationController(config);
