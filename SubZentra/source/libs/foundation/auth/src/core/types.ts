/**
 * Authentication Types
 *
 * Core type definitions for the foundation-auth library.
 *
 * @module core/types
 */

import type {
  Identity,
  LoginFlow,
  RecoveryFlow,
  RegistrationFlow,
  Session,
  SettingsFlow,
  VerificationFlow,
} from '@ory/client-fetch';

import type { AuthFlowType, AuthStateType, FlowStateType, SessionStateType } from './constants';

// =============================================================================
// User Role and Permission Types (compatible with data-model)
// =============================================================================

/**
 * Single source-of-truth for user roles.
 *
 * All role-related types, validation, and permission lookups derive from
 * this constant so that adding a new role is a single-line change.
 */
export const USER_ROLES = {
  OWNER: 'owner',
  ADMIN: 'admin',
  MEMBER: 'member',
  VIEWER: 'viewer',
  GUEST: 'guest',
} as const;

/**
 * User role type (derived from USER_ROLES constant)
 */
export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];

/**
 * Check if a string is a valid UserRole
 */
export const isValidRole = (role: string): role is UserRole =>
  (Object.values(USER_ROLES) as readonly string[]).includes(role);

/**
 * User permissions map (compatible with foundation-data-model UserPermissions)
 */
export interface UserPermissions {
  canManageUsers: boolean;
  canManageTenant: boolean;
  canViewAnalytics: boolean;
  canExportData: boolean;
  canConfigureIntegrations: boolean;
}

/**
 * Role → permissions lookup table.
 * Derived from USER_ROLES to guarantee exhaustive coverage.
 */
const ROLE_PERMISSIONS: Readonly<Record<UserRole, UserPermissions>> = {
  [USER_ROLES.OWNER]: {
    canManageUsers: true,
    canManageTenant: true,
    canViewAnalytics: true,
    canExportData: true,
    canConfigureIntegrations: true,
  },
  [USER_ROLES.ADMIN]: {
    canManageUsers: true,
    canManageTenant: false,
    canViewAnalytics: true,
    canExportData: true,
    canConfigureIntegrations: true,
  },
  [USER_ROLES.MEMBER]: {
    canManageUsers: false,
    canManageTenant: false,
    canViewAnalytics: true,
    canExportData: true,
    canConfigureIntegrations: false,
  },
  [USER_ROLES.VIEWER]: {
    canManageUsers: false,
    canManageTenant: false,
    canViewAnalytics: true,
    canExportData: false,
    canConfigureIntegrations: false,
  },
  [USER_ROLES.GUEST]: {
    canManageUsers: false,
    canManageTenant: false,
    canViewAnalytics: false,
    canExportData: false,
    canConfigureIntegrations: false,
  },
};

/**
 * Get permissions for a user role
 */
export const getUserPermissions = (role: UserRole): UserPermissions => ROLE_PERMISSIONS[role];

// =============================================================================
// Configuration Types
// =============================================================================

/**
 * Ory Kratos/Hydra configuration
 */
export interface OryConfig {
  /** Ory Kratos public URL (for browser flows) */
  kratosUrl: string;
  /** Ory Hydra public URL (optional, for OAuth2/OIDC) */
  hydraUrl?: string;
  /** Custom Ory project slug (for Ory Network) */
  projectSlug?: string;
}

/**
 * Combined authentication configuration
 */
export interface AuthConfig {
  /** Ory configuration */
  ory: OryConfig;
  /** Session refresh interval in milliseconds */
  sessionRefreshIntervalMs?: number;
  /** Enable automatic session refresh */
  autoRefreshSession?: boolean;
  /** Enable debug logging */
  debug?: boolean;
}

// =============================================================================
// Session Types
// =============================================================================

/**
 * Authentication session state
 */
export interface AuthSession {
  /** Ory session object */
  session: Session;
  /** Session state */
  state: SessionStateType;
  /** Session expiry timestamp */
  expiresAt: number | null;
  /** Last refresh timestamp */
  lastRefreshedAt: number;
  /** Whether the session is authenticated */
  isAuthenticated: boolean;
}

/**
 * Session state change event
 */
export interface SessionStateChangeEvent {
  /** Previous session state */
  previousState: SessionStateType;
  /** New session state */
  newState: SessionStateType;
  /** Session data (if available) */
  session: Session | null;
  /** Timestamp of the change */
  timestamp: number;
}

