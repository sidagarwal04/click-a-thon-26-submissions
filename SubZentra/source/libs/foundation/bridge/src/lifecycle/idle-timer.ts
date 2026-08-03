/**
 * Idle timer for DuckDB lifecycle management
 * @module lifecycle/idle-timer
 */

import type { Milliseconds } from '@open-zentra/foundation-data-model';
import { Timestamp } from '@open-zentra/foundation-data-model';
import {
  createDebugLogger,
  Disposable,
  SafeTimer,
  type Logger,
} from '@open-zentra/foundation-utils';

/**
 * Idle timer configuration
 */
export interface IdleTimerConfig {
  /** Idle timeout in milliseconds */
  timeout: number;
  /** Callback when idle timeout is reached */
  onIdle: () => void | Promise<void>;
  /** Callback when activity is detected */
  onActivity?: () => void;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Idle timer for tracking inactivity
 *
 * Uses SafeTimer internally for proper lifecycle management and cleanup.
 * Extends Disposable to ensure proper resource cleanup.
 */
export class IdleTimer extends Disposable {
  private readonly config: IdleTimerConfig;
  private timer: SafeTimer | null = null;
  private lastActivityAt: Timestamp = Timestamp.from(0);
  private isIdle = false;
  private readonly logger: Logger;

  constructor(config: IdleTimerConfig) {
    super();
    this.config = config;
    this.logger = createDebugLogger('IdleTimer', config.debug ?? false);
  }

  /**
   * Start the idle timer
   */
  start(): void {
    this.ensureNotDisposed();
    this.touch();
    this.logger.debug('Started with timeout:', this.config.timeout, 'ms');
  }

  /**
   * Stop the idle timer
   */
  stop(): void {
    if (this.timer) {
      this.timer.dispose();
      this.timer = null;
    }
    this.logger.debug('Stopped');
  }

  /**
   * Record activity (reset timer)
   */
  touch(): void {
    this.ensureNotDisposed();
    this.lastActivityAt = Timestamp.now();
    this.isIdle = false;

    // Dispose existing timer and create new one
    if (this.timer) {
      this.timer.dispose();
      this.timer = null;
    }

    // Create new timer
    this.timer = new SafeTimer({
      delay: this.config.timeout,
      callback: () => this.handleIdle(),
      debug: this.config.debug,
      autoStart: true,
    });

    this.config.onActivity?.();
  }

  /**
   * Handle idle timeout
   */
  private async handleIdle(): Promise<void> {
    if (this.isDisposed) return;

    this.isIdle = true;
    this.timer = null;

    this.logger.debug('Idle timeout reached');

    try {
      await this.config.onIdle();
    } catch (error) {
      this.logger.debug('onIdle error:', error);
    }
  }

  /**
   * Get time since last activity
   */
  getIdleTime(): Milliseconds {
    return Timestamp.diff(Timestamp.now(), this.lastActivityAt);
  }

  /**
   * Check if currently idle
   */
  getIsIdle(): boolean {
    return this.isIdle;
  }

  /**
   * Get last activity timestamp
   */
  getLastActivityAt(): Timestamp {
    return this.lastActivityAt;
  }

  /**
   * Reset to active state
   */
  reset(): void {
    this.touch();
    this.logger.debug('Reset');
  }

  /**
   * Cleanup on dispose
   */
  protected onDispose(): void {
    this.stop();
    this.logger.debug('Disposed');
  }
}

/**
 * Create an idle timer
 */
export const createIdleTimer = (config: IdleTimerConfig): IdleTimer => new IdleTimer(config);
