/**
 * Conflict resolution exports
 *
 * NOTE: ConflictStrategy, ConflictContext, ConflictResult, and MergeConfig types
 * should be imported directly from @open-zentra/foundation-data-model
 *
 * @module conflicts
 */

export {
  serverWins,
  clientWins,
  lastWriteWins,
  merge,
  manual,
  strategyResolvers,
  DEFAULT_MERGE_CONFIG,
} from './strategies';

export {
  ConflictResolver,
  getConflictResolver,
  resetConflictResolver,
  createConflictResolver,
  type ConflictResolverConfig,
} from './resolver';
