/**
 * Auth Container
 *
 * Centralized dependency injection container for authentication services.
 * Manages initialization and disposal of auth-related services.
 *
 * @module core/container
 */

import { Mutex } from '@open-zentra/foundation-utils';

import { createOryClientConfig, getOryClient, type OryClientInstance } from './ory-client';
import type {
  AuthConfig,
  AuthFacadeInterface,
  FlowServiceInterface,
  SessionServiceInterface,
  UserServiceInterface,
} from './types';

// =============================================================================
// Types
// =============================================================================

/**
 * Auth container dependencies
 */
export interface AuthContainerDependencies {
  /** Ory client instance */
  oryClient: OryClientInstance;
  /** Session service */
  sessionService: SessionServiceInterface;
  /** Flow service */
  flowService: FlowServiceInterface;
  /** User service */
  userService: UserServiceInterface;
  /** Auth facade */
  facade: AuthFacadeInterface;
  /** Auth configuration */
  config: AuthConfig;
}

/**
 * Factory functions for creating dependencies
 */
export interface AuthDependencyFactories {
  /** Factory for session service */
  sessionService?: (client: OryClientInstance, config: AuthConfig) => SessionServiceInterface;
  /** Factory for flow service */
  flowService?: (client: OryClientInstance, config: AuthConfig) => FlowServiceInterface;
  /** Factory for user service */
  userService?: (client: OryClientInstance, config: AuthConfig) => UserServiceInterface;
  /** Factory for auth facade */
  facade?: (
    sessionService: SessionServiceInterface,
    flowService: FlowServiceInterface,
    userService: UserServiceInterface,
    config: AuthConfig,
  ) => AuthFacadeInterface;
}

/**
 * Auth container configuration
 */
export interface AuthContainerConfig {
  /** Auth configuration */
  config: AuthConfig;
  /** Optional factory overrides (for testing) */
  factories?: AuthDependencyFactories;
}

// =============================================================================
// Auth Container
// =============================================================================

/**
 * Auth container class
 *
 * Manages the lifecycle of authentication services with:
 * - Idempotent initialization (multiple calls return same promise)
 * - Mutex-protected disposal for race condition prevention
 * - Factory override support for testing
 *
 * @example
 * ```typescript
 * const container = new AuthContainer({
 *   config: {
 *     ory: { kratosUrl: 'https://your-project.ory.cloud' },
 *   },
 * });
 *
 * const deps = await container.initialize();
 * // Use deps.facade, deps.sessionService, etc.
 *
 * // Later, dispose
 * await container.dispose();
 * ```
 */
export class AuthContainer {
  private readonly containerConfig: AuthContainerConfig;
  private readonly disposeMutex = new Mutex();

  private deps: AuthContainerDependencies | null = null;
  private initPromise: Promise<AuthContainerDependencies> | null = null;
  private disposed = false;

  constructor(containerConfig: AuthContainerConfig) {
    this.containerConfig = containerConfig;
  }

  /**
   * Check if container is initialized
   */
  get isInitialized(): boolean {
    return this.deps !== null;
  }

  /**
   * Check if container is disposed
   */
  get isDisposed(): boolean {
    return this.disposed;
  }

  /**
   * Initialize the container and create all dependencies
   *
   * Multiple calls return the same promise (idempotent).
   */
  initialize = async (): Promise<AuthContainerDependencies> => {
    // Already disposed
    if (this.disposed) {
      throw new Error('[AuthContainer] Container has been disposed');
    }

    // Already initialized
    if (this.deps !== null) {
      return this.deps;
    }

    // Already initializing (return existing promise)
    if (this.initPromise !== null) {
      return this.initPromise;
    }

    // Start initialization
    this.initPromise = this.createDependencies();

    try {
      this.deps = await this.initPromise;
      return this.deps;
    } catch (error) {
      // Reset on failure to allow retry
      this.initPromise = null;
      throw error;
    }
  };

  /**
   * Dispose all resources
   *
   * Mutex-protected to prevent race conditions during disposal.
   */
  dispose = async (): Promise<void> => {
    // Use mutex to prevent concurrent disposal
    const release = await this.disposeMutex.acquire();

    try {
      // Already disposed
      if (this.disposed) {
        return;
      }

      // Wait for any pending initialization
      if (this.initPromise !== null) {
        try {
          await this.initPromise;
        } catch {
          // Ignore init errors during disposal
        }
        this.initPromise = null;
      }

      // Dispose services in reverse order
      if (this.deps !== null) {
        const { facade, userService, flowService, sessionService } = this.deps;

        // Dispose facade first (it coordinates other services)
        await facade.dispose().catch(console.error);

        // Dispose individual services
        await userService.dispose().catch(console.error);
        await flowService.dispose().catch(console.error);
        await sessionService.dispose().catch(console.error);

        this.deps = null;
      }

      this.disposed = true;
    } finally {
      release();
    }
  };

  /**
   * Get dependencies (throws if not initialized)
   */
  getDependencies = (): AuthContainerDependencies => {
    if (this.disposed) {
      throw new Error('[AuthContainer] Container has been disposed');
    }
    if (this.deps === null) {
      throw new Error('[AuthContainer] Container not initialized. Call initialize() first.');
    }
    return this.deps;
  };

  /**
   * Create all dependencies
   */
  private createDependencies = async (): Promise<AuthContainerDependencies> => {
    const { config, factories = {} } = this.containerConfig;

    // Create Ory client
    const oryClient = getOryClient(createOryClientConfig(config.ory));

    // Import service implementations (lazy to avoid circular deps)
    const { SessionService } = await import('../services/session-service');
    const { FlowService } = await import('../services/flow-service');
    const { UserService } = await import('../services/user-service');
    const { AuthFacade } = await import('../facade/auth-facade');

    // Create services using factories or defaults
    const sessionService =
      factories.sessionService?.(oryClient, config) ?? new SessionService(oryClient, config);

    const flowService =
      factories.flowService?.(oryClient, config) ?? new FlowService(oryClient, config);

    const userService =
      factories.userService?.(oryClient, config) ?? new UserService(oryClient, config);

    // Create facade
    const facade =
      factories.facade?.(sessionService, flowService, userService, config) ??
      new AuthFacade(sessionService, flowService, userService, config);

    // Initialize facade
    await facade.initialize();

    return {
      oryClient,
      sessionService,
      flowService,
      userService,
      facade,
      config,
    };
  };
}

// =============================================================================
// Factory Function
// =============================================================================

/**
 * Create an auth container instance
 *
 * @param containerConfig - Container configuration
 * @returns Auth container instance
 */
export const createAuthContainer = (containerConfig: AuthContainerConfig): AuthContainer =>
  new AuthContainer(containerConfig);
