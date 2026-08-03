/**
 * Lifecycle management exports
 * @module lifecycle
 */

export { IdleTimer, createIdleTimer, type IdleTimerConfig } from './idle-timer';

export {
  RehydrationController,
  createRehydrationController,
  type RehydrationControllerConfig,
  type RehydrationState,
} from './rehydration';
