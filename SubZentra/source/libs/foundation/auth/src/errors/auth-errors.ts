/**
 * Authentication Error Classes
 *
 * Custom error classes for authentication operations.
 * All errors extend FoundationError from data-model.
 *
 * @module errors/auth-errors
 */

import {
  FOUNDATION_ERROR_CODE,
  FoundationError,
  type ErrorContext,
} from '@open-zentra/foundation-data-model';

import { AUTH_ERROR_CODE, type AuthErrorCode } from '../core/constants';

// =============================================================================
// Base Auth Error
// =============================================================================

/**
 * Base class for authentication errors
 *
 * Extends FoundationError to integrate with the foundation error infrastructure.
 */
export abstract class AuthError extends FoundationError {
  /**
   * Auth-specific error code
   */
  abstract readonly authCode: AuthErrorCode;

  /**
   * All auth errors use the INTERNAL_ERROR code from FoundationErrorCode
   * but have their own authCode for more specific identification
   */
  readonly code = FOUNDATION_ERROR_CODE.INTERNAL_ERROR;

  constructor(message: string, context: ErrorContext = {}, cause?: Error) {
    super(message, { ...context, domain: 'auth' }, cause);
  }
}

// =============================================================================
// Initialization Errors
// =============================================================================

/**
 * Error thrown when auth provider is not initialized
 */
export class AuthNotInitializedError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.NOT_INITIALIZED;

  constructor(operation?: string, cause?: Error) {
    super(
      `Auth provider not initialized${operation ? `. Cannot perform: ${operation}` : ''}`,
      { operation },
      cause,
    );
  }
}

// =============================================================================
// Session Errors
// =============================================================================

/**
 * Error thrown when session check fails
 */
export class SessionCheckError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.SESSION_CHECK_FAILED;

  constructor(reason?: string, cause?: Error) {
    super(`Session check failed${reason ? `: ${reason}` : ''}`, { reason }, cause);
  }
}

/**
 * Error thrown when session refresh fails
 */
export class SessionRefreshError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.SESSION_REFRESH_FAILED;

  constructor(reason?: string, cause?: Error) {
    super(`Session refresh failed${reason ? `: ${reason}` : ''}`, { reason }, cause);
  }
}

/**
 * Error thrown when session has expired
 */
export class SessionExpiredError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.SESSION_EXPIRED;

  constructor(expiredAt?: number, cause?: Error) {
    super('Session has expired', { expiredAt }, cause);
  }
}

/**
 * Error thrown when logout fails
 */
export class LogoutError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.LOGOUT_FAILED;

  constructor(reason?: string, cause?: Error) {
    super(`Logout failed${reason ? `: ${reason}` : ''}`, { reason }, cause);
  }
}

// =============================================================================
// Flow Errors
// =============================================================================

/**
 * Error thrown when flow creation fails
 */
export class FlowCreationError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.FLOW_CREATION_FAILED;

  constructor(flowType: string, reason?: string, cause?: Error) {
    super(
      `Failed to create ${flowType} flow${reason ? `: ${reason}` : ''}`,
      { flowType, reason },
      cause,
    );
  }
}

/**
 * Error thrown when flow is not found
 */
export class FlowNotFoundError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.FLOW_NOT_FOUND;

  constructor(flowId: string, flowType?: string, cause?: Error) {
    super(
      `Flow not found: ${flowId}${flowType ? ` (${flowType})` : ''}`,
      { flowId, flowType },
      cause,
    );
  }
}

/**
 * Error thrown when flow submission fails
 */
export class FlowSubmissionError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.FLOW_SUBMISSION_FAILED;

  constructor(flowType: string, reason?: string, cause?: Error) {
    super(
      `Failed to submit ${flowType} flow${reason ? `: ${reason}` : ''}`,
      { flowType, reason },
      cause,
    );
  }
}

/**
 * Error thrown when flow has expired
 */
export class FlowExpiredError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.FLOW_EXPIRED;

  constructor(flowId: string, flowType?: string, expiredAt?: number, cause?: Error) {
    super(`Flow has expired: ${flowId}`, { flowId, flowType, expiredAt }, cause);
  }
}

// =============================================================================
// Authentication Errors
// =============================================================================

/**
 * Error thrown when credentials are invalid
 */
export class InvalidCredentialsError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.INVALID_CREDENTIALS;

  constructor(cause?: Error) {
    super('Invalid credentials', {}, cause);
  }
}

/**
 * Error thrown when user is not found
 */
