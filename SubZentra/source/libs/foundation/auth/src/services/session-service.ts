/**
 * Session Service
 *
 * Manages user sessions including checking, refreshing, and logout.
 *
 * @module services/session-service
 */

import type { Session } from '@ory/client-fetch';

import { ManagedInterval } from '@open-zentra/foundation-utils';

import { DEFAULT_AUTH_CONFIG, SESSION_STATE, type SessionStateType } from '../core/constants';
import type { OryClientInstance } from '../core/ory-client';
import type {
  AuthConfig,
  AuthSession,
  SessionServiceInterface,
  SessionStateChangeEvent,
  SessionStateListener,
} from '../core/types';
import {
  AuthNetworkError,
  LogoutError,
  SessionCheckError,
  SessionExpiredError,
  SessionRefreshError,
} from '../errors/auth-errors';

// =============================================================================
// Session Service
// =============================================================================

/**
 * Session service implementation
 *
 * Handles session lifecycle:
 * - Session initialization and checking
 * - Session refresh (manual and automatic)
 * - Logout
 * - Access token retrieval (for authenticated API and WebSocket calls)
 * - State change notifications
 */
export class SessionService implements SessionServiceInterface {
  private readonly oryClient: OryClientInstance;
  private readonly config: AuthConfig;
  private readonly listeners = new Set<SessionStateListener>();

  private session: AuthSession | null = null;
  private refreshInterval: ManagedInterval | null = null;
  private disposed = false;

  constructor(oryClient: OryClientInstance, config: AuthConfig) {
    this.oryClient = oryClient;
    this.config = config;
  }

  /**
   * Initialize and check current session
   */
  initialize = async (): Promise<AuthSession | null> => {
    this.ensureNotDisposed();

    try {
      const authSession = await this.checkSession();

      // Start auto-refresh if enabled and session exists
      if (authSession && this.config.autoRefreshSession !== false) {
        this.startAutoRefresh();
      }

      return authSession;
    } catch (error) {
      // Session check failure during init is not fatal - user may not be logged in
      if (error instanceof SessionCheckError) {
        return null;
      }
      throw error;
    }
  };

  /**
   * Check if session is valid
   */
  checkSession = async (): Promise<AuthSession | null> => {
    this.ensureNotDisposed();

    const previousState = this.session?.state ?? SESSION_STATE.INVALID;

    try {
      const response = await this.oryClient.frontend.toSession();

      if (!response.active) {
        this.updateSession(null, SESSION_STATE.INVALID, previousState);
        return null;
      }

      const authSession = this.createAuthSession(response, SESSION_STATE.ACTIVE);
      this.updateSession(authSession, SESSION_STATE.ACTIVE, previousState);
      return authSession;
    } catch (error) {
      // 401/403 means no valid session
      if (this.isUnauthorizedError(error)) {
        this.updateSession(null, SESSION_STATE.INVALID, previousState);
        return null;
      }

      // Network error
      if (this.isNetworkError(error)) {
        throw new AuthNetworkError('checkSession', error as Error);
      }

      throw new SessionCheckError(
        error instanceof Error ? error.message : 'Unknown error',
        error instanceof Error ? error : undefined,
      );
    }
  };

  /**
   * Refresh the current session
   */
  refresh = async (): Promise<AuthSession | null> => {
    this.ensureNotDisposed();

    const previousState = this.session?.state ?? SESSION_STATE.INVALID;

    // Notify listeners that refresh is in progress
    this.updateSession(
      this.session ? { ...this.session, state: SESSION_STATE.REFRESHING } : null,
      SESSION_STATE.REFRESHING,
      previousState,
    );

    try {
      // Ory uses cookie-based sessions, so we just need to call toSession
      // to verify and potentially extend the session
      const response = await this.oryClient.frontend.toSession();

      if (!response.active) {
        this.updateSession(null, SESSION_STATE.EXPIRED, SESSION_STATE.REFRESHING);
        throw new SessionExpiredError();
      }

      const authSession = this.createAuthSession(response, SESSION_STATE.ACTIVE);
      this.updateSession(authSession, SESSION_STATE.ACTIVE, SESSION_STATE.REFRESHING);
      return authSession;
    } catch (error) {
      if (error instanceof SessionExpiredError) {
        throw error;
      }

      // Unauthorized during refresh means session expired
      if (this.isUnauthorizedError(error)) {
        this.updateSession(null, SESSION_STATE.EXPIRED, SESSION_STATE.REFRESHING);
        throw new SessionExpiredError(undefined, error as Error);
      }

      // Network error during refresh
      if (this.isNetworkError(error)) {
        // Keep current session state on network error
        this.updateSession(
          this.session ? { ...this.session, state: SESSION_STATE.STALE } : null,
          SESSION_STATE.STALE,
          SESSION_STATE.REFRESHING,
        );
        throw new AuthNetworkError('refresh', error as Error);
      }

      throw new SessionRefreshError(
        error instanceof Error ? error.message : 'Unknown error',
        error instanceof Error ? error : undefined,
      );
    }
  };

