/**
 * Mutex/Semaphore utilities for preventing race conditions
 * @module concurrency/mutex
 */

/**
 * Simple mutex for async operations
 * Ensures only one operation runs at a time
 */
export class Mutex {
  private locked = false;
  private queue: Array<() => void> = [];

  /**
   * Check if mutex is currently locked
   */
  get isLocked(): boolean {
    return this.locked;
  }

  /**
   * Acquire the mutex lock
   * Returns a release function
   */
  async acquire(): Promise<() => void> {
    return new Promise<() => void>((resolve) => {
      const tryAcquire = () => {
        if (!this.locked) {
          this.locked = true;
          resolve(this.release.bind(this));
        } else {
          this.queue.push(tryAcquire);
        }
      };
      tryAcquire();
    });
  }

  /**
   * Release the mutex lock
   */
  private release(): void {
    this.locked = false;
    const next = this.queue.shift();
    if (next) {
      next();
    }
  }

  /**
   * Run a function with the mutex lock
   */
  async runExclusive<T>(fn: () => Promise<T>): Promise<T> {
    const release = await this.acquire();
    try {
      return await fn();
    } finally {
      release();
    }
  }

  /**
   * Try to acquire the lock without waiting
   * Returns null if lock is already held
   */
  tryAcquire(): (() => void) | null {
    if (this.locked) {
      return null;
    }
    this.locked = true;
    return this.release.bind(this);
  }

  /**
   * Try to run a function with the mutex lock without waiting
   * Returns null if lock is already held, otherwise returns the function result
   */
  async tryRunExclusive<T>(fn: () => Promise<T>): Promise<T | null> {
    const release = this.tryAcquire();
    if (!release) {
      return null;
    }
    try {
      return await fn();
    } finally {
      release();
    }
  }

  /**
   * Get the number of waiters in the queue
   */
  get queueLength(): number {
    return this.queue.length;
  }
}

/**
 * Semaphore for limiting concurrent operations
 */
export class Semaphore {
  private permits: number;
  private queue: Array<() => void> = [];

  constructor(permits: number) {
    if (permits < 1) {
      throw new Error('Semaphore must have at least 1 permit');
    }
    this.permits = permits;
  }

  /**
   * Get available permits
   */
  get available(): number {
    return this.permits;
  }

  /**
   * Acquire a permit
   */
  async acquire(): Promise<() => void> {
    return new Promise<() => void>((resolve) => {
      const tryAcquire = () => {
        if (this.permits > 0) {
          this.permits--;
          resolve(this.release.bind(this));
        } else {
          this.queue.push(tryAcquire);
        }
      };
      tryAcquire();
    });
  }

  /**
   * Release a permit
   */
  private release(): void {
    this.permits++;
    const next = this.queue.shift();
    if (next) {
      next();
    }
  }

  /**
   * Run a function with a permit
   */
  async runWithPermit<T>(fn: () => Promise<T>): Promise<T> {
    const release = await this.acquire();
    try {
      return await fn();
    } finally {
      release();
    }
  }
}
