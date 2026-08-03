/**
 * Network status monitor
 * @module network
 */

import axios, { type AxiosInstance } from 'axios';

import {
  SYNC_STATE_KEY,
  type NetworkStatus,
  type NetworkStatusListener,
} from '@open-zentra/foundation-data-model';
import type { InsightsDatabase } from '@open-zentra/foundation-database';
import { DEFAULT_NETWORK_STATUS, getDatabase } from '@open-zentra/foundation-database';
import {
  AsyncDisposable,
  createDebugLogger,
  createSingletonFactory,
  ManagedInterval,
  normalizeError,
} from '@open-zentra/foundation-utils';

import {
  DEFAULT_HEALTH_CHECK_INTERVAL_MS,
  DEFAULT_HEALTH_CHECK_TIMEOUT_MS,
  DEFAULT_HEALTH_CHECK_URL,
} from '../core/defaults';
import type { INetworkMonitor } from '../core/interfaces';

/**
 * Network status event values.
 */
export const NETWORK_STATUS_EVENT = {
  ONLINE: 'online',
  OFFLINE: 'offline',
  CONNECTIVITY_CHECK: 'connectivity_check',
} as const;

export type NetworkStatusEvent = (typeof NETWORK_STATUS_EVENT)[keyof typeof NETWORK_STATUS_EVENT];

/**
 * Network monitor configuration
 */
export interface NetworkMonitorConfig {
  /** Database instance */
  database?: InsightsDatabase;
  /** Health check URL */
  healthCheckUrl?: string;
  /** Health check interval in ms (0 = disabled) */
  healthCheckInterval?: number;
  /** Timeout for health check requests */
  healthCheckTimeout?: number;
  /** Optional shared Axios instance for connectivity checks */
  axiosInstance?: AxiosInstance;
  /** Enable debug logging */
  debug?: boolean;
  /** Error callback for centralized error handling */
  onError?: (error: Error, context?: string) => void;
}

type ResolvedNetworkMonitorConfig = Required<
  Omit<NetworkMonitorConfig, 'database' | 'onError' | 'axiosInstance'>
>;

/**
 * Default network monitor configuration
 */
const DEFAULT_CONFIG: ResolvedNetworkMonitorConfig = {
  healthCheckUrl: DEFAULT_HEALTH_CHECK_URL,
  healthCheckInterval: DEFAULT_HEALTH_CHECK_INTERVAL_MS,
  healthCheckTimeout: DEFAULT_HEALTH_CHECK_TIMEOUT_MS,
  debug: false,
};

/**
 * Type guard to validate NetworkStatus structure
 */
const isValidNetworkStatusValue = (value: unknown): value is NetworkStatus =>
  value !== null &&
  typeof value === 'object' &&
  'isOnline' in value &&
  typeof value.isOnline === 'boolean';

/**
 * Network status monitor with proper disposal
 */
export class NetworkStatusMonitor extends AsyncDisposable implements INetworkMonitor {
  private db: InsightsDatabase;
  private config: ResolvedNetworkMonitorConfig;
  private axiosInstance: AxiosInstance;
  private onError?: (error: Error, context?: string) => void;
  private listeners: Set<NetworkStatusListener> = new Set();
  private currentStatus: NetworkStatus;
  private healthCheckInterval: ManagedInterval | null = null;
  private abortController: AbortController | null = null;
  private started = false;
  private windowListenersAttached = false;
  private logger;

  constructor(config: NetworkMonitorConfig = {}) {
    super();
    const { database, onError, axiosInstance, ...resolvedConfig } = config;
    this.config = { ...DEFAULT_CONFIG, ...resolvedConfig };
    this.onError = onError;
    this.db = database ?? getDatabase();
    this.axiosInstance = axiosInstance ?? axios;
    this.currentStatus = { ...DEFAULT_NETWORK_STATUS };
    this.logger = createDebugLogger('NetworkStatusMonitor', this.config.debug);
  }

  /**
   * Handle errors with optional callback
   */
  private handleError(error: unknown, context?: string): void {
    const err = normalizeError(error);
    this.logger.error(`Error in ${context ?? 'unknown'}:`, err);
    this.onError?.(err, context);
  }

  /**
   * Get current network status
   */
  get status(): NetworkStatus {
    return { ...this.currentStatus };
  }

  /**
   * Check if currently online
   */
  get isOnline(): boolean {
    return this.currentStatus.isOnline;
  }

