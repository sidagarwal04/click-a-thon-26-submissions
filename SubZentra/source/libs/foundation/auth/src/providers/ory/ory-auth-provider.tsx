import { useEffect, useMemo, useState, type ReactNode } from 'react';

import {
  AUTH_STATE,
  createAuthScope,
  createInitializingAuthState,
  createUnauthenticatedAuthState,
  type AuthState,
  type ResolvedAuthTransport,
} from '../../kernel';
import { AuthRuntimeProvider, type AuthRuntimeProviderProps } from '../../runtime/react';
import type { AuthProviderProps as LegacyAuthProviderProps } from '../../core/types';
import { useAuth as useLegacyAuth } from '../../hooks/use-auth';
import { useAuthSession as useLegacyAuthSession } from '../../hooks/use-auth-session';
import { AuthProvider as LegacyOryProvider } from '../auth-provider';
import {
  createManagedAuthAdapter,
  type ManagedAuthProviderAdapter,
} from '../shared/managed-auth-adapter';

export interface OryAuthProviderProps
  extends Omit<LegacyAuthProviderProps, 'children' | 'loadingComponent' | 'errorComponent'>,
    Omit<AuthRuntimeProviderProps, 'adapter' | 'children'> {
  readonly children: ReactNode;
  readonly adapter?: ManagedAuthProviderAdapter;
}

const ORY_PROVIDER = 'ory';

const anonymousTransport: ResolvedAuthTransport = { kind: 'anonymous' };

export const createOryAuthAdapter = (): ManagedAuthProviderAdapter =>
  createManagedAuthAdapter(ORY_PROVIDER, createInitializingAuthState(ORY_PROVIDER));

const createOryAuthState = (
  legacyAuth: ReturnType<typeof useLegacyAuth>,
  legacySession: ReturnType<typeof useLegacyAuthSession>,
): AuthState => {
  if (legacyAuth.isInitializing) {
    return createInitializingAuthState(ORY_PROVIDER);
  }

  if (legacyAuth.error) {
    return {
      ...createUnauthenticatedAuthState(ORY_PROVIDER),
      state: AUTH_STATE.ERROR,
      error: legacyAuth.error,
    };
  }

  if (!legacyAuth.isAuthenticated || !legacyAuth.user) {
    return createUnauthenticatedAuthState(ORY_PROVIDER);
  }

  const scope = createAuthScope({
    provider: ORY_PROVIDER,
    subjectId: legacyAuth.user.id,
    tenantId: legacyAuth.user.tenantId,
    sessionId: legacySession.session?.session.id ?? null,
  });

  const principal = {
    id: legacyAuth.user.id,
    email: legacyAuth.user.email,
    name: legacyAuth.user.name,
    firstName: legacyAuth.user.firstName,
    lastName: legacyAuth.user.lastName,
    avatarUrl: legacyAuth.user.avatarUrl,
    emailVerified: legacyAuth.user.emailVerified,
    tenantId: legacyAuth.user.tenantId,
    role: legacyAuth.user.role,
    permissions: legacyAuth.user.permissions,
    claims: legacyAuth.user.identity.metadata_public ?? {},
    provider: ORY_PROVIDER,
  };

  return {
    state: AUTH_STATE.AUTHENTICATED,
    isInitializing: false,
    isLoading: legacyAuth.isLoading,
    isAuthenticated: true,
    principal,
    user: principal,
    tenant: {
      id: legacyAuth.user.tenantId,
      slug: null,
      name: null,
      role: legacyAuth.user.role,
      permissions: legacyAuth.user.permissions,
    },
    session: {
      id: legacySession.session?.session.id ?? null,
      state: legacySession.sessionState === 'refreshing' ? 'revalidating' : 'active',
      expiresAt: legacySession.session?.expiresAt ?? null,
      lastRefreshedAt: legacySession.session?.lastRefreshedAt ?? null,
      isAuthenticated: true,
      tokenType: 'bearer',
    },
    scope,
    error: null,
  };
};

const OryAuthBridge = ({ adapter }: { readonly adapter: ManagedAuthProviderAdapter }): null => {
  const legacyAuth = useLegacyAuth();
  const legacySession = useLegacyAuthSession();

  const snapshot = useMemo(
    () => createOryAuthState(legacyAuth, legacySession),
    [legacyAuth, legacySession],
  );

  useEffect(() => {
    adapter.setSnapshot(snapshot);
  }, [adapter, snapshot]);

  useEffect(() => {
    adapter.setActions({
      login: async (intent) => {
        await legacyAuth.login(intent?.redirectTo);
      },
      register: async (intent) => {
        await legacyAuth.register(intent?.redirectTo);
      },
      logout: async (intent) => {
        await legacyAuth.logout(intent?.redirectTo);
      },
      refresh: legacySession.refresh,
      getAccessToken: legacySession.getAccessToken,
      getTransport: async () => {
        if (!legacyAuth.isAuthenticated) {
          return anonymousTransport;
        }

        const token = await legacySession.getAccessToken();
        return token ? { kind: 'bearer', token, scheme: 'Bearer' } : { kind: 'cookie', withCredentials: true };
      },
      invalidate: legacySession.refresh,
      setActiveTenant: async () => undefined,
    });
  }, [adapter, legacyAuth, legacySession]);

  return null;
};

export const OryAuthProvider = ({
  adapter,
  children,
  loadingComponent,
  errorComponent,
  ...legacyProps
}: OryAuthProviderProps): ReactNode => {
  const [managedAdapter] = useState(() => adapter ?? createOryAuthAdapter());

  return (
    <LegacyOryProvider
      {...legacyProps}
      loadingComponent={loadingComponent}
      errorComponent={errorComponent}
    >
      <AuthRuntimeProvider
        adapter={managedAdapter}
        loadingComponent={loadingComponent}
        errorComponent={errorComponent}
      >
        <OryAuthBridge adapter={managedAdapter} />
        {children}
      </AuthRuntimeProvider>
    </LegacyOryProvider>
  );
};
