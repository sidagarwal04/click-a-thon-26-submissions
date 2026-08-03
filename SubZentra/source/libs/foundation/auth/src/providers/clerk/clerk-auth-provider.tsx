import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { useAuth as useClerkAuth, useClerk, useOrganization, useSession, useUser } from '@clerk/clerk-react';

import {
  AUTH_STATE,
  USER_ROLES,
  createAuthScope,
  createInitializingAuthState,
  createUnauthenticatedAuthState,
  normalizeProviderRole,
  type AuthNavigationIntent,
  type AuthState,
  type AuthTransportAudience,
  type AuthTransportRequest,
  type ResolvedAuthTransport,
  type UserPermissions,
} from '../../kernel';
import { AuthRuntimeProvider, type AuthRuntimeProviderProps } from '../../runtime/react';
import {
  createManagedAuthAdapter,
  type ManagedAuthProviderAdapter,
} from '../shared/managed-auth-adapter';

type ClerkTransportMode = 'anonymous' | 'cookie' | 'bearer';

export interface ClerkAuthAdapterOptions {
  readonly provider?: string;
  readonly firstPartyTransport?: Exclude<ClerkTransportMode, 'anonymous'>;
  readonly defaultTransport?: Exclude<ClerkTransportMode, 'anonymous'>;
  readonly audienceTransport?: Partial<Record<AuthTransportAudience, ClerkTransportMode>>;
  readonly tokenTemplate?: string;
  readonly tokenTemplates?: Partial<Record<AuthTransportAudience, string>>;
}

export interface ClerkAuthProviderProps
  extends Omit<AuthRuntimeProviderProps, 'adapter' | 'children'> {
  readonly children: ReactNode;
  readonly adapter?: ManagedAuthProviderAdapter;
  readonly options?: ClerkAuthAdapterOptions;
}

const CLERK_PROVIDER = 'clerk';

const resolveRedirect = (intent?: AuthNavigationIntent): string | undefined => intent?.redirectTo;

const asRecord = (value: unknown): Readonly<Record<string, unknown>> =>
  value && typeof value === 'object' ? { ...(value as Record<string, unknown>) } : {};

const EMPTY_PERMISSIONS: UserPermissions = {
  canManageUsers: false,
  canManageTenant: false,
  canViewAnalytics: false,
  canExportData: false,
  canConfigureIntegrations: false,
};

const resolveTransportMode = (
  request: AuthTransportRequest | undefined,
  options: ClerkAuthAdapterOptions,
): ClerkTransportMode => {
  const audience = request?.audience;

  if (audience && options.audienceTransport?.[audience]) {
    return options.audienceTransport[audience];
  }

  if (audience === 'first_party_http') {
    return options.firstPartyTransport ?? 'cookie';
  }

  return options.defaultTransport ?? 'bearer';
};

const resolveTokenTemplate = (
  request: AuthTransportRequest | undefined,
  options: ClerkAuthAdapterOptions,
): string | undefined => {
  const audience = request?.audience;
  return (audience ? options.tokenTemplates?.[audience] : undefined) ?? options.tokenTemplate;
};

const createSignedOutTransport = (): ResolvedAuthTransport => ({ kind: 'anonymous' });

export const createClerkAuthAdapter = (
  options: ClerkAuthAdapterOptions = {},
): ManagedAuthProviderAdapter =>
  createManagedAuthAdapter(options.provider ?? CLERK_PROVIDER, createInitializingAuthState(options.provider ?? CLERK_PROVIDER));

