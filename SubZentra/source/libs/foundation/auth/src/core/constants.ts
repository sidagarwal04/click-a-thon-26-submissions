/**
 * Authentication Constants
 *
 * Centralized constants for the foundation-auth library.
 *
 * @module core/constants
 */

// =============================================================================
// Auth Flow Types
// =============================================================================

/**
 * Types of authentication flows supported by Ory
 */
export const AUTH_FLOW_TYPE = {
  /** User login flow */
  LOGIN: 'login',
  /** User registration flow */
  REGISTRATION: 'registration',
  /** Password/account recovery flow */
  RECOVERY: 'recovery',
  /** Email/phone verification flow */
  VERIFICATION: 'verification',
  /** Account settings flow */
  SETTINGS: 'settings',
} as const;

export type AuthFlowType = (typeof AUTH_FLOW_TYPE)[keyof typeof AUTH_FLOW_TYPE];

// =============================================================================
// Auth States
// =============================================================================

/**
 * Possible authentication states
 */
export const AUTH_STATE = {
  /** Initial state while checking session */
  INITIALIZING: 'initializing',
  /** User is authenticated with a valid session */
  AUTHENTICATED: 'authenticated',
  /** User is not authenticated */
  UNAUTHENTICATED: 'unauthenticated',
  /** An error occurred during authentication */
  ERROR: 'error',
} as const;

export type AuthStateType = (typeof AUTH_STATE)[keyof typeof AUTH_STATE];

// =============================================================================
// Auth Error Codes
// =============================================================================

/**
 * Authentication-specific error codes
 */
export const AUTH_ERROR_CODE = {
  /** Auth provider not initialized */
  NOT_INITIALIZED: 'AUTH_NOT_INITIALIZED',
  /** Authentication required but not present (401-equivalent) */
  UNAUTHORIZED: 'AUTH_UNAUTHORIZED',
  /** Session check failed */
  SESSION_CHECK_FAILED: 'AUTH_SESSION_CHECK_FAILED',
  /** Session refresh failed */
  SESSION_REFRESH_FAILED: 'AUTH_SESSION_REFRESH_FAILED',
  /** Session has expired */
  SESSION_EXPIRED: 'AUTH_SESSION_EXPIRED',
  /** Logout operation failed */
  LOGOUT_FAILED: 'AUTH_LOGOUT_FAILED',
  /** Flow creation failed */
  FLOW_CREATION_FAILED: 'AUTH_FLOW_CREATION_FAILED',
  /** Flow not found */
  FLOW_NOT_FOUND: 'AUTH_FLOW_NOT_FOUND',
  /** Flow submission failed */
  FLOW_SUBMISSION_FAILED: 'AUTH_FLOW_SUBMISSION_FAILED',
  /** Flow has expired */
  FLOW_EXPIRED: 'AUTH_FLOW_EXPIRED',
  /** Invalid credentials */
  INVALID_CREDENTIALS: 'AUTH_INVALID_CREDENTIALS',
  /** User not found */
  USER_NOT_FOUND: 'AUTH_USER_NOT_FOUND',
  /** Permission denied */
  PERMISSION_DENIED: 'AUTH_PERMISSION_DENIED',
  /** Token retrieval failed */
  TOKEN_RETRIEVAL_FAILED: 'AUTH_TOKEN_RETRIEVAL_FAILED',
  /** Token has expired */
  TOKEN_EXPIRED: 'AUTH_TOKEN_EXPIRED',
  /** Ory client configuration error */
  CLIENT_CONFIG_ERROR: 'AUTH_CLIENT_CONFIG_ERROR',
  /** Network error during auth operation */
  NETWORK_ERROR: 'AUTH_NETWORK_ERROR',
} as const;

export type AuthErrorCode = (typeof AUTH_ERROR_CODE)[keyof typeof AUTH_ERROR_CODE];

// =============================================================================
// Default Configuration
// =============================================================================

/**
 * Default authentication configuration values
 */
export const DEFAULT_AUTH_CONFIG = {
  /** Session refresh interval in milliseconds (5 minutes) */
  SESSION_REFRESH_INTERVAL_MS: 300_000,
  /** Flow timeout in milliseconds (30 minutes) */
  FLOW_TIMEOUT_MS: 1_800_000,
  /** Token refresh buffer in milliseconds (1 minute before expiry) */
  TOKEN_REFRESH_BUFFER_MS: 60_000,
  /** Maximum retry attempts for session checks */
  MAX_SESSION_CHECK_RETRIES: 3,
  /** Retry delay for session checks in milliseconds */
  SESSION_CHECK_RETRY_DELAY_MS: 1_000,
} as const;

// =============================================================================
// Session States
// =============================================================================

/**
 * Session activity states
 */
export const SESSION_STATE = {
  /** Session is active and valid */
  ACTIVE: 'active',
  /** Session is refreshing */
  REFRESHING: 'refreshing',
  /** Session is stale (needs refresh) */
  STALE: 'stale',
  /** Session is expired */
  EXPIRED: 'expired',
  /** Session is invalid */
  INVALID: 'invalid',
} as const;

export type SessionStateType = (typeof SESSION_STATE)[keyof typeof SESSION_STATE];

// =============================================================================
// Flow States
// =============================================================================

/**
 * Auth flow states
 */
export const FLOW_STATE = {
  /** Flow is pending user action */
  PENDING: 'pending',
  /** Flow is being submitted */
  SUBMITTING: 'submitting',
  /** Flow completed successfully */
  COMPLETED: 'completed',
  /** Flow failed */
  FAILED: 'failed',
  /** Flow has expired */
  EXPIRED: 'expired',
} as const;

export type FlowStateType = (typeof FLOW_STATE)[keyof typeof FLOW_STATE];

// =============================================================================
// Identity Traits Keys
// =============================================================================

/**
 * Common Ory identity trait keys
 */
export const IDENTITY_TRAIT = {
  EMAIL: 'email',
  NAME: 'name',
  FIRST_NAME: 'first_name',
  LAST_NAME: 'last_name',
  PHONE: 'phone',
  AVATAR_URL: 'avatar_url',
  ROLE: 'role',
  TENANT_ID: 'tenant_id',
} as const;

export type IdentityTraitKey = (typeof IDENTITY_TRAIT)[keyof typeof IDENTITY_TRAIT];
