/**
 * Disposable pattern utilities
 *
 * Provides interfaces and base classes for resource cleanup following the
 * disposable pattern commonly used in managed runtimes.
 *
 * @module disposable
 */

/**
 * Disposable interface for resource cleanup
 */
export interface IDisposable {
  /** Dispose of resources */
  dispose(): void;
  /** Check if disposed */
  readonly isDisposed: boolean;
}

/**
 * Async disposable interface
 */
export interface IAsyncDisposable {
  /** Async dispose of resources */
  disposeAsync(): Promise<void>;
  /** Check if disposed */
  readonly isDisposed: boolean;
}

/**
 * Error thrown when trying to use a disposed object
 */
export class DisposedError extends Error {
  constructor(className: string) {
    super(`Cannot use disposed ${className}`);
    this.name = 'DisposedError';
  }
}

/**
 * Base class for disposable objects
 */
export abstract class Disposable implements IDisposable {
  private _isDisposed = false;

  get isDisposed(): boolean {
    return this._isDisposed;
  }

  /**
   * Ensure the object is not disposed before use
   */
  protected ensureNotDisposed(): void {
    if (this._isDisposed) {
      throw new DisposedError(this.constructor.name);
    }
  }

  /**
   * Dispose of resources
   */
  dispose(): void {
    if (this._isDisposed) return;
    this._isDisposed = true;
    this.onDispose();
  }

  /**
   * Override to implement cleanup logic
   */
  protected abstract onDispose(): void;
}

/**
 * Base class for async disposable objects
 */
export abstract class AsyncDisposable implements IAsyncDisposable {
  private _isDisposed = false;

  get isDisposed(): boolean {
    return this._isDisposed;
  }

  /**
   * Ensure the object is not disposed before use
   */
  protected ensureNotDisposed(): void {
    if (this._isDisposed) {
      throw new DisposedError(this.constructor.name);
    }
  }

  /**
   * Async dispose of resources
   */
  async disposeAsync(): Promise<void> {
    if (this._isDisposed) return;
    this._isDisposed = true;
    await this.onDisposeAsync();
  }

  /**
   * Override to implement async cleanup logic
   */
  protected abstract onDisposeAsync(): Promise<void>;
}

/**
 * Composite disposable - disposes multiple resources
 */
export class CompositeDisposable implements IDisposable {
  private disposables: IDisposable[] = [];
  private _isDisposed = false;

  get isDisposed(): boolean {
    return this._isDisposed;
  }

  /**
   * Add a disposable to be managed
   */
  add(disposable: IDisposable): void {
    if (this._isDisposed) {
      disposable.dispose();
      return;
    }
    this.disposables.push(disposable);
  }

  /**
   * Add a cleanup function as a disposable
   */
  addFunction(cleanup: () => void): void {
    this.add({
      isDisposed: false,
      dispose: cleanup,
    });
  }

  /**
   * Remove a disposable without disposing it
   */
  remove(disposable: IDisposable): boolean {
    const index = this.disposables.indexOf(disposable);
    if (index !== -1) {
      this.disposables.splice(index, 1);
      return true;
    }
    return false;
  }

  /**
   * Dispose all managed disposables
   */
  dispose(): void {
    if (this._isDisposed) return;
    this._isDisposed = true;

    // Dispose in reverse order (LIFO)
    for (let i = this.disposables.length - 1; i >= 0; i--) {
      try {
        this.disposables[i].dispose();
      } catch (error) {
        console.error('Error disposing resource:', error);
      }
    }
    this.disposables = [];
  }

  /**
   * Get the count of managed disposables
   */
  get count(): number {
    return this.disposables.length;
  }
}

/**
 * Create a disposable from a cleanup function
 */
export const createDisposable = (cleanup: () => void): IDisposable => {
  let disposed = false;
  return {
    get isDisposed() {
      return disposed;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      cleanup();
    },
  };
};

/**
 * Using pattern - ensures disposal after use
 */
export const using = <T extends IDisposable, R>(disposable: T, fn: (resource: T) => R): R => {
  try {
    return fn(disposable);
  } finally {
    disposable.dispose();
  }
};

/**
 * Async using pattern
 */
export const usingAsync = async <T extends IAsyncDisposable, R>(
  disposable: T,
  fn: (resource: T) => Promise<R>,
): Promise<R> => {
  try {
    return await fn(disposable);
  } finally {
    await disposable.disposeAsync();
  }
};