export class UserNotFoundError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.USER_NOT_FOUND;

  constructor(identifier?: string, cause?: Error) {
    super(`User not found${identifier ? `: ${identifier}` : ''}`, { identifier }, cause);
  }
}

// =============================================================================
// Authorization Errors
// =============================================================================

/**
 * Error thrown when permission is denied
 */
export class PermissionDeniedError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.PERMISSION_DENIED;

  constructor(permission?: string, requiredRole?: string, context?: ErrorContext, cause?: Error) {
    super(
      `Permission denied${permission ? `: ${permission}` : ''}${
        requiredRole ? ` (requires: ${requiredRole})` : ''
      }`,
      { ...context, permission, requiredRole },
      cause,
    );
  }
}

// =============================================================================
// Token Errors
// =============================================================================

/**
 * Error thrown when token retrieval fails
 */
export class TokenRetrievalError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.TOKEN_RETRIEVAL_FAILED;

  constructor(reason?: string, cause?: Error) {
    super(`Failed to retrieve access token${reason ? `: ${reason}` : ''}`, { reason }, cause);
  }
}

/**
 * Error thrown when token has expired
 */
export class TokenExpiredError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.TOKEN_EXPIRED;

  constructor(expiredAt?: number, cause?: Error) {
    super('Access token has expired', { expiredAt }, cause);
  }
}

// =============================================================================
// Configuration Errors
// =============================================================================

/**
 * Error thrown when client configuration is invalid
 */
export class ClientConfigError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.CLIENT_CONFIG_ERROR;

  constructor(reason: string, cause?: Error) {
    super(`Auth client configuration error: ${reason}`, { reason }, cause);
  }
}

// =============================================================================
// Network Errors
// =============================================================================

/**
 * Error thrown when a network error occurs during auth operation
 */
export class AuthNetworkError extends AuthError {
  readonly authCode = AUTH_ERROR_CODE.NETWORK_ERROR;

  constructor(operation?: string, cause?: Error) {
    super(
      `Network error during authentication${operation ? ` (${operation})` : ''}`,
      { operation },
      cause,
    );
  }
}

// =============================================================================
// Type Guards
// =============================================================================

/**
 * Check if an error is an AuthError
 */
export const isAuthError = (error: unknown): error is AuthError => error instanceof AuthError;

/**
 * Check if an error has a specific auth error code
 */
export const hasAuthErrorCode = (error: unknown, code: AuthErrorCode): error is AuthError =>
  isAuthError(error) && error.authCode === code;

/**
 * Session error codes
 */
const SESSION_ERROR_CODES: AuthErrorCode[] = [
  AUTH_ERROR_CODE.SESSION_CHECK_FAILED,
  AUTH_ERROR_CODE.SESSION_REFRESH_FAILED,
  AUTH_ERROR_CODE.SESSION_EXPIRED,
];

/**
 * Flow error codes
 */
const FLOW_ERROR_CODES: AuthErrorCode[] = [
  AUTH_ERROR_CODE.FLOW_CREATION_FAILED,
  AUTH_ERROR_CODE.FLOW_NOT_FOUND,
  AUTH_ERROR_CODE.FLOW_SUBMISSION_FAILED,
  AUTH_ERROR_CODE.FLOW_EXPIRED,
];

/**
 * Token error codes
 */
const TOKEN_ERROR_CODES: AuthErrorCode[] = [
  AUTH_ERROR_CODE.TOKEN_RETRIEVAL_FAILED,
  AUTH_ERROR_CODE.TOKEN_EXPIRED,
];

/**
 * Retryable error codes
 */
const RETRYABLE_ERROR_CODES: AuthErrorCode[] = [
  AUTH_ERROR_CODE.NETWORK_ERROR,
  AUTH_ERROR_CODE.SESSION_CHECK_FAILED,
  AUTH_ERROR_CODE.SESSION_REFRESH_FAILED,
];

/**
 * Check if error is a session-related error
 */
export const isSessionError = (error: unknown): error is AuthError =>
  isAuthError(error) && SESSION_ERROR_CODES.includes(error.authCode);

/**
 * Check if error is a flow-related error
 */
export const isFlowError = (error: unknown): error is AuthError =>
  isAuthError(error) && FLOW_ERROR_CODES.includes(error.authCode);

/**
 * Check if error is a token-related error
 */
export const isTokenError = (error: unknown): error is AuthError =>
  isAuthError(error) && TOKEN_ERROR_CODES.includes(error.authCode);

/**
 * Check if error is retryable
 */
export const isRetryableAuthError = (error: unknown): boolean =>
  isAuthError(error) && RETRYABLE_ERROR_CODES.includes(error.authCode);