/**
 * Session state listener
 */
export type SessionStateListener = (event: SessionStateChangeEvent) => void;

// =============================================================================
// Identity Types
// =============================================================================

/**
 * Ory identity traits (type-safe wrapper)
 */
export interface IdentityTraits {
  email?: string;
  name?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  avatar_url?: string;
  role?: UserRole;
  tenant_id?: string;
  [key: string]: unknown;
}

/**
 * Verifiable address with string dates
 */
export interface VerifiableAddress {
  id?: string;
  value: string;
  verified: boolean;
  via: string;
  status: string;
  verified_at?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Recovery address with string dates
 */
export interface RecoveryAddress {
  id?: string;
  value: string;
  via: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Extended identity with typed traits (uses string dates for consistency)
 */
export interface TypedIdentity {
  id: string;
  schema_id?: string;
  schema_url?: string;
  state?: string;
  state_changed_at?: string;
  traits: IdentityTraits;
  verifiable_addresses?: VerifiableAddress[];
  recovery_addresses?: RecoveryAddress[];
  metadata_public?: Record<string, unknown>;
  metadata_admin?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

// =============================================================================
// User Types
// =============================================================================

/**
 * Authenticated user derived from Ory identity
 */
export interface AuthUser {
  /** User's unique identifier (Ory identity ID) */
  id: string;
  /** User's email address */
  email: string;
  /** User's display name */
  name: string | null;
  /** User's first name */
  firstName: string | null;
  /** User's last name */
  lastName: string | null;
  /** User's avatar URL */
  avatarUrl: string | null;
  /** User's role */
  role: UserRole;
  /** User's tenant ID */
  tenantId: string | null;
  /** User's permissions derived from role */
  permissions: UserPermissions;
  /** Whether email is verified */
  emailVerified: boolean;
  /** Raw Ory identity object */
  identity: TypedIdentity;
}

// =============================================================================
// Auth State Types
// =============================================================================

/**
 * Overall authentication state
 */
export interface AuthState {
  /** Current auth state type */
  state: AuthStateType;
  /** Whether authentication is being initialized */
  isInitializing: boolean;
  /** Whether a session check is in progress */
  isLoading: boolean;
  /** Whether user is authenticated */
  isAuthenticated: boolean;
  /** Current session (if authenticated) */
  session: AuthSession | null;
  /** Current user (if authenticated) */
  user: AuthUser | null;
  /** Error (if any) */
  error: Error | null;
}

/**
 * Auth state change event
 */
export interface AuthStateChangeEvent {
  /** Previous auth state */
  previousState: AuthState;
  /** New auth state */
  newState: AuthState;
  /** Timestamp of the change */
  timestamp: number;
}

/**
 * Auth state listener
 */
export type AuthStateListener = (event: AuthStateChangeEvent) => void;

// =============================================================================
// Flow Types
// =============================================================================

/**
 * Union type for all Ory flow types
 */
export type OryFlow = LoginFlow | RegistrationFlow | RecoveryFlow | VerificationFlow | SettingsFlow;

/**
 * Flow state wrapper
 */
export interface FlowState<T extends OryFlow = OryFlow> {
  /** Flow type */
  type: AuthFlowType;
  /** Flow data */
  flow: T | null;
  /** Flow state */
  state: FlowStateType;
  /** Flow error (if any) */
  error: Error | null;
  /** Flow ID */
  flowId: string | null;
  /** Flow expiry timestamp */
  expiresAt: number | null;
}

/**
 * Login flow state
 */
export type LoginFlowState = FlowState<LoginFlow>;

/**
 * Registration flow state
 */
export type RegistrationFlowState = FlowState<RegistrationFlow>;

/**
 * Recovery flow state
 */
export type RecoveryFlowState = FlowState<RecoveryFlow>;

/**
 * Verification flow state
 */
export type VerificationFlowState = FlowState<VerificationFlow>;

/**
 * Settings flow state
 */
export type SettingsFlowState = FlowState<SettingsFlow>;

// =============================================================================
// Flow Submission Types
// =============================================================================

/**
 * Login flow submission data
 */
export interface LoginSubmission {
  /** Identifier (email, username, etc.) */
  identifier: string;
  /** Password */
  password: string;
  /** CSRF token (auto-populated) */
  csrf_token?: string;
  /** Remember me option */
  remember?: boolean;
}

/**
 * Registration flow submission data
 */
export interface RegistrationSubmission {
  /** Email address */
  email: string;
  /** Password */
  password: string;
  /** Name (optional) */
  name?: string;
  /** First name (optional) */
  first_name?: string;
  /** Last name (optional) */
  last_name?: string;
  /** CSRF token (auto-populated) */
  csrf_token?: string;
  /** Additional traits */
  [key: string]: unknown;
}

/**
 * Recovery flow submission data
 */
export interface RecoverySubmission {
  /** Email address */
  email: string;
  /** CSRF token (auto-populated) */
  csrf_token?: string;
}

/**
 * Verification flow submission data
 */
export interface VerificationSubmission {
  /** Email address */
  email: string;
  /** Verification code (optional, for code flow) */
  code?: string;
  /** CSRF token (auto-populated) */
  csrf_token?: string;
}

/**
 * Settings flow submission data
 */
export interface SettingsSubmission {
  /** Password change */
  password?: string;
  /** Profile traits update */
  traits?: Partial<IdentityTraits>;
  /** CSRF token (auto-populated) */
  csrf_token?: string;
}

// =============================================================================
// Context Types
// =============================================================================

/**
 * Public auth context value (for app components)
 */
export interface AuthContextValue {
  // State
  /** Whether auth is initializing */
  isInitializing: boolean;
  /** Whether a session operation is in progress */
  isLoading: boolean;
  /** Whether user is authenticated */
  isAuthenticated: boolean;
  /** Current authenticated user */
  user: AuthUser | null;
  /** Auth error (if any) */
  error: Error | null;