const createClerkAuthState = ({
  auth,
  user,
  session,
  organization,
  isLoaded,
  options,
}: {
  readonly auth: ReturnType<typeof useClerkAuth>;
  readonly user: ReturnType<typeof useUser>['user'];
  readonly session: ReturnType<typeof useSession>['session'];
  readonly organization: ReturnType<typeof useOrganization>['organization'];
  readonly isLoaded: boolean;
  readonly options: ClerkAuthAdapterOptions;
}): AuthState => {
  const provider = options.provider ?? CLERK_PROVIDER;

  if (!isLoaded) {
    return createInitializingAuthState(provider);
  }

  if (!auth.isSignedIn || !auth.userId || !auth.sessionId || !user) {
    return createUnauthenticatedAuthState(provider);
  }

  const role = normalizeProviderRole(auth.orgRole, USER_ROLES.MEMBER);
  const claims = asRecord(auth.sessionClaims);
  const tenantId = auth.orgId ?? null;
  const primaryEmail = user.primaryEmailAddress?.emailAddress ?? user.emailAddresses[0]?.emailAddress ?? '';
  const scope = createAuthScope({
    provider,
    subjectId: auth.userId,
    tenantId,
    sessionId: auth.sessionId,
  });

  const principal = {
    id: auth.userId,
    email: primaryEmail,
    name: user.fullName,
    firstName: user.firstName,
    lastName: user.lastName,
    avatarUrl: user.imageUrl,
    emailVerified: user.hasVerifiedEmailAddress,
    tenantId,
    role,
    permissions: EMPTY_PERMISSIONS,
    claims,
    provider,
  };

  return {
    state: AUTH_STATE.AUTHENTICATED,
    isInitializing: false,
    isLoading: false,
    isAuthenticated: true,
    principal,
    user: principal,
    tenant: {
      id: tenantId,
      slug: auth.orgSlug ?? organization?.slug ?? null,
      name: organization?.name ?? null,
      role: tenantId ? role : null,
      permissions: null,
    },
    session: {
      id: auth.sessionId,
      state: 'active',
      expiresAt: session?.expireAt?.getTime() ?? null,
      lastRefreshedAt: Date.now(),
      isAuthenticated: true,
      tokenType: 'bearer',
    },
    scope,
    error: null,
  };
};

const ClerkAuthBridge = ({
  adapter,
  options,
}: {
  readonly adapter: ManagedAuthProviderAdapter;
  readonly options: ClerkAuthAdapterOptions;
}): null => {
  const auth = useClerkAuth();
  const clerk = useClerk();
  const userState = useUser();
  const sessionState = useSession();
  const organizationState = useOrganization();
  const optionsRef = useRef(options);

  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const snapshot = useMemo(
    () =>
      createClerkAuthState({
        auth,
        user: userState.user,
        session: sessionState.session,
        organization: organizationState.organization,
        isLoaded:
          auth.isLoaded &&
          userState.isLoaded &&
          sessionState.isLoaded &&
          organizationState.isLoaded,
        options,
      }),
    [
      auth,
      options,
      organizationState.isLoaded,
      organizationState.organization,
      sessionState.isLoaded,
      sessionState.session,
      userState.isLoaded,
      userState.user,
    ],
  );

  useEffect(() => {
    adapter.setSnapshot(snapshot);
  }, [adapter, snapshot]);

  useEffect(() => {
    const getBearerTransport = async (
      request?: AuthTransportRequest,
    ): Promise<ResolvedAuthTransport> => {
      const template = resolveTokenTemplate(request, optionsRef.current);
      const token = await auth.getToken(template ? { template } : undefined);

      return token ? { kind: 'bearer', token, scheme: 'Bearer' } : createSignedOutTransport();
    };

    adapter.setActions({
      login: async (intent) => {
        await clerk.redirectToSignIn({ redirectUrl: resolveRedirect(intent) });
      },
      register: async (intent) => {
        await clerk.redirectToSignUp({ redirectUrl: resolveRedirect(intent) });
      },
      logout: async (intent) => {
        await auth.signOut({ redirectUrl: resolveRedirect(intent) });
      },
      refresh: async () => {
        sessionState.session?.clearCache();
        await sessionState.session?.touch();
      },
      getAccessToken: async (request) => {
        const transport = await getBearerTransport(request);
        return transport.kind === 'bearer' ? transport.token : null;
      },
      getTransport: async (request) => {
        if (!auth.isLoaded || !auth.isSignedIn) {
          return createSignedOutTransport();
        }

        const mode = resolveTransportMode(request, optionsRef.current);

        if (mode === 'anonymous') {
          return createSignedOutTransport();
        }

        if (mode === 'cookie') {
          return { kind: 'cookie', withCredentials: true };
        }

        return getBearerTransport(request);
      },
      invalidate: async () => {
        sessionState.session?.clearCache();
      },
      setActiveTenant: async (tenantId) => {
        await clerk.setActive({ organization: tenantId });
      },
    });
  }, [adapter, auth, clerk, sessionState.session]);

  return null;
};

export const ClerkAuthProvider = ({
  adapter,
  options = {},
  children,
  loadingComponent,
  errorComponent,
}: ClerkAuthProviderProps): ReactNode => {
  const [managedAdapter] = useState(() => adapter ?? createClerkAuthAdapter(options));

  return (
    <AuthRuntimeProvider
      adapter={managedAdapter}
      loadingComponent={loadingComponent}
      errorComponent={errorComponent}
    >
      <ClerkAuthBridge adapter={managedAdapter} options={options} />
      {children}
    </AuthRuntimeProvider>
  );
};
