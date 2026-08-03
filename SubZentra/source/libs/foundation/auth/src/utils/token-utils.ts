/**
 * Token Utilities
 *
 * JWT token handling utilities.
 *
 * @module utils/token-utils
 */

// =============================================================================
// Types
// =============================================================================

/**
 * JWT header
 */
export interface JwtHeader {
  alg: string;
  typ: string;
  kid?: string;
}

/**
 * Standard JWT claims
 */
export interface JwtStandardClaims {
  /** Issuer */
  iss?: string;
  /** Subject (user ID) */
  sub?: string;
  /** Audience */
  aud?: string | string[];
  /** Expiration time (Unix timestamp) */
  exp?: number;
  /** Not before (Unix timestamp) */
  nbf?: number;
  /** Issued at (Unix timestamp) */
  iat?: number;
  /** JWT ID */
  jti?: string;
}

/**
 * JWT payload with standard and custom claims
 */
export interface JwtPayload extends JwtStandardClaims {
  /** Email claim */
  email?: string;
  /** Email verified claim */
  email_verified?: boolean;
  /** Name claim */
  name?: string;
  /** Given name claim */
  given_name?: string;
  /** Family name claim */
  family_name?: string;
  /** Picture URL claim */
  picture?: string;
  /** Custom claims */
  [key: string]: unknown;
}

/**
 * Decoded JWT
 */
export interface DecodedJwt {
  header: JwtHeader;
  payload: JwtPayload;
  signature: string;
}

// =============================================================================
// Decoding (without verification)
// =============================================================================

/**
 * Decode a JWT without verification
 *
 * WARNING: This does NOT verify the signature. Use only for reading claims
 * from tokens that have already been verified by the backend.
 *
 * @param token - JWT string
 * @returns Decoded JWT or null if invalid
 *
 * @example
 * ```typescript
 * const decoded = decodeJwt(accessToken);
 * if (decoded) {
 *   console.log('User ID:', decoded.payload.sub);
 *   console.log('Expires:', new Date(decoded.payload.exp! * 1000));
 * }
 * ```
 */
export const decodeJwt = (token: string): DecodedJwt | null => {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) {
      return null;
    }

    const [headerB64, payloadB64, signature] = parts;

    const header = JSON.parse(base64UrlDecode(headerB64)) as JwtHeader;
    const payload = JSON.parse(base64UrlDecode(payloadB64)) as JwtPayload;

    return { header, payload, signature };
  } catch {
    return null;
  }
};

/**
 * Decode JWT payload only
 *
 * @param token - JWT string
 * @returns JWT payload or null if invalid
 */
export const decodeJwtPayload = (token: string): JwtPayload | null => {
  const decoded = decodeJwt(token);
  return decoded?.payload ?? null;
};

// =============================================================================
// Token Validation (client-side checks only)
// =============================================================================

/**
 * Get payload from token input (string, decoded JWT, or payload)
 */
const extractPayload = (token: string | DecodedJwt | JwtPayload): JwtPayload | null => {
  if (typeof token === 'string') {
    return decodeJwtPayload(token);
  }
  if (token && typeof token === 'object' && 'payload' in token) {
    return (token as DecodedJwt).payload;
  }
  return token as JwtPayload;
};

/**
 * Check if a token is expired
 *
 * @param token - JWT string or decoded JWT
 * @param bufferMs - Buffer time in milliseconds (default: 0)
 * @returns True if token is expired
 *
 * @example
 * ```typescript
 * // Check if expired with 1 minute buffer
 * if (isTokenExpired(accessToken, 60_000)) {
 *   await refreshToken();
 * }
 * ```
 */
export const isTokenExpired = (token: string | DecodedJwt | JwtPayload, bufferMs = 0): boolean => {
  const payload = extractPayload(token);

  if (!payload?.exp) {
    // No expiration claim - consider it valid
    return false;
  }

  const expirationTime = payload.exp * 1000; // Convert to milliseconds
  const now = Date.now();

  return now + bufferMs >= expirationTime;
};

/**
 * Get token expiration time
 *
 * @param token - JWT string or decoded JWT
 * @returns Expiration timestamp in milliseconds, or null if no expiration
 */
export const getTokenExpiration = (token: string | DecodedJwt | JwtPayload): number | null => {
  const payload = extractPayload(token);

  if (!payload?.exp) {
    return null;
  }

  return payload.exp * 1000;
};

/**
 * Get time until token expires
 *
 * @param token - JWT string or decoded JWT
 * @returns Milliseconds until expiration, or null if no expiration
 */
export const getTimeUntilExpiration = (token: string | DecodedJwt | JwtPayload): number | null => {
  const expiration = getTokenExpiration(token);
  if (expiration === null) {
    return null;
  }

  return Math.max(0, expiration - Date.now());
};

// =============================================================================
// Claim Extraction
// =============================================================================

/**
 * Get payload from token input (string or payload object)
 */
const getPayloadFromInput = (token: string | JwtPayload): JwtPayload | null => {
  if (typeof token === 'string') {
    return decodeJwtPayload(token);
  }
  return token;
};

/**
 * Extract user ID from token
 *
 * @param token - JWT string or payload
 * @returns User ID (sub claim) or null
 */
export const getUserIdFromToken = (token: string | JwtPayload): string | null => {
  const payload = getPayloadFromInput(token);
  return payload?.sub ?? null;
};

/**
 * Extract email from token
 *
 * @param token - JWT string or payload
 * @returns Email or null
 */
export const getEmailFromToken = (token: string | JwtPayload): string | null => {
  const payload = getPayloadFromInput(token);
  return payload?.email ?? null;
};

/**
 * Extract custom claim from token
 *
 * @param token - JWT string or payload
 * @param claim - Claim name
 * @returns Claim value or null
 */
export const getClaimFromToken = <T = unknown>(
  token: string | JwtPayload,
  claim: string,
): T | null => {
  const payload = getPayloadFromInput(token);
  return (payload?.[claim] as T) ?? null;
};

// =============================================================================
// Internal Helpers
// =============================================================================

/**
 * Decode base64url string
 */
const base64UrlDecode = (input: string): string => {
  // Replace base64url characters with base64
  let base64 = input.replace(/-/g, '+').replace(/_/g, '/');

  // Add padding if needed
  const padding = base64.length % 4;
  if (padding) {
    base64 += '='.repeat(4 - padding);
  }

  // Decode
  if (typeof atob === 'function') {
    // Browser
    return decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    );
  } else {
    // Node.js
    return Buffer.from(base64, 'base64').toString('utf8');
  }
};