  // Actions
  /** Initiate login flow */
  login: (returnTo?: string) => Promise<void>;
  /** Initiate registration flow */
  register: (returnTo?: string) => Promise<void>;
  /** Logout current user */
  logout: (returnTo?: string) => Promise<void>;
  /** Initiate password recovery */
  recoverPassword: (email: string) => Promise<void>;

  // Permission checks
  /** Check if user has a specific permission */
  hasPermission: (permission: keyof UserPermissions) => boolean;
  /** Check if user has a specific role */
  hasRole: (role: UserRole | UserRole[]) => boolean;
  /** Check if user has any of the specified roles */
  hasAnyRole: (roles: UserRole[]) => boolean;
}

/**
 * Internal auth context value (for internal hooks)
 */
export interface AuthInternals {
  /** Auth facade instance */
  facade: AuthFacadeInterface | null;
  /** Get access token for API calls */
  getAccessToken: () => Promise<string | null>;
  /** Force re-authentication */
  reauthenticate: () => Promise<void>;
  /** Current auth state */
  state: AuthState;
  /** Auth configuration */
  config: AuthConfig;
}

// =============================================================================
// Service Interfaces
// =============================================================================

/**
 * Session service interface
 */
export interface SessionServiceInterface {
  /** Initialize and check current session */
  initialize: () => Promise<AuthSession | null>;
  /** Check if session is valid */
  checkSession: () => Promise<AuthSession | null>;
  /** Refresh the current session */
  refresh: () => Promise<AuthSession | null>;
  /** Terminate the current session */
  logout: (returnTo?: string) => Promise<void>;
  /** Get access token for API calls */
  getAccessToken: () => Promise<string | null>;
  /** Get current session state */
  getState: () => AuthSession | null;
  /** Subscribe to session state changes */
  subscribe: (listener: SessionStateListener) => () => void;
  /** Dispose resources */
  dispose: () => Promise<void>;
}

/**
 * Flow service interface
 */
export interface FlowServiceInterface {
  // Login
  createLoginFlow: (returnTo?: string) => Promise<LoginFlow>;
  getLoginFlow: (flowId: string) => Promise<LoginFlow>;
  submitLoginFlow: (flowId: string, data: LoginSubmission) => Promise<void>;

  // Registration
  createRegistrationFlow: (returnTo?: string) => Promise<RegistrationFlow>;
  getRegistrationFlow: (flowId: string) => Promise<RegistrationFlow>;
  submitRegistrationFlow: (flowId: string, data: RegistrationSubmission) => Promise<void>;

