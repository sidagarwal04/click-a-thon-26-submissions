/**
 * @foundation/sync-engine - Internal Exports
 *
 * @internal
 * Internal exports for foundation library use only.
 * Not part of public API - may change without notice.
 *
 * These exports are used internally by the foundation layer but should not
 * be imported directly by application code. Use the public coordinator API instead.
 *
 * NOTE: For Mutex, Semaphore, Disposable, Logger, and other utilities,
 * import directly from @open-zentra/foundation-utils
 *
 * @packageDocumentation
 */

// ============================================================================
// Container (Internal)
// ============================================================================

export {
  SyncEngineContainer,
  SyncEngineFactory,
  syncEngineFactory,
  createSyncEngineContainer,
  type SyncEngineContainerConfig,
} from './core';
