/**
 * Logger Utility
 *
 * Level-based logging with namespaces and customizable handlers.
 *
 * @module logger
 */

export { Logger, createLogger, createDebugLogger } from './logger';
export {
  LOG_LEVEL,
  LOG_LEVEL_PRIORITY,
  type LogLevel,
  type LogHandler,
  type LoggerConfig,
} from './types';
