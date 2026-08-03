/**
 * Core Module
 *
 * Core functionality for the foundation-auth library.
 *
 * @module core
 */

// =============================================================================
// Constants
// =============================================================================

export {
  // Auth flow types
  AUTH_FLOW_TYPE,
  type AuthFlowType,
  // Auth states
  AUTH_STATE,
  type AuthStateType,
  // Auth error codes
  AUTH_ERROR_CODE,
  type AuthErrorCode,
  // Default configuration
  DEFAULT_AUTH_CONFIG,
  // Session states
  SESSION_STATE,
  type SessionStateType,
  // Flow states
  FLOW_STATE,
  type FlowStateType,
  // Identity traits
  IDENTITY_TRAIT,
  type IdentityTraitKey,
} from './constants';

// =============================================================================
// Types
// =============================================================================

// User role and permissions (defined locally, compatible with data-model)
export type { UserRole, UserPermissions } from './types';
export { USER_ROLES, isValidRole, getUserPermissions } from './types';

export type {
  // Configuration
  OryConfig,
  AuthConfig,
  // Session
  AuthSession,
  SessionStateChangeEvent,
  SessionStateListener,
  // Identity
  IdentityTraits,
  TypedIdentity,
  VerifiableAddress,
  RecoveryAddress,
  // User
  AuthUser,
  // Auth state
  AuthState,
  AuthStateChangeEvent,
  AuthStateListener,
  // Flows
  OryFlow,
  FlowState,
  LoginFlowState,
  RegistrationFlowState,
  RecoveryFlowState,
  VerificationFlowState,
  SettingsFlowState,
  // Flow submissions
  LoginSubmission,
  RegistrationSubmission,
  RecoverySubmission,
  VerificationSubmission,
  SettingsSubmission,
  // Context
  AuthContextValue,
  AuthInternals,
  // Service interfaces
  SessionServiceInterface,
  FlowServiceInterface,
  UserServiceInterface,
  AuthFacadeInterface,
  // Provider props
  AuthProviderProps,
  // Hook return types
  UseAuthResult,
  UseAuthUserResult,
  UseRequiredAuthUserResult,
  UseAuthSessionResult,
  UseAuthFlowOptions,
  UseAuthFlowResult,
} from './types';

// =============================================================================
// Ory Client
// =============================================================================

export {
  getOryClient,
  resetOryClient,
  hasOryClient,
  createOryClientConfig,
  type OryClientConfig,
  type OryClientInstance,
} from './ory-client';

// =============================================================================
// Container
// =============================================================================

export {
  AuthContainer,
  createAuthContainer,
  type AuthContainerDependencies,
  type AuthDependencyFactories,
  type AuthContainerConfig,
} from './container';