  /**
   * Start monitoring network status
   */
  async start(): Promise<void> {
    this.ensureNotDisposed();
    if (this.started) return;
    this.started = true;

    // Load persisted status with type validation
    try {
      const entry = await this.db.syncState.get(SYNC_STATE_KEY.NETWORK_STATUS);
      if (entry?.value) {
        if (isValidNetworkStatusValue(entry.value)) {
          this.currentStatus = entry.value;
        } else {
          this.logger.warn('Invalid network status format in storage, using default');
        }
      }
    } catch (error) {
      this.handleError(error, 'Load persisted status');
    }

    // Set up browser event listeners
    if (typeof window !== 'undefined') {
      this.attachWindowListeners();

      const connectionType = this.getNavigatorConnectionType();
      if (connectionType) {
        this.currentStatus.connectionType = connectionType;
      }
    }

    // Start health checks
    if (this.config.healthCheckInterval > 0) {
      this.startHealthChecks();
    }

    // Initial check
    await this.checkConnectivity();

    this.logger.debug('Started monitoring');
  }

  /**
   * Stop monitoring
   */
  stop(): void {
    if (!this.started) return;
    this.started = false;

    this.stopHealthChecks();
    this.abortController?.abort();
    this.abortController = null;
    this.detachWindowListeners();

    // Clear listeners
    this.listeners.clear();

    this.logger.debug('Stopped monitoring');
  }

  /**
   * Subscribe to status changes
   */
  subscribe(listener: NetworkStatusListener): () => void {
    this.ensureNotDisposed();
    this.listeners.add(listener);
    // Immediately call with current status
    listener(this.status);

    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Manual connectivity check
   */
  async checkConnectivity(): Promise<boolean> {
    this.ensureNotDisposed();

    // First check navigator.onLine
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      this.setOffline();
      return false;
    }

    // Then do a real connectivity check
    try {
      this.abortController?.abort();
      this.abortController = new AbortController();

      const timeoutSignal = AbortSignal.timeout
        ? AbortSignal.timeout(this.config.healthCheckTimeout)
        : this.abortController.signal;

      // Resolve relative URLs against the current origin so the check
      // works correctly in all environments (browser, SSR, tests).
      const healthCheckUrl = this.resolveHealthCheckUrl(this.config.healthCheckUrl);

      const response = await this.axiosInstance.head(healthCheckUrl, {
        signal: timeoutSignal,
        timeout: this.config.healthCheckTimeout,
        headers: {
          'Cache-Control': 'no-store',
          Pragma: 'no-cache',
        },
        validateStatus: () => true,
      });

      if (response.status >= 200 && response.status < 300) {
        this.setOnline();
        return true;
      }

      this.setOffline();
      return false;
    } catch (error) {
      // Network error means offline
      if (error instanceof Error && error.name !== 'AbortError' && error.name !== 'CanceledError') {
        this.setOffline();
      }
      return false;
    }
  }

  /**
   * Resolve a health-check URL to an absolute URL.
   *
   * If the URL is already absolute it is returned as-is.
   * Relative URLs are resolved against `window.location.origin` when
   * running in a browser. Outside a browser context a relative URL
   * is returned unchanged (caller is responsible for providing an
   * absolute URL in non-browser environments).
   */
  private resolveHealthCheckUrl(url: string): string {
    // Already absolute
    if (/^https?:\/\//i.test(url)) {
      return url;
    }

    // In a browser, resolve against the current origin
    if (typeof window !== 'undefined' && window.location?.origin) {
      try {
        return new URL(url, window.location.origin).href;
      } catch {
        this.logger.warn('Failed to resolve health check URL, using as-is', { url });
      }
    }

    return url;
  }

  /**
   * Get connection type from navigator.connection when available.
   */
  private getNavigatorConnectionType = (): string | undefined => {
    if (typeof navigator === 'undefined') {
      return undefined;
    }

    const connectionValue = Reflect.get(navigator, 'connection');
    if (typeof connectionValue !== 'object' || connectionValue === null) {
      return undefined;
    }

    const typeValue = Reflect.get(connectionValue, 'type');
    return typeof typeValue === 'string' ? typeValue : undefined;
  };

  /**
   * Attach browser connectivity listeners once.
   */
  private attachWindowListeners = (): void => {
    if (this.windowListenersAttached || typeof window === 'undefined') {
      return;
    }

    window.addEventListener('online', this.handleOnline);
    window.addEventListener('offline', this.handleOffline);
    this.windowListenersAttached = true;
  };

