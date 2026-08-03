/**
 * Tests for auth-errors
 *
 * Custom error classes and type guards.
 */

import { describe, expect, it } from 'vitest';

import { AUTH_ERROR_CODE } from '../core/constants';
import {
  AuthNetworkError,
  AuthNotInitializedError,
  ClientConfigError,
  FlowCreationError,
  FlowExpiredError,
  FlowNotFoundError,
  FlowSubmissionError,
  hasAuthErrorCode,
  InvalidCredentialsError,
  isAuthError,
  isFlowError,
  isRetryableAuthError,
  isSessionError,
  isTokenError,
  LogoutError,
  PermissionDeniedError,
  SessionCheckError,
  SessionExpiredError,
  SessionRefreshError,
  TokenExpiredError,
  TokenRetrievalError,
  UserNotFoundError,
} from './auth-errors';

// =============================================================================
// Error Construction Tests
// =============================================================================

describe('auth-errors', () => {
  // ===========================================================================
  // AuthNotInitializedError
  // ===========================================================================

  describe('AuthNotInitializedError', () => {
    it('should create with default message', () => {
      const error = new AuthNotInitializedError();
      expect(error.message).toBe('Auth provider not initialized');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.NOT_INITIALIZED);
    });

    it('should include operation in message', () => {
      const error = new AuthNotInitializedError('logout');
      expect(error.message).toContain('logout');
    });

    it('should preserve cause', () => {
      const cause = new Error('underlying');
      const error = new AuthNotInitializedError('op', cause);
      expect(error.cause).toBe(cause);
    });
  });

  // ===========================================================================
  // Session Errors
  // ===========================================================================

  describe('SessionCheckError', () => {
    it('should create with reason', () => {
      const error = new SessionCheckError('network timeout');
      expect(error.message).toContain('network timeout');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.SESSION_CHECK_FAILED);
    });

    it('should create without reason', () => {
      const error = new SessionCheckError();
      expect(error.message).toBe('Session check failed');
    });
  });

  describe('SessionRefreshError', () => {
    it('should have correct auth code', () => {
      const error = new SessionRefreshError('token invalid');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.SESSION_REFRESH_FAILED);
      expect(error.message).toContain('token invalid');
    });
  });

  describe('SessionExpiredError', () => {
    it('should have correct auth code', () => {
      const error = new SessionExpiredError(Date.now());
      expect(error.authCode).toBe(AUTH_ERROR_CODE.SESSION_EXPIRED);
      expect(error.message).toBe('Session has expired');
    });
  });

  describe('LogoutError', () => {
    it('should include reason', () => {
      const error = new LogoutError('server error');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.LOGOUT_FAILED);
      expect(error.message).toContain('server error');
    });
  });

  // ===========================================================================
  // Flow Errors
  // ===========================================================================

  describe('FlowCreationError', () => {
    it('should include flow type', () => {
      const error = new FlowCreationError('login', 'server unavailable');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.FLOW_CREATION_FAILED);
      expect(error.message).toContain('login');
      expect(error.message).toContain('server unavailable');
    });
  });

  describe('FlowNotFoundError', () => {
    it('should include flow id and type', () => {
      const error = new FlowNotFoundError('flow-123', 'registration');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.FLOW_NOT_FOUND);
      expect(error.message).toContain('flow-123');
      expect(error.message).toContain('registration');
    });
  });

  describe('FlowSubmissionError', () => {
    it('should have correct auth code', () => {
      const error = new FlowSubmissionError('login', 'validation failed');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.FLOW_SUBMISSION_FAILED);
    });
  });

  describe('FlowExpiredError', () => {
    it('should include flow id', () => {
      const error = new FlowExpiredError('flow-456', 'recovery', Date.now());
      expect(error.authCode).toBe(AUTH_ERROR_CODE.FLOW_EXPIRED);
      expect(error.message).toContain('flow-456');
    });
  });

  // ===========================================================================
  // Auth Errors
  // ===========================================================================

  describe('InvalidCredentialsError', () => {
    it('should have correct auth code', () => {
      const error = new InvalidCredentialsError();
      expect(error.authCode).toBe(AUTH_ERROR_CODE.INVALID_CREDENTIALS);
      expect(error.message).toBe('Invalid credentials');
    });
  });

  describe('UserNotFoundError', () => {
    it('should include identifier', () => {
      const error = new UserNotFoundError('user@example.com');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.USER_NOT_FOUND);
      expect(error.message).toContain('user@example.com');
    });
  });

  // ===========================================================================
  // Authorization Errors
  // ===========================================================================

  describe('PermissionDeniedError', () => {
    it('should include permission and role', () => {
      const error = new PermissionDeniedError('canManageUsers', 'admin');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.PERMISSION_DENIED);
      expect(error.message).toContain('canManageUsers');
      expect(error.message).toContain('admin');
    });

    it('should work without optional params', () => {
      const error = new PermissionDeniedError();
      expect(error.message).toBe('Permission denied');
    });
  });

  // ===========================================================================
  // Token Errors
  // ===========================================================================

  describe('TokenRetrievalError', () => {
    it('should include reason', () => {
      const error = new TokenRetrievalError('no session');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.TOKEN_RETRIEVAL_FAILED);
      expect(error.message).toContain('no session');
    });
  });

  describe('TokenExpiredError', () => {
    it('should have correct auth code', () => {
      const error = new TokenExpiredError(Date.now());
      expect(error.authCode).toBe(AUTH_ERROR_CODE.TOKEN_EXPIRED);
    });
  });

  // ===========================================================================
  // Configuration & Network Errors
  // ===========================================================================

  describe('ClientConfigError', () => {
    it('should include reason', () => {
      const error = new ClientConfigError('missing kratosUrl');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.CLIENT_CONFIG_ERROR);
      expect(error.message).toContain('missing kratosUrl');
    });
  });

  describe('AuthNetworkError', () => {
    it('should include operation', () => {
      const error = new AuthNetworkError('session check');
      expect(error.authCode).toBe(AUTH_ERROR_CODE.NETWORK_ERROR);
      expect(error.message).toContain('session check');
    });
  });

  // ===========================================================================
  // Type Guards
  // ===========================================================================

  describe('isAuthError', () => {
    it('should return true for AuthError instances', () => {
      expect(isAuthError(new SessionCheckError())).toBe(true);
      expect(isAuthError(new FlowCreationError('login'))).toBe(true);
      expect(isAuthError(new TokenExpiredError())).toBe(true);
    });

    it('should return false for standard Error', () => {
      expect(isAuthError(new Error('test'))).toBe(false);
    });

    it('should return false for non-error values', () => {
      expect(isAuthError(null)).toBe(false);
      expect(isAuthError(undefined)).toBe(false);
      expect(isAuthError('error string')).toBe(false);
      expect(isAuthError(42)).toBe(false);
    });
  });

  describe('hasAuthErrorCode', () => {
    it('should match correct auth code', () => {
      const error = new SessionExpiredError();
      expect(hasAuthErrorCode(error, AUTH_ERROR_CODE.SESSION_EXPIRED)).toBe(true);
    });

    it('should not match incorrect auth code', () => {
      const error = new SessionExpiredError();
      expect(hasAuthErrorCode(error, AUTH_ERROR_CODE.FLOW_EXPIRED)).toBe(false);
    });

    it('should return false for non-AuthError', () => {
      expect(hasAuthErrorCode(new Error('test'), AUTH_ERROR_CODE.SESSION_EXPIRED)).toBe(false);
    });
  });

  describe('isSessionError', () => {
    it('should return true for session-related errors', () => {
      expect(isSessionError(new SessionCheckError())).toBe(true);
      expect(isSessionError(new SessionRefreshError())).toBe(true);
      expect(isSessionError(new SessionExpiredError())).toBe(true);
    });

    it('should return false for non-session errors', () => {
      expect(isSessionError(new FlowCreationError('login'))).toBe(false);
      expect(isSessionError(new TokenExpiredError())).toBe(false);
      expect(isSessionError(new Error('generic'))).toBe(false);
    });
  });

  describe('isFlowError', () => {
    it('should return true for flow-related errors', () => {
      expect(isFlowError(new FlowCreationError('login'))).toBe(true);
      expect(isFlowError(new FlowNotFoundError('id-1'))).toBe(true);
      expect(isFlowError(new FlowSubmissionError('login'))).toBe(true);
      expect(isFlowError(new FlowExpiredError('id-1'))).toBe(true);
    });

    it('should return false for non-flow errors', () => {
      expect(isFlowError(new SessionCheckError())).toBe(false);
      expect(isFlowError(new TokenExpiredError())).toBe(false);
    });
  });

  describe('isTokenError', () => {
    it('should return true for token-related errors', () => {
      expect(isTokenError(new TokenRetrievalError())).toBe(true);
      expect(isTokenError(new TokenExpiredError())).toBe(true);
    });

    it('should return false for non-token errors', () => {
      expect(isTokenError(new SessionExpiredError())).toBe(false);
      expect(isTokenError(new FlowCreationError('login'))).toBe(false);
    });
  });

  describe('isRetryableAuthError', () => {
    it('should return true for retryable errors', () => {
      expect(isRetryableAuthError(new AuthNetworkError())).toBe(true);
      expect(isRetryableAuthError(new SessionCheckError())).toBe(true);
      expect(isRetryableAuthError(new SessionRefreshError())).toBe(true);
    });

    it('should return false for non-retryable errors', () => {
      expect(isRetryableAuthError(new InvalidCredentialsError())).toBe(false);
      expect(isRetryableAuthError(new PermissionDeniedError())).toBe(false);
      expect(isRetryableAuthError(new FlowExpiredError('id-1'))).toBe(false);
      expect(isRetryableAuthError(new SessionExpiredError())).toBe(false);
    });

    it('should return false for non-AuthError', () => {
      expect(isRetryableAuthError(new Error('network'))).toBe(false);
    });
  });
});
