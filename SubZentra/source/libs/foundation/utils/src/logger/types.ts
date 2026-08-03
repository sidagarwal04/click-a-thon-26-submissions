/**
 * Logger utility types
 * @module logger/types
 */

/**
 * Log level constant values
 */
export const LOG_LEVEL = {
  DEBUG: 'debug',
  INFO: 'info',
  WARN: 'warn',
  ERROR: 'error',
  NONE: 'none',
} as const;

/**
 * Log level type derived from LOG_LEVEL constants
 */
export type LogLevel = (typeof LOG_LEVEL)[keyof typeof LOG_LEVEL];

/**
 * Log level priority (higher = more important)
 */
export const LOG_LEVEL_PRIORITY: Readonly<Record<LogLevel, number>> = {
  [LOG_LEVEL.DEBUG]: 0,
  [LOG_LEVEL.INFO]: 1,
  [LOG_LEVEL.WARN]: 2,
  [LOG_LEVEL.ERROR]: 3,
  [LOG_LEVEL.NONE]: 4,
};

/**
 * Custom log handler function
 */
export type LogHandler = (level: LogLevel, prefix: string, ...args: unknown[]) => void;

/**
 * Logger configuration
 */
export interface LoggerConfig {
  /** Minimum log level to output */
  level: LogLevel;
  /** Logger prefix/namespace */
  prefix: string;
  /** Custom log handler */
  handler?: LogHandler;
}
