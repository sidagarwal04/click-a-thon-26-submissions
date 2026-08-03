/**
 * Analytics Sync module
 *
 * Background parquet synchronization primitives and hooks.
 *
 * @module analytics-sync
 */

export {
  useBackgroundFileSync,
  type UseBackgroundFileSyncOptions,
  type UseBackgroundFileSyncResult,
  type BackgroundSyncState,
} from './use-background-file-sync';

export { INITIAL_DOWNLOAD_STATE, type DownloadProgressState } from './file-download-service';
