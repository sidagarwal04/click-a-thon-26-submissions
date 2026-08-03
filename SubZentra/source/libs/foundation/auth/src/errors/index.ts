/**
 * Errors Module
 *
 * Authentication error classes and type guards.
 *
 * @module errors
 */

export {
  // Base class
  AuthError,
  // Initialization errors
  AuthNotInitializedError,
  // Session errors
  SessionCheckError,
  SessionRefreshError,
  SessionExpiredError,
  LogoutError,
  // Flow errors
  FlowCreationError,
  FlowNotFoundError,
  FlowSubmissionError,
  FlowExpiredError,
  // Authentication errors
  InvalidCredentialsError,
  UserNotFoundError,
  // Authorization errors
  PermissionDeniedError,
  // Token errors
  TokenRetrievalError,
  TokenExpiredError,
  // Configuration errors
  ClientConfigError,
  // Network errors
  AuthNetworkError,
  // Type guards
  isAuthError,
  hasAuthErrorCode,
  isSessionError,
  isFlowError,
  isTokenError,
  isRetryableAuthError,
} from './auth-errors';
