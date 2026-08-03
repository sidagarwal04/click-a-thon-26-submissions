import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { useAuth as useClerkAuth } from '@clerk/clerk-react';

import {
  AUTHZ_ROLE_ACTION,
  createAuthzDecision,
  createDeniedAuthzDecision,
  createInitializingAuthzSnapshot,
  createReadyAuthzSnapshot,
  createUnauthorizedAuthzSnapshot,
  type AuthzCheck,
  type AuthzDecision,
  type AuthzScope,
} from '../../core';
import { AuthzProvider, type AuthzProviderProps } from '../../runtime/react';
import {
  createManagedAuthzAdapter,
  type ManagedAuthzProviderAdapter,
} from '../shared/managed-authz-adapter';
import {
  resolveClerkPermissionKey,
  resolveClerkRoleKey,
  type ClerkAuthzMappingOptions,
  type ClerkAuthzPermissionMapping,
  type ClerkAuthzPermissionTemplate,
} from './clerk-authz-mapping';

type ClerkAuth = ReturnType<typeof useClerkAuth>;
type ClerkHas = Exclude<ClerkAuth['has'], undefined>;

export interface ClerkAuthzAdapterOptions extends ClerkAuthzMappingOptions {
  readonly provider?: string;
  readonly requireTenant?: boolean;
  readonly debugMetadata?: boolean;
}

export interface ClerkAuthzProviderProps extends Omit<AuthzProviderProps, 'adapter' | 'children'> {
  readonly children: ReactNode;
  readonly adapter?: ManagedAuthzProviderAdapter;
  readonly options?: ClerkAuthzAdapterOptions;
}

export type { ClerkAuthzPermissionMapping, ClerkAuthzPermissionTemplate };

const CLERK_AUTHZ_PROVIDER = 'clerk';
const DEFAULT_CLERK_AUTHZ_OPTIONS: ClerkAuthzAdapterOptions = {};

const hasRequiredTenant = (
  auth: ClerkAuth,
  scope: AuthzScope | null,
  options: ClerkAuthzAdapterOptions,
): boolean => {
  if (options.requireTenant === false) {
    return true;
  }

  return Boolean(auth.orgId && scope?.tenantId);
};

const hasScopeMismatch = (auth: ClerkAuth, scope: AuthzScope | null): boolean => {
  if (!scope) {
    return true;
  }

  if (scope.subjectId && auth.userId && scope.subjectId !== auth.userId) {
    return true;
  }

  if (scope.sessionId && auth.sessionId && scope.sessionId !== auth.sessionId) {
    return true;
  }

  return Boolean(scope.tenantId && auth.orgId && scope.tenantId !== auth.orgId);
};

const createDenied = ({
  auth,
  check,
  options,
  reason,
  scope,
  permissionKey,
  roleKey,
}: {
  readonly auth: ClerkAuth;
  readonly check: AuthzCheck;
  readonly options: ClerkAuthzAdapterOptions;
  readonly reason: string;
  readonly scope: AuthzScope | null;
  readonly permissionKey?: string;
  readonly roleKey?: string;
}): AuthzDecision =>
  createDeniedAuthzDecision({
    source: options.provider ?? CLERK_AUTHZ_PROVIDER,
    reason: !auth.isLoaded ? 'clerk_loading' : reason,
    scope,
    ...(options.debugMetadata && permissionKey ? { permissionKey } : {}),
    ...(options.debugMetadata && roleKey ? { roleKey } : {}),
    ...(options.debugMetadata && check.action === AUTHZ_ROLE_ACTION && !roleKey
      ? { roleKey: check.resource }
      : {}),
  });

