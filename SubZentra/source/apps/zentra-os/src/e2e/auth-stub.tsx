/**
 * The identity provider, replaced at build time for browser journeys.
 *
 * Aliased over `@open-zentra/foundation-auth` only when Vite runs in `e2e`
 * mode, so nothing here reaches a production bundle. That is why this is a
 * build-time alias rather than a third auth provider inside the library: a
 * provider would ship, and an auth bypass that ships is an auth bypass
 * somebody eventually reaches.
 *
 * It stubs exactly one thing — the browser's belief that a session exists —
 * and nothing beyond it. The token it hands out is a real RS256 token minted
 * by `tools/e2e/prepare.py`, which the API verifies against a real JWKS before
 * resolving a real Tenant under real RLS. Everything from the Authorization
 * header inward is the production path.
 *
 * The role is read from a cookie rather than baked in, so one build serves
 * every role and a journey changes only that.
 */

import { useCallback, useMemo, type ReactNode } from 'react';

const ROLE_COOKIE = 'zentra_e2e_role';
const TOKEN_COOKIE = 'zentra_e2e_token';

const cookie = (name: string): string | null => {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : null;
};

export interface AuthUser {
  readonly id: string;
  readonly email: string;
}

export interface AuthTenant {
  readonly id: string;
  readonly name: string;
}

export const useAuth = () => {
  const role = cookie(ROLE_COOKIE) ?? 'owner';
  const hasToken = Boolean(cookie(TOKEN_COOKIE));

  return useMemo(
    () => ({
      // Never "still initializing": a spinner that never resolves would make
      // every journey time out somewhere unhelpful.
      isInitializing: false,
      // Driven by the token cookie so a journey can assert the signed-out
      // screen by simply not setting one.
      isAuthenticated: hasToken,
      login: () => undefined,
      // Read by the authz boundary. The server is the authority on what a role
      // may do — `can_decide` and friends come back on the API response — so an
      // empty scope here cannot grant anything the API would refuse.
      scope: undefined,
      logout: () => undefined,
      user: hasToken
        ? ({ id: `user_e2e_${role}`, email: `${role}@e2e.zentraos.test` } as AuthUser)
        : null,
      // The id is only used to gate a query; the API decides the real Tenant
      // from the token, and this value is never sent anywhere.
      tenant: hasToken
        ? ({ id: 'e2e', name: 'Forensic Observatory E2E' } as AuthTenant)
        : null,
    }),
    [hasToken, role],
  );
};

/**
 * The provider chain, collapsed.
 *
 * `providers.tsx` wraps the app in ClerkProvider → ClerkAuthProvider →
 * ClerkAuthzProvider. None of them can run without a Clerk session, and none
 * of them decides anything the journeys assert: authorization is enforced by
 * the API against the token, not by these wrappers. So in `e2e` mode they
 * become pass-throughs, and every specifier that would have pulled Clerk in is
 * aliased to this file.
 */
const passThrough = ({ children }: { readonly children?: ReactNode }) => <>{children}</>;

export const ClerkProvider = passThrough;
export const ClerkAuthProvider = passThrough;
export const ClerkAuthzProvider = passThrough;

export const useAuthSession = () => {
  const getAccessToken = useCallback(async () => cookie(TOKEN_COOKIE), []);
  return useMemo(() => ({ getAccessToken }), [getAccessToken]);
};