  /**
   * Terminate the current session
   */
  logout = async (returnTo?: string): Promise<void> => {
    this.ensureNotDisposed();

    const previousState = this.session?.state ?? SESSION_STATE.INVALID;

    try {
      // Stop auto-refresh
      this.stopAutoRefresh();

      // Create a browser logout flow
      const logoutFlow = await this.oryClient.frontend.createBrowserLogoutFlow();

      // Execute the logout
      if (logoutFlow.logout_url) {
        // If we have a logout URL, redirect to it
        // In a SPA, we might want to handle this differently
        if (typeof window !== 'undefined' && logoutFlow.logout_url) {
          const url = new URL(logoutFlow.logout_url);
          if (returnTo) {
            url.searchParams.set('return_to', returnTo);
          }
          window.location.href = url.toString();
          return;
        }
      }

      // Fallback: use the logout token directly
      if (logoutFlow.logout_token) {
        await this.oryClient.frontend.updateLogoutFlow({
          token: logoutFlow.logout_token,
          returnTo,
        });
      }

      // Clear session state
      this.updateSession(null, SESSION_STATE.INVALID, previousState);
    } catch (error) {
      // Even if logout fails, clear local session state
      this.updateSession(null, SESSION_STATE.INVALID, previousState);

      throw new LogoutError(
        error instanceof Error ? error.message : 'Unknown error',
        error instanceof Error ? error : undefined,
      );
    }
  };

  /**
   * Get access token for API calls.
   *
   * **Important:** Ory Kratos uses cookie-based sessions by default, so
   * there is no standalone access token to retrieve — the session cookie
   * is sent automatically with every request. This method intentionally
   * returns `null` when running with cookie-based auth.
   *
   * If you later integrate Ory Hydra (OIDC), implement token exchange here.
   *
   * @returns `null` for cookie-based auth (session cookie is sent automatically)
   */
  getAccessToken = async (): Promise<string | null> => {
    this.ensureNotDisposed();

    // Cookie-based auth: no standalone access token exists.
    // The browser sends the session cookie automatically.
    console.debug(
      '[SessionService] getAccessToken called — returning null (cookie-based auth). ' +
        'If you need an access token, integrate Ory Hydra for OIDC token exchange.',
    );
    return null;
  };

  /**
   * Get current session state
   */
  getState = (): AuthSession | null => this.session;

  /**
   * Subscribe to session state changes
   */
  subscribe = (listener: SessionStateListener): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  /**
   * Dispose resources
   */
  dispose = async (): Promise<void> => {
    if (this.disposed) return;

    this.disposed = true;
    this.stopAutoRefresh();
    this.listeners.clear();
    this.session = null;
  };

  // ==========================================================================
  // Private Methods
  // ==========================================================================

  /**
   * Ensure service is not disposed
   */
  private ensureNotDisposed = (): void => {
    if (this.disposed) {
      throw new Error('[SessionService] Service has been disposed');
    }
  };

  /**
   * Create AuthSession from Ory Session
   */
  private createAuthSession = (session: Session, state: SessionStateType): AuthSession => ({
    session,
    state,
    expiresAt: session.expires_at ? new Date(session.expires_at).getTime() : null,
    lastRefreshedAt: Date.now(),
    isAuthenticated: session.active === true,
  });

  /**
   * Update session and notify listeners
   */
  private updateSession = (
    session: AuthSession | null,
    newState: SessionStateType,
    previousState: SessionStateType,
  ): void => {
    this.session = session;

    // Notify listeners
    const event: SessionStateChangeEvent = {
      previousState,
      newState,
      session: session?.session ?? null,
      timestamp: Date.now(),
    };

    this.listeners.forEach((listener) => {
      try {
        listener(event);
      } catch (error) {
        console.error('[SessionService] Listener error:', error);
      }
    });
  };

  /**
   * Start automatic session refresh
   */
  private startAutoRefresh = (): void => {
    const intervalValue =
      this.config.sessionRefreshIntervalMs ?? DEFAULT_AUTH_CONFIG.SESSION_REFRESH_INTERVAL_MS;

    this.refreshInterval = new ManagedInterval({
      callback: async () => {
        try {
          await this.refresh();
        } catch (error) {
          console.warn('[SessionService] Auto-refresh failed:', error);
        }
      },
      interval: intervalValue,
      immediate: false,
      autoStart: true,
    });
  };

  /**
   * Stop automatic session refresh
   */
  private stopAutoRefresh = (): void => {
    this.refreshInterval?.stop();
    this.refreshInterval = null;
  };

  /**
   * Check if error is an unauthorized error
   */
  private isUnauthorizedError = (error: unknown): boolean => {
    if (error && typeof error === 'object' && 'status' in error) {
      const status = (error as { status: number }).status;
      return status === 401 || status === 403;
    }
    return false;
  };

  /**
   * Check if error is a network error
   */
  private isNetworkError = (error: unknown): boolean => {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      return true;
    }
    if (error && typeof error === 'object' && 'name' in error) {
      return (error as { name: string }).name === 'NetworkError';
    }
    return false;
  };
}
