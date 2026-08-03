/**
 * Tests for token-utils
 *
 * JWT decoding and validation utilities.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  decodeJwt,
  decodeJwtPayload,
  getClaimFromToken,
  getEmailFromToken,
  getTimeUntilExpiration,
  getTokenExpiration,
  getUserIdFromToken,
  isTokenExpired,
  type DecodedJwt,
  type JwtPayload,
} from './token-utils';

// =============================================================================
// Helpers
// =============================================================================

/**
 * Create a valid JWT string from header and payload objects.
 */
const createJwt = (
  header: Record<string, unknown> = { alg: 'RS256', typ: 'JWT' },
  payload: Record<string, unknown> = {},
  signature = 'test-signature',
): string => {
  const encode = (obj: Record<string, unknown>): string => {
    const json = JSON.stringify(obj);
    // Base64url encode
    const base64 = btoa(
      encodeURIComponent(json).replace(/%([0-9A-F]{2})/g, (_, p1) =>
        String.fromCharCode(parseInt(p1 as string, 16)),
      ),
    );
    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  };

  return `${encode(header)}.${encode(payload)}.${signature}`;
};

/**
 * Create a JWT with standard claims.
 */
const createStandardJwt = (claims: Partial<JwtPayload> = {}): string =>
  createJwt(
    { alg: 'RS256', typ: 'JWT' },
    {
      sub: 'user-123',
      iss: 'https://auth.example.com',
      iat: Math.floor(Date.now() / 1000),
      ...claims,
    },
  );

// =============================================================================
// Tests
// =============================================================================

