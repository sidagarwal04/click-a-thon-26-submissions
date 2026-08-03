/**
 * Disposable pattern utilities
 * @module disposable
 */

export {
  type IDisposable,
  type IAsyncDisposable,
  Disposable,
  AsyncDisposable,
  CompositeDisposable,
  DisposedError,
  createDisposable,
  using,
  usingAsync,
} from './disposable';
