/**
 * Logger implementation
 * @module logger/logger
 */

import type { LoggerConfig, LogHandler, LogLevel } from './types';
import { LOG_LEVEL, LOG_LEVEL_PRIORITY } from './types';

/**
 * Default log handler using console
 */
const defaultHandler: LogHandler = (level: LogLevel, prefix: string, ...args: unknown[]): void => {
  const timestamp = new Date().toISOString();
  const formattedPrefix = `[${timestamp}] [${prefix}]`;

  switch (level) {
    case LOG_LEVEL.DEBUG:
      console.debug(formattedPrefix, ...args);
      break;
    case LOG_LEVEL.INFO:
      console.info(formattedPrefix, ...args);
      break;
    case LOG_LEVEL.WARN:
      console.warn(formattedPrefix, ...args);
      break;
    case LOG_LEVEL.ERROR:
      console.error(formattedPrefix, ...args);
      break;
  }
};

/**
 * Logger class with level-based filtering
 */
export class Logger {
  private config: LoggerConfig;

  constructor(config: Partial<LoggerConfig> & { prefix: string }) {
    this.config = {
      level: config.level ?? LOG_LEVEL.INFO,
      prefix: config.prefix,
      handler: config.handler ?? defaultHandler,
    };
  }

  /**
   * Check if a log level should be output
   */
  private shouldLog(level: LogLevel): boolean {
    return LOG_LEVEL_PRIORITY[level] >= LOG_LEVEL_PRIORITY[this.config.level];
  }

  /**
   * Log at debug level
   */
  debug(...args: unknown[]): void {
    if (this.shouldLog(LOG_LEVEL.DEBUG)) {
      this.config.handler?.(LOG_LEVEL.DEBUG, this.config.prefix, ...args);
    }
  }

  /**
   * Log at info level
   */
  info(...args: unknown[]): void {
    if (this.shouldLog(LOG_LEVEL.INFO)) {
      this.config.handler?.(LOG_LEVEL.INFO, this.config.prefix, ...args);
    }
  }

  /**
   * Log at warn level
   */
  warn(...args: unknown[]): void {
    if (this.shouldLog(LOG_LEVEL.WARN)) {
      this.config.handler?.(LOG_LEVEL.WARN, this.config.prefix, ...args);
    }
  }

  /**
   * Log at error level
   */
  error(...args: unknown[]): void {
    if (this.shouldLog(LOG_LEVEL.ERROR)) {
      this.config.handler?.(LOG_LEVEL.ERROR, this.config.prefix, ...args);
    }
  }

  /**
   * Create a child logger with a sub-prefix
   */
  child(subPrefix: string): Logger {
    return new Logger({
      ...this.config,
      prefix: `${this.config.prefix}:${subPrefix}`,
    });
  }

  /**
   * Set the log level
   */
  setLevel(level: LogLevel): void {
    this.config.level = level;
  }

  /**
   * Get the current log level
   */
  getLevel(): LogLevel {
    return this.config.level;
  }

  /**
   * Get the logger prefix
   */
  getPrefix(): string {
    return this.config.prefix;
  }
}

/**
 * Create a logger instance
 * @param prefix - Logger namespace/prefix
 * @param options - Optional logger configuration
 * @returns Logger instance
 */
export const createLogger = (
  prefix: string,
  options?: Partial<Omit<LoggerConfig, 'prefix'>>,
): Logger => new Logger({ prefix, ...options });

/**
 * Create a debug-only logger (only logs when debug is true)
 * @param prefix - Logger namespace/prefix
 * @param debug - Whether debug logging is enabled
 * @returns Logger instance
 */
export const createDebugLogger = (prefix: string, debug: boolean): Logger =>
  new Logger({
    prefix,
    level: debug ? LOG_LEVEL.DEBUG : LOG_LEVEL.NONE,
  });