  // Recovery
  createRecoveryFlow: (returnTo?: string) => Promise<RecoveryFlow>;
  getRecoveryFlow: (flowId: string) => Promise<RecoveryFlow>;
  submitRecoveryFlow: (flowId: string, data: RecoverySubmission) => Promise<void>;

  // Verification
  createVerificationFlow: (returnTo?: string) => Promise<VerificationFlow>;
  getVerificationFlow: (flowId: string) => Promise<VerificationFlow>;
  submitVerificationFlow: (flowId: string, data: VerificationSubmission) => Promise<void>;

  // Settings
  createSettingsFlow: (returnTo?: string) => Promise<SettingsFlow>;
  getSettingsFlow: (flowId: string) => Promise<SettingsFlow>;
  submitSettingsFlow: (flowId: string, data: SettingsSubmission) => Promise<void>;

  /** Dispose resources */
  dispose: () => Promise<void>;
}

/**
 * User service interface
 */
export interface UserServiceInterface {
  /** Get current user's identity */
  getCurrentIdentity: () => Promise<TypedIdentity | null>;
  /** Update user traits */
  updateTraits: (traits: Partial<IdentityTraits>) => Promise<TypedIdentity>;
  /** Dispose resources */
  dispose: () => Promise<void>;
}

/**
 * Auth facade interface
 */
export interface AuthFacadeInterface {
  /** Session service */
  readonly session: SessionServiceInterface;
  /** Flow service */
  readonly flow: FlowServiceInterface;
  /** User service */
  readonly user: UserServiceInterface;
  /** Map Ory identity to AuthUser */
  mapIdentityToUser: (identity: Identity) => AuthUser;
  /** Initialize facade */
  initialize: () => Promise<void>;
  /** Dispose facade */
  dispose: () => Promise<void>;
}

// =============================================================================
// Provider Props
// =============================================================================

/**
 * AuthProvider component props
 */
export interface AuthProviderProps {
  /** Auth configuration */
  config: AuthConfig;
  /** Child components */
  children: React.ReactNode;
  /** Loading component to show during initialization */
  loadingComponent?: React.ReactNode;
  /** Error component to show on initialization error */
  errorComponent?: React.ReactNode | ((error: Error) => React.ReactNode);
  /** Callback when auth state changes */
  onAuthStateChange?: (state: AuthState) => void;
}

// =============================================================================
// Hook Return Types
// =============================================================================

/**
 * useAuth hook return type
 */
export interface UseAuthResult extends AuthContextValue {
  /** Raw auth state */
  state: AuthStateType;
}

/**
 * useAuthUser hook return type
 */
export interface UseAuthUserResult {
  /** Current user (null if not authenticated) */
  user: AuthUser | null;
  /** Whether auth is loading */
  isLoading: boolean;
  /** Whether user is authenticated */
  isAuthenticated: boolean;
}

/**
 * useRequiredAuthUser hook return type
 */
export interface UseRequiredAuthUserResult {
  /** Current user (throws if not authenticated) */
  user: AuthUser;
  /** Whether auth is loading */
  isLoading: boolean;
}

/**
 * useAuthSession hook return type
 */
export interface UseAuthSessionResult {
  /** Current session */
  session: AuthSession | null;
  /** Whether session is loading */
  isLoading: boolean;
  /** Session state */
  sessionState: SessionStateType | null;
  /** Get access token */
  getAccessToken: () => Promise<string | null>;
  /** Refresh session */
  refresh: () => Promise<void>;
}

/**
 * useAuthFlow hook options
 */
export interface UseAuthFlowOptions<T extends AuthFlowType> {
  /** Flow type */
  type: T;
  /** Auto-create flow on mount */
  autoCreate?: boolean;
  /** Return URL after flow completion */
  returnTo?: string;
}

/**
 * useAuthFlow hook return type
 */
export interface UseAuthFlowResult<T extends OryFlow> {
  /** Flow state */
  flowState: FlowState<T>;
  /** Create a new flow */
  createFlow: () => Promise<void>;
  /** Submit the flow */
  submitFlow: (data: unknown) => Promise<void>;
  /** Reset flow state */
  resetFlow: () => void;
  /** Whether flow is loading */
  isLoading: boolean;
  /** Whether flow is submitting */
  isSubmitting: boolean;
}