  /**
   * Detach browser connectivity listeners.
   */
  private detachWindowListeners = (): void => {
    if (!this.windowListenersAttached || typeof window === 'undefined') {
      return;
    }

    window.removeEventListener('online', this.handleOnline);
    window.removeEventListener('offline', this.handleOffline);
    this.windowListenersAttached = false;
  };

  /**
   * Async dispose implementation
   */
  protected async onDisposeAsync(): Promise<void> {
    this.stop();
    this.listeners.clear();
    this.logger.debug('Disposed');
  }

  /**
   * Handle browser online event
   */
  private handleOnline = (): void => {
    this.logger.debug('Browser online event');
    // Verify with health check
    this.checkConnectivity().catch((error) => {
      this.handleError(error, 'Browser online connectivity check');
    });
  };

  /**
   * Handle browser offline event
   */
  private handleOffline = (): void => {
    this.logger.debug('Browser offline event');
    this.setOffline();
  };

  /**
   * Set status to online
   */
  private setOnline(): void {
    if (this.currentStatus.isOnline) return;

    this.currentStatus = {
      ...this.currentStatus,
      isOnline: true,
      lastOnlineAt: Date.now(),
    };

    this.persistStatus();
    this.notifyListeners();
    this.logger.debug('Status changed to online');
  }

  /**
   * Set status to offline
   */
  private setOffline(): void {
    if (!this.currentStatus.isOnline) return;

    this.currentStatus = {
      ...this.currentStatus,
      isOnline: false,
      lastOfflineAt: Date.now(),
    };

    this.persistStatus();
    this.notifyListeners();
    this.logger.debug('Status changed to offline');
  }

  /**
   * Start periodic health checks using ManagedInterval for proper cleanup
   */
  private startHealthChecks(): void {
    if (this.healthCheckInterval) return;

    this.healthCheckInterval = new ManagedInterval({
      interval: this.config.healthCheckInterval,
      callback: () => {
        this.checkConnectivity().catch((error) => {
          this.handleError(error, 'Periodic health check');
        });
      },
      debug: this.config.debug,
      autoStart: true,
    });
  }

  /**
   * Stop periodic health checks
   */
  private stopHealthChecks(): void {
    if (this.healthCheckInterval) {
      this.healthCheckInterval.dispose();
      this.healthCheckInterval = null;
    }
  }

  /**
   * Persist status to database
   */
  private persistStatus(): void {
    const persistedStatus = {
      isOnline: this.currentStatus.isOnline,
      lastOnlineAt: this.currentStatus.lastOnlineAt,
      lastOfflineAt: this.currentStatus.lastOfflineAt,
      connectionType: this.currentStatus.connectionType ?? null,
    };

    this.db.syncState
      .put({
        key: SYNC_STATE_KEY.NETWORK_STATUS,
        value: persistedStatus,
        updatedAt: Date.now(),
      })
      .catch((error) => {
        this.handleError(error, 'Status persistence');
      });
  }

  /**
   * Notify all listeners
   */
  private notifyListeners(): void {
    const status = this.status;
    for (const listener of this.listeners) {
      try {
        listener(status);
      } catch (error) {
        this.logger.error('Listener error:', error);
      }
    }
  }
}

// NOTE: NetworkStatusListener is now in @foundation/data-model
// Import it from there for consistency across the codebase

/**
 * Singleton factory for network monitor
 */
const networkMonitorFactory = createSingletonFactory(
  (config: NetworkMonitorConfig | undefined) => new NetworkStatusMonitor(config),
  {
    name: 'NetworkStatusMonitor',
    onDispose: async (instance) => {
      if (instance instanceof NetworkStatusMonitor) {
        await instance.disposeAsync();
      }
    },
  },
);

/**
 * Get or create network monitor singleton instance.
 */
export const getNetworkMonitor = (config?: NetworkMonitorConfig): NetworkStatusMonitor =>
  networkMonitorFactory.getInstance(config);

/**
 * Reset network monitor singleton (for testing).
 */
export const resetNetworkMonitor = (): void => {
  void networkMonitorFactory.reset();
};

/**
 * Create a new NetworkStatusMonitor instance (non-singleton).
 */
export const createNetworkMonitor = (config?: NetworkMonitorConfig): NetworkStatusMonitor =>
  new NetworkStatusMonitor(config);