const checkWithClerk = ({
  auth,
  check,
  options,
  scope,
}: {
  readonly auth: ClerkAuth;
  readonly check: AuthzCheck;
  readonly options: ClerkAuthzAdapterOptions;
  readonly scope: AuthzScope | null;
}): AuthzDecision => {
  if (!auth.isLoaded) {
    return createDenied({ auth, check, options, reason: 'clerk_loading', scope });
  }

  if (!auth.isSignedIn || !auth.userId) {
    return createDenied({ auth, check, options, reason: 'signed_out', scope });
  }

  if (!hasRequiredTenant(auth, scope, options)) {
    return createDenied({ auth, check, options, reason: 'tenant_required', scope });
  }

  if (hasScopeMismatch(auth, scope)) {
    return createDenied({ auth, check, options, reason: 'scope_mismatch', scope });
  }

  if (!auth.has) {
    return createDenied({ auth, check, options, reason: 'clerk_has_unavailable', scope });
  }

  if (check.action === AUTHZ_ROLE_ACTION) {
    const roleKey = resolveClerkRoleKey(check.resource, options);
    const allowed = auth.has({ role: roleKey } as Parameters<ClerkHas>[0]);

    return createAuthzDecision({
      allowed,
      source: options.provider ?? CLERK_AUTHZ_PROVIDER,
      reason: allowed ? null : 'role_denied',
      scope,
      ...(options.debugMetadata ? { roleKey } : {}),
    });
  }

  const permissionKey = resolveClerkPermissionKey(check, options);

  if (!permissionKey) {
    return createDenied({ auth, check, options, reason: 'mapping_not_found', scope });
  }

  const allowed = auth.has({ permission: permissionKey } as Parameters<ClerkHas>[0]);

  return createAuthzDecision({
    allowed,
    source: options.provider ?? CLERK_AUTHZ_PROVIDER,
    reason: allowed ? null : 'permission_denied',
    scope,
    ...(options.debugMetadata ? { permissionKey } : {}),
  });
};

export const createClerkAuthzAdapter = (
  options: ClerkAuthzAdapterOptions = {},
): ManagedAuthzProviderAdapter =>
  createManagedAuthzAdapter(
    options.provider ?? CLERK_AUTHZ_PROVIDER,
    createInitializingAuthzSnapshot(options.provider ?? CLERK_AUTHZ_PROVIDER),
  );

const ClerkAuthzBridge = ({
  adapter,
  options,
  scope,
}: {
  readonly adapter: ManagedAuthzProviderAdapter;
  readonly options: ClerkAuthzAdapterOptions;
  readonly scope: AuthzScope | null;
}): null => {
  const auth = useClerkAuth();
  const optionsRef = useRef(options);

  // Synced in a layout effect rather than during render: a ref written
  // mid-render is unsound under concurrent rendering. Nothing here reads
  // it during render, so the effect is equivalent.
  useLayoutEffect(() => {
    optionsRef.current = options;
  });


  const provider = options.provider ?? CLERK_AUTHZ_PROVIDER;

  const snapshot = useMemo(() => {
    if (!auth.isLoaded) {
      return createInitializingAuthzSnapshot(provider, scope);
    }

    if (
      !auth.isSignedIn ||
      !hasRequiredTenant(auth, scope, options) ||
      hasScopeMismatch(auth, scope)
    ) {
      return createUnauthorizedAuthzSnapshot(provider, scope);
    }

    return createReadyAuthzSnapshot(provider, scope);
  }, [
    auth.isLoaded,
    auth.isSignedIn,
    auth.orgId,
    auth.sessionId,
    auth.userId,
    options,
    provider,
    scope,
  ]);

  useEffect(() => {
    adapter.setSnapshot(snapshot);
  }, [adapter, snapshot]);

  useEffect(() => {
    adapter.setActions({
      check: (check) =>
        checkWithClerk({
          auth,
          check,
          options: optionsRef.current,
          scope: adapter.getSnapshot().scope,
        }),
      checkBatch: (checks) =>
        checks.map((check) =>
          checkWithClerk({
            auth,
            check,
            options: optionsRef.current,
            scope: adapter.getSnapshot().scope,
          }),
        ),
      refresh: async () => undefined,
    });
  }, [adapter, auth]);

  return null;
};

export const ClerkAuthzProvider = ({
  adapter,
  options = DEFAULT_CLERK_AUTHZ_OPTIONS,
  children,
  scope = null,
  loadingBehavior,
  onDecision,
  onError,
}: ClerkAuthzProviderProps): ReactNode => {
  const [managedAdapter] = useState(() => adapter ?? createClerkAuthzAdapter(options));

  return (
    <AuthzProvider
      adapter={managedAdapter}
      loadingBehavior={loadingBehavior}
      onDecision={onDecision}
      onError={onError}
      scope={scope}
    >
      <ClerkAuthzBridge adapter={managedAdapter} options={options} scope={scope} />
      {children}
    </AuthzProvider>
  );
};
