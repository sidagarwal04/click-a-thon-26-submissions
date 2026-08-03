/**
 * Auth Provider
 *
 * Main authentication provider component.
 *
 * @module providers/auth-provider
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { AUTH_STATE, SESSION_STATE, type AuthStateType } from '../core/constants';
import { AuthContainer, type AuthContainerDependencies } from '../core/container';
import type {
  AuthConfig,
  AuthContextValue,
  AuthInternals,
  AuthProviderProps,
  AuthState,
  AuthUser,
  SessionStateChangeEvent,
  UserPermissions,
  UserRole,
} from '../core/types';
import { AuthContext } from './auth-context';
import { AuthInternalsContext } from './auth-internals-context';

// =============================================================================
// Auth Provider
// =============================================================================

/**
 * Auth provider component
 *
 * Provides authentication context to the application.
 *
 * @example
 * ```tsx
 * <AuthProvider
 *   config={{
 *     ory: { kratosUrl: 'https://your-project.ory.cloud' },
 *   }}
 *   loadingComponent={<LoadingSpinner />}
 *   errorComponent={(error) => <ErrorMessage error={error} />}
 * >
 *   <App />
 * </AuthProvider>
 * ```
 */
export const AuthProvider = ({
  config,
  children,
  loadingComponent = null,
  errorComponent = null,
  onAuthStateChange,
}: AuthProviderProps): ReactNode => {
  // State
  const [deps, setDeps] = useState<AuthContainerDependencies | null>(null);
  const [authState, setAuthState] = useState<AuthState>({
    state: AUTH_STATE.INITIALIZING,
    isInitializing: true,
    isLoading: true,
    isAuthenticated: false,
    session: null,
    user: null,
    error: null,
  });

  // Refs
  const containerRef = useRef<AuthContainer | null>(null);
  const sessionUnsubscribeRef = useRef<(() => void) | null>(null);
  const configRef = useRef<AuthConfig>(config);
  const onAuthStateChangeRef = useRef(onAuthStateChange);
  const authStateRef = useRef<AuthState>(authState);

  // Keep callback inputs current without mutating refs during render.
  useEffect(() => {
    configRef.current = config;
    onAuthStateChangeRef.current = onAuthStateChange;
    authStateRef.current = authState;
  }, [authState, config, onAuthStateChange]);

  // ==========================================================================
  // Session State Handler (stable ref pattern to avoid dependency loop)
  // ==========================================================================

  const handleSessionStateChange = useCallback(
    (event: SessionStateChangeEvent) => {
      const { newState, session } = event;
      const currentDeps = containerRef.current?.isInitialized
        ? containerRef.current.getDependencies()
        : null;

      if (!currentDeps) return;

      // Read previous state from ref to avoid stale closure over authState
      const previousAuthState = authStateRef.current;
      let nextAuthState: AuthState;

      switch (newState) {
        case SESSION_STATE.ACTIVE:
          if (session && session.identity) {
            const user = currentDeps.facade.mapIdentityToUser(session.identity);
            nextAuthState = {
              state: AUTH_STATE.AUTHENTICATED,
              isInitializing: false,
              isLoading: false,
              isAuthenticated: true,
              session: {
                session,
                state: newState,
                expiresAt: session.expires_at ? new Date(session.expires_at).getTime() : null,
                lastRefreshedAt: Date.now(),
                isAuthenticated: true,
              },
              user,
              error: null,
            };
          } else {
            nextAuthState = {
              state: AUTH_STATE.UNAUTHENTICATED,
              isInitializing: false,
              isLoading: false,
              isAuthenticated: false,
              session: null,
              user: null,
              error: null,
            };
          }
          break;

        case SESSION_STATE.REFRESHING:
          nextAuthState = {
            ...previousAuthState,
            isLoading: true,
          };
          break;

        case SESSION_STATE.EXPIRED:
        case SESSION_STATE.INVALID:
          nextAuthState = {
            state: AUTH_STATE.UNAUTHENTICATED,
            isInitializing: false,
            isLoading: false,
            isAuthenticated: false,
            session: null,
            user: null,
            error: null,
          };
          break;

        case SESSION_STATE.STALE:
          nextAuthState = {
            ...previousAuthState,
            session: previousAuthState.session
              ? { ...previousAuthState.session, state: newState }
              : null,
          };
          break;

        default:
          return;
      }

      setAuthState(nextAuthState);

      // Notify callback
      if (onAuthStateChangeRef.current) {
        onAuthStateChangeRef.current(nextAuthState);
      }
    },
    [], // Stable: reads all mutable state from refs
  );

  // ==========================================================================
  // Initialization
  // ==========================================================================

  useEffect(() => {
    let mounted = true;

    const initializeAuth = async () => {
      try {
        // Create container
        const container = new AuthContainer({ config: configRef.current });
        containerRef.current = container;

        // Initialize
        const dependencies = await container.initialize();

        if (!mounted || container.isDisposed) return;

        // Subscribe to session state changes
        const unsubscribe = dependencies.sessionService.subscribe(handleSessionStateChange);
        sessionUnsubscribeRef.current = unsubscribe;

        // Get initial session state
        const currentSession = dependencies.sessionService.getState();
        let initialUser: AuthUser | null = null;
        let initialState: AuthStateType = AUTH_STATE.UNAUTHENTICATED;

        if (currentSession?.isAuthenticated && currentSession.session.identity) {
          initialUser = dependencies.facade.mapIdentityToUser(currentSession.session.identity);
          initialState = AUTH_STATE.AUTHENTICATED;
        }

        if (!mounted || container.isDisposed) return;

        // Update state
        setDeps(dependencies);
        setAuthState({
          state: initialState,
          isInitializing: false,
          isLoading: false,
          isAuthenticated: initialState === AUTH_STATE.AUTHENTICATED,
          session: currentSession,
          user: initialUser,
          error: null,
        });
      } catch (error) {
        if (!mounted) return;

        console.error('[AuthProvider] Initialization failed:', error);

        setAuthState({
          state: AUTH_STATE.ERROR,
          isInitializing: false,
          isLoading: false,
          isAuthenticated: false,
          session: null,
          user: null,
          error: error instanceof Error ? error : new Error('Initialization failed'),
        });
      }
    };

    initializeAuth();

    // Cleanup
    return () => {
      mounted = false;

      // Unsubscribe from session changes
      sessionUnsubscribeRef.current?.();
      sessionUnsubscribeRef.current = null;

      // Dispose container
      containerRef.current?.dispose().catch(console.error);
      containerRef.current = null;
    };
  }, [config.ory.kratosUrl, handleSessionStateChange]); // handleSessionStateChange is stable (empty deps)

  // ==========================================================================
  // Actions
  // ==========================================================================

  const login = useCallback(
    async (returnTo?: string) => {
      if (!deps) return;

      try {
        const flow = await deps.flowService.createLoginFlow(returnTo);

        // In a SPA, we'd typically show a form. Here we redirect to Ory UI.
        // This can be customized based on the app's needs.
        if (flow.request_url) {
          window.location.href = flow.request_url;
        }
      } catch (error) {
        console.error('[AuthProvider] Login flow creation failed:', error);
        throw error;
      }
    },
    [deps],
  );

  const register = useCallback(
    async (returnTo?: string) => {
      if (!deps) return;

      try {
        const flow = await deps.flowService.createRegistrationFlow(returnTo);

        if (flow.request_url) {
          window.location.href = flow.request_url;
        }
      } catch (error) {
        console.error('[AuthProvider] Registration flow creation failed:', error);
        throw error;
      }
    },
    [deps],
  );

  const logout = useCallback(
    async (returnTo?: string) => {
      if (!deps) return;

      try {
        await deps.sessionService.logout(returnTo);
      } catch (error) {
        console.error('[AuthProvider] Logout failed:', error);
        throw error;
      }
    },
    [deps],
  );

  const recoverPassword = useCallback(
    async (email: string) => {
      if (!deps) return;

      try {
        const flow = await deps.flowService.createRecoveryFlow();
        await deps.flowService.submitRecoveryFlow(flow.id, { email });
      } catch (error) {
        console.error('[AuthProvider] Password recovery failed:', error);
        throw error;
      }
    },
    [deps],
  );

  // ==========================================================================
  // Permission Checks
  // ==========================================================================

  const hasPermission = useCallback(
    (permission: keyof UserPermissions): boolean => {
      if (!authState.user) return false;
      return authState.user.permissions[permission] === true;
    },
    [authState.user],
  );

  const hasRole = useCallback(
    (role: UserRole | UserRole[]): boolean => {
      if (!authState.user) return false;
      const roles = Array.isArray(role) ? role : [role];
      return roles.includes(authState.user.role);
    },
    [authState.user],
  );

  const hasAnyRole = useCallback(
    (roles: UserRole[]): boolean => {
      if (!authState.user) return false;
      return roles.includes(authState.user.role);
    },
    [authState.user],
  );

  // ==========================================================================
  // Internals Actions
  // ==========================================================================

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!deps) return null;
    return deps.sessionService.getAccessToken();
  }, [deps]);

  const reauthenticate = useCallback(async () => {
    if (!deps) return;
    await deps.sessionService.checkSession();
  }, [deps]);

  // ==========================================================================
  // Context Values
  // ==========================================================================

  const publicContextValue = useMemo<AuthContextValue>(
    () => ({
      isInitializing: authState.isInitializing,
      isLoading: authState.isLoading,
      isAuthenticated: authState.isAuthenticated,
      user: authState.user,
      error: authState.error,
      login,
      register,
      logout,
      recoverPassword,
      hasPermission,
      hasRole,
      hasAnyRole,
    }),
    [
      authState.isInitializing,
      authState.isLoading,
      authState.isAuthenticated,
      authState.user,
      authState.error,
      login,
      register,
      logout,
      recoverPassword,
      hasPermission,
      hasRole,
      hasAnyRole,
    ],
  );

  const internalsContextValue = useMemo<AuthInternals>(
    () => ({
      facade: deps?.facade ?? null,
      getAccessToken,
      reauthenticate,
      state: authState,
      config,
    }),
    [deps?.facade, getAccessToken, reauthenticate, authState, config],
  );

  // ==========================================================================
  // Render
  // ==========================================================================

  // Show loading component during initialization
  if (authState.isInitializing && loadingComponent) {
    return loadingComponent;
  }

  // Show error component on initialization error
  if (authState.state === AUTH_STATE.ERROR && authState.error && errorComponent) {
    const errorContent =
      typeof errorComponent === 'function' ? errorComponent(authState.error) : errorComponent;
    return errorContent;
  }

  return (
    <AuthContext.Provider value={publicContextValue}>
      <AuthInternalsContext.Provider value={internalsContextValue}>
        {children}
      </AuthInternalsContext.Provider>
    </AuthContext.Provider>
  );
};
