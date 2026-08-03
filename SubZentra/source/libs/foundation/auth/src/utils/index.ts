/**
 * Utils Module
 *
 * Authentication utility functions.
 *
 * @module utils
 */

export { createRealtimeTicketFetcher, type RealtimeAuthTicket } from './realtime-ticket';

export {
  // Decoding
  decodeJwt,
  decodeJwtPayload,
  // Validation
  isTokenExpired,
  getTokenExpiration,
  getTimeUntilExpiration,
  // Claim extraction
  getUserIdFromToken,
  getEmailFromToken,
  getClaimFromToken,
  // Types
  type JwtHeader,
  type JwtStandardClaims,
  type JwtPayload,
  type DecodedJwt,
} from './token-utils';
