/**
 * Tests for auth constants
 *
 * Validates constant values and type exports.
 */

import { describe, expect, it } from 'vitest';

import {
  AUTH_ERROR_CODE,
  AUTH_FLOW_TYPE,
  AUTH_STATE,
  DEFAULT_AUTH_CONFIG,
  FLOW_STATE,
  IDENTITY_TRAIT,
  SESSION_STATE,
} from './constants';

describe('auth constants', () => {
  // ===========================================================================
  // AUTH_FLOW_TYPE
  // ===========================================================================

  describe('AUTH_FLOW_TYPE', () => {
    it('should define all 5 flow types', () => {
      expect(AUTH_FLOW_TYPE.LOGIN).toBe('login');
      expect(AUTH_FLOW_TYPE.REGISTRATION).toBe('registration');
      expect(AUTH_FLOW_TYPE.RECOVERY).toBe('recovery');
      expect(AUTH_FLOW_TYPE.VERIFICATION).toBe('verification');
      expect(AUTH_FLOW_TYPE.SETTINGS).toBe('settings');
    });

    it('should have exactly 5 entries', () => {
      expect(Object.keys(AUTH_FLOW_TYPE)).toHaveLength(5);
    });
  });

  // ===========================================================================
  // AUTH_STATE
  // ===========================================================================

  describe('AUTH_STATE', () => {
    it('should define all states', () => {
      expect(AUTH_STATE.INITIALIZING).toBe('initializing');
      expect(AUTH_STATE.AUTHENTICATED).toBe('authenticated');
      expect(AUTH_STATE.UNAUTHENTICATED).toBe('unauthenticated');
      expect(AUTH_STATE.ERROR).toBe('error');
    });

    it('should have exactly 4 entries', () => {
      expect(Object.keys(AUTH_STATE)).toHaveLength(4);
    });
  });

  // ===========================================================================
  // AUTH_ERROR_CODE
  // ===========================================================================

  describe('AUTH_ERROR_CODE', () => {
    it('should prefix all codes with AUTH_', () => {
      for (const value of Object.values(AUTH_ERROR_CODE)) {
        expect(value).toMatch(/^AUTH_/);
      }
    });

    it('should define all error codes', () => {
      expect(AUTH_ERROR_CODE.NOT_INITIALIZED).toBe('AUTH_NOT_INITIALIZED');
      expect(AUTH_ERROR_CODE.UNAUTHORIZED).toBe('AUTH_UNAUTHORIZED');
      expect(AUTH_ERROR_CODE.SESSION_CHECK_FAILED).toBe('AUTH_SESSION_CHECK_FAILED');
      expect(AUTH_ERROR_CODE.SESSION_REFRESH_FAILED).toBe('AUTH_SESSION_REFRESH_FAILED');
      expect(AUTH_ERROR_CODE.SESSION_EXPIRED).toBe('AUTH_SESSION_EXPIRED');
      expect(AUTH_ERROR_CODE.LOGOUT_FAILED).toBe('AUTH_LOGOUT_FAILED');
      expect(AUTH_ERROR_CODE.FLOW_CREATION_FAILED).toBe('AUTH_FLOW_CREATION_FAILED');
      expect(AUTH_ERROR_CODE.FLOW_NOT_FOUND).toBe('AUTH_FLOW_NOT_FOUND');
      expect(AUTH_ERROR_CODE.FLOW_SUBMISSION_FAILED).toBe('AUTH_FLOW_SUBMISSION_FAILED');
      expect(AUTH_ERROR_CODE.FLOW_EXPIRED).toBe('AUTH_FLOW_EXPIRED');
      expect(AUTH_ERROR_CODE.INVALID_CREDENTIALS).toBe('AUTH_INVALID_CREDENTIALS');
      expect(AUTH_ERROR_CODE.USER_NOT_FOUND).toBe('AUTH_USER_NOT_FOUND');
      expect(AUTH_ERROR_CODE.PERMISSION_DENIED).toBe('AUTH_PERMISSION_DENIED');
      expect(AUTH_ERROR_CODE.TOKEN_RETRIEVAL_FAILED).toBe('AUTH_TOKEN_RETRIEVAL_FAILED');
      expect(AUTH_ERROR_CODE.TOKEN_EXPIRED).toBe('AUTH_TOKEN_EXPIRED');
      expect(AUTH_ERROR_CODE.CLIENT_CONFIG_ERROR).toBe('AUTH_CLIENT_CONFIG_ERROR');
      expect(AUTH_ERROR_CODE.NETWORK_ERROR).toBe('AUTH_NETWORK_ERROR');
    });

    it('should have exactly 17 error codes', () => {
      expect(Object.keys(AUTH_ERROR_CODE)).toHaveLength(17);
    });
  });

  // ===========================================================================
  // DEFAULT_AUTH_CONFIG
  // ===========================================================================

  describe('DEFAULT_AUTH_CONFIG', () => {
    it('should define session refresh interval (5 minutes)', () => {
      expect(DEFAULT_AUTH_CONFIG.SESSION_REFRESH_INTERVAL_MS).toBe(300_000);
    });

    it('should define flow timeout (30 minutes)', () => {
      expect(DEFAULT_AUTH_CONFIG.FLOW_TIMEOUT_MS).toBe(1_800_000);
    });

    it('should define token refresh buffer (1 minute)', () => {
      expect(DEFAULT_AUTH_CONFIG.TOKEN_REFRESH_BUFFER_MS).toBe(60_000);
    });

    it('should define max session check retries', () => {
      expect(DEFAULT_AUTH_CONFIG.MAX_SESSION_CHECK_RETRIES).toBe(3);
    });

    it('should define session check retry delay', () => {
      expect(DEFAULT_AUTH_CONFIG.SESSION_CHECK_RETRY_DELAY_MS).toBe(1_000);
    });
  });

  // ===========================================================================
  // SESSION_STATE
  // ===========================================================================

  describe('SESSION_STATE', () => {
    it('should define all session states', () => {
      expect(SESSION_STATE.ACTIVE).toBe('active');
      expect(SESSION_STATE.REFRESHING).toBe('refreshing');
      expect(SESSION_STATE.STALE).toBe('stale');
      expect(SESSION_STATE.EXPIRED).toBe('expired');
      expect(SESSION_STATE.INVALID).toBe('invalid');
    });

    it('should have exactly 5 entries', () => {
      expect(Object.keys(SESSION_STATE)).toHaveLength(5);
    });
  });

  // ===========================================================================
  // FLOW_STATE
  // ===========================================================================

  describe('FLOW_STATE', () => {
    it('should define all flow states', () => {
      expect(FLOW_STATE.PENDING).toBe('pending');
      expect(FLOW_STATE.SUBMITTING).toBe('submitting');
      expect(FLOW_STATE.COMPLETED).toBe('completed');
      expect(FLOW_STATE.FAILED).toBe('failed');
      expect(FLOW_STATE.EXPIRED).toBe('expired');
    });

    it('should have exactly 5 entries', () => {
      expect(Object.keys(FLOW_STATE)).toHaveLength(5);
    });
  });

  // ===========================================================================
  // IDENTITY_TRAIT
  // ===========================================================================

  describe('IDENTITY_TRAIT', () => {
    it('should define all trait keys', () => {
      expect(IDENTITY_TRAIT.EMAIL).toBe('email');
      expect(IDENTITY_TRAIT.NAME).toBe('name');
      expect(IDENTITY_TRAIT.FIRST_NAME).toBe('first_name');
      expect(IDENTITY_TRAIT.LAST_NAME).toBe('last_name');
      expect(IDENTITY_TRAIT.PHONE).toBe('phone');
      expect(IDENTITY_TRAIT.AVATAR_URL).toBe('avatar_url');
      expect(IDENTITY_TRAIT.ROLE).toBe('role');
      expect(IDENTITY_TRAIT.TENANT_ID).toBe('tenant_id');
    });

    it('should have exactly 8 entries', () => {
      expect(Object.keys(IDENTITY_TRAIT)).toHaveLength(8);
    });
  });
});