describe('token-utils', () => {
  // ===========================================================================
  // decodeJwt
  // ===========================================================================

  describe('decodeJwt', () => {
    it('should decode a valid JWT', () => {
      const token = createStandardJwt({ sub: 'user-42', email: 'test@example.com' });
      const result = decodeJwt(token);

      expect(result).not.toBeNull();
      expect(result!.header.alg).toBe('RS256');
      expect(result!.header.typ).toBe('JWT');
      expect(result!.payload.sub).toBe('user-42');
      expect(result!.payload.email).toBe('test@example.com');
      expect(result!.signature).toBe('test-signature');
    });

    it('should return null for empty string', () => {
      expect(decodeJwt('')).toBeNull();
    });

    it('should return null for string with wrong number of parts', () => {
      expect(decodeJwt('only-one-part')).toBeNull();
      expect(decodeJwt('two.parts')).toBeNull();
      expect(decodeJwt('four.parts.here.now')).toBeNull();
    });

    it('should return null for invalid base64url', () => {
      expect(decodeJwt('!!!.@@@.###')).toBeNull();
    });

    it('should return null for non-JSON base64', () => {
      const notJson = btoa('not json').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
      expect(decodeJwt(`${notJson}.${notJson}.sig`)).toBeNull();
    });

    it('should handle JWT with custom header fields', () => {
      const token = createJwt({ alg: 'ES256', typ: 'JWT', kid: 'key-1' }, { sub: 'u1' });
      const result = decodeJwt(token);

      expect(result).not.toBeNull();
      expect(result!.header.kid).toBe('key-1');
      expect(result!.header.alg).toBe('ES256');
    });
  });

  // ===========================================================================
  // decodeJwtPayload
  // ===========================================================================

  describe('decodeJwtPayload', () => {
    it('should return payload from valid JWT', () => {
      const token = createStandardJwt({ sub: 'user-1', name: 'Alice' });
      const payload = decodeJwtPayload(token);

      expect(payload).not.toBeNull();
      expect(payload!.sub).toBe('user-1');
      expect(payload!.name).toBe('Alice');
    });

    it('should return null for invalid token', () => {
      expect(decodeJwtPayload('invalid')).toBeNull();
    });
  });

  // ===========================================================================
  // isTokenExpired
  // ===========================================================================

  describe('isTokenExpired', () => {
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2025-01-15T12:00:00Z'));
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should return false for token without exp claim', () => {
      const token = createStandardJwt({ sub: 'user-1' });
      expect(isTokenExpired(token)).toBe(false);
    });

    it('should return false for non-expired token', () => {
      const futureExp = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
      const token = createStandardJwt({ exp: futureExp });
      expect(isTokenExpired(token)).toBe(false);
    });

    it('should return true for expired token', () => {
      const pastExp = Math.floor(Date.now() / 1000) - 60; // 1 minute ago
      const token = createStandardJwt({ exp: pastExp });
      expect(isTokenExpired(token)).toBe(true);
    });

    it('should consider buffer time', () => {
      const exp = Math.floor(Date.now() / 1000) + 30; // 30 seconds from now
      const token = createStandardJwt({ exp });

      // Without buffer - not expired
      expect(isTokenExpired(token)).toBe(false);

      // With 60s buffer - expired (30s remaining < 60s buffer)
      expect(isTokenExpired(token, 60_000)).toBe(true);
    });

    it('should accept DecodedJwt input', () => {
      const futureExp = Math.floor(Date.now() / 1000) + 3600;
      const decoded: DecodedJwt = {
        header: { alg: 'RS256', typ: 'JWT' },
        payload: { exp: futureExp },
        signature: 'sig',
      };
      expect(isTokenExpired(decoded)).toBe(false);
    });

    it('should accept JwtPayload input', () => {
      const futureExp = Math.floor(Date.now() / 1000) + 3600;
      const payload: JwtPayload = { exp: futureExp };
      expect(isTokenExpired(payload)).toBe(false);
    });

    it('should return false for invalid token string', () => {
      // Invalid token → null payload → no exp → not expired
      expect(isTokenExpired('invalid-token')).toBe(false);
    });
  });

  // ===========================================================================
  // getTokenExpiration
  // ===========================================================================

  describe('getTokenExpiration', () => {
    it('should return expiration in milliseconds', () => {
      const exp = 1705320000; // Unix timestamp in seconds
      const token = createStandardJwt({ exp });
      expect(getTokenExpiration(token)).toBe(exp * 1000);
    });

    it('should return null for token without exp', () => {
      const token = createStandardJwt({ sub: 'user-1' });
      expect(getTokenExpiration(token)).toBeNull();
    });

    it('should return null for invalid token', () => {
      expect(getTokenExpiration('invalid')).toBeNull();
    });

    it('should accept payload object', () => {
      const payload: JwtPayload = { exp: 1705320000 };
      expect(getTokenExpiration(payload)).toBe(1705320000 * 1000);
    });
  });

  // ===========================================================================
  // getTimeUntilExpiration
  // ===========================================================================

  describe('getTimeUntilExpiration', () => {
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2025-01-15T12:00:00Z'));
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should return milliseconds until expiration', () => {
      const exp = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
      const token = createStandardJwt({ exp });
      const timeLeft = getTimeUntilExpiration(token);

      expect(timeLeft).toBe(3600 * 1000);
    });

    it('should return 0 for already expired token', () => {
      const exp = Math.floor(Date.now() / 1000) - 60; // 1 minute ago
      const token = createStandardJwt({ exp });
      expect(getTimeUntilExpiration(token)).toBe(0);
    });

    it('should return null for token without exp', () => {
      const token = createStandardJwt({});
      expect(getTimeUntilExpiration(token)).toBeNull();
    });
  });

  // ===========================================================================
  // getUserIdFromToken
  // ===========================================================================

  describe('getUserIdFromToken', () => {
    it('should extract sub claim from token string', () => {
      const token = createStandardJwt({ sub: 'user-abc-123' });
      expect(getUserIdFromToken(token)).toBe('user-abc-123');
    });

    it('should extract sub from payload object', () => {
      const payload: JwtPayload = { sub: 'user-xyz' };
      expect(getUserIdFromToken(payload)).toBe('user-xyz');
    });

    it('should return null when no sub claim', () => {
      const payload: JwtPayload = { email: 'test@example.com' };
      expect(getUserIdFromToken(payload)).toBeNull();
    });

    it('should return null for invalid token', () => {
      expect(getUserIdFromToken('invalid')).toBeNull();
    });
  });

  // ===========================================================================
  // getEmailFromToken
  // ===========================================================================

  describe('getEmailFromToken', () => {
    it('should extract email claim from token string', () => {
      const token = createStandardJwt({ email: 'test@example.com' });
      expect(getEmailFromToken(token)).toBe('test@example.com');
    });

    it('should extract email from payload object', () => {
      const payload: JwtPayload = { email: 'alice@example.com' };
      expect(getEmailFromToken(payload)).toBe('alice@example.com');
    });

    it('should return null when no email claim', () => {
      const payload: JwtPayload = { sub: 'user-1' };
      expect(getEmailFromToken(payload)).toBeNull();
    });
  });

  // ===========================================================================
  // getClaimFromToken
  // ===========================================================================

  describe('getClaimFromToken', () => {
    it('should extract custom string claim', () => {
      const token = createStandardJwt({ role: 'admin' });
      expect(getClaimFromToken<string>(token, 'role')).toBe('admin');
    });

    it('should extract custom number claim', () => {
      const payload: JwtPayload = { org_id: 42 };
      expect(getClaimFromToken<number>(payload, 'org_id')).toBe(42);
    });

    it('should extract custom object claim', () => {
      const payload: JwtPayload = { metadata: { tier: 'pro' } };
      const result = getClaimFromToken<{ tier: string }>(payload, 'metadata');
      expect(result).toEqual({ tier: 'pro' });
    });

    it('should return null for missing claim', () => {
      const payload: JwtPayload = { sub: 'user-1' };
      expect(getClaimFromToken(payload, 'nonexistent')).toBeNull();
    });

    it('should return null for invalid token', () => {
      expect(getClaimFromToken('invalid', 'sub')).toBeNull();
    });
  });
});
