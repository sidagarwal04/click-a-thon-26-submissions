/**
 * Instance Manager
 *
 * Singleton manager for named axios instances with full lifecycle
 * control including interceptor cleanup on removal.
 *
 * @module instance/instance-manager
 */

import type { AxiosInstance } from 'axios';

import { createConfigSignature } from '../core/config-signature';
import type { AuthConfig, HttpClientConfig, ResolvedHttpConfig } from '../core/types';
import { HttpConfigError, HttpNotInitializedError } from '../errors/http-errors';
import { removeInterceptors, setupInterceptors, type InterceptorIds } from '../interceptors/setup';
import { createConfiguredAxiosInstance } from './axios-factory';

// =============================================================================
// Types
// =============================================================================

interface ManagedInstance {
  readonly instance: AxiosInstance;
  readonly config: ResolvedHttpConfig;
  readonly signature: string;
  readonly interceptorIds: InterceptorIds;
  readonly getAccessToken: NonNullable<AuthConfig['getAccessToken']>;
}

// =============================================================================
// Instance Manager
// =============================================================================

/**
 * Manages named axios instances as singletons.
 *
 * Each instance is identified by a string key (defaults to its baseUrl).
 * The first instance created becomes the default unless overridden.
 * Removing or clearing instances properly ejects all registered interceptors
 * to prevent memory leaks.
 */
class HttpInstanceManager {
  private readonly instances = new Map<string, ManagedInstance>();
  private defaultKey: string | null = null;

  /**
   * Creates a new managed instance or returns an existing one for the given key.
   */
  createInstance(
    config: HttpClientConfig,
    key?: string,
    options?: {
      readonly getAccessToken?: AuthConfig['getAccessToken'];
      readonly authTransport?: AuthConfig['transport'];
      readonly setAsDefault?: boolean;
    },
  ): ManagedInstance {
    const instanceKey = key ?? config.baseUrl;
    const signature = createConfigSignature({
      config,
      getAccessToken: options?.getAccessToken,
      authTransport: options?.authTransport,
    });

    const existing = this.instances.get(instanceKey);
    if (existing) {
      if (existing.signature !== signature) {
        throw new HttpConfigError(
          `Instance "${instanceKey}" already exists with a different configuration`,
        );
      }
      return existing;
    }

    if (!config.baseUrl) {
      throw new HttpConfigError('baseUrl is required');
    }

    const { instance, resolvedConfig, getAccessToken } = createConfiguredAxiosInstance(config, {
      getAccessToken: options?.getAccessToken,
    });

    const interceptorIds = setupInterceptors(instance, resolvedConfig, {
      getAccessToken,
      authTransport: options?.authTransport,
      clientHeaders: config.clientHeaders,
    });

    const managed: ManagedInstance = {
      instance,
      config: resolvedConfig,
      signature,
      interceptorIds,
      getAccessToken,
    };

    this.instances.set(instanceKey, managed);

    if (options?.setAsDefault || this.defaultKey === null) {
      this.defaultKey = instanceKey;
    }

    return managed;
  }

  getInstance = (key: string): ManagedInstance | undefined => this.instances.get(key);

  getDefaultInstance(): ManagedInstance {
    if (this.defaultKey === null) {
      throw new HttpNotInitializedError('getDefaultInstance');
    }

    const instance = this.instances.get(this.defaultKey);
    if (!instance) {
      throw new HttpNotInitializedError('getDefaultInstance');
    }

    return instance;
  }

  hasInstance = (key: string): boolean => this.instances.has(key);

  hasDefaultInstance = (): boolean =>
    this.defaultKey !== null && this.instances.has(this.defaultKey);

  /**
   * Removes and cleans up an instance, ejecting its interceptors.
   */
  removeInstance(key: string): boolean {
    const managed = this.instances.get(key);
    if (managed) {
      removeInterceptors(managed.instance, managed.interceptorIds);
    }

    const removed = this.instances.delete(key);

    if (key === this.defaultKey) {
      this.defaultKey = null;

      const firstKey = this.instances.keys().next().value;
      if (typeof firstKey === 'string') {
        this.defaultKey = firstKey;
      }
    }

    return removed;
  }

  setDefaultInstance(key: string): void {
    if (!this.instances.has(key)) {
      throw new HttpNotInitializedError(`setDefaultInstance: ${key}`);
    }
    this.defaultKey = key;
  }

  getInstanceKeys = (): string[] => Array.from(this.instances.keys());

  /**
   * Removes all managed instances, ejecting every interceptor.
   */
  clear(): void {
    for (const managed of this.instances.values()) {
      removeInterceptors(managed.instance, managed.interceptorIds);
    }
    this.instances.clear();
    this.defaultKey = null;
  }

  get size(): number {
    return this.instances.size;
  }
}

// =============================================================================
// Singleton Export
// =============================================================================

/** Global HTTP instance manager singleton */
export const httpInstanceManager = new HttpInstanceManager();

/** Shorthand: get the default axios instance. Throws if uninitialised. */
export const getDefaultAxiosInstance = (): AxiosInstance =>
  httpInstanceManager.getDefaultInstance().instance;

/** Shorthand: get an axios instance by key. Returns undefined if not found. */
export const getAxiosInstance = (key: string): AxiosInstance | undefined =>
  httpInstanceManager.getInstance(key)?.instance;
