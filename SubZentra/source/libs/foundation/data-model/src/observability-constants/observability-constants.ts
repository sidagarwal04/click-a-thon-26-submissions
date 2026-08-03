/**
 * Observability Constants
 *
 * Shared constants for observability across foundation libraries.
 *
 * @module observability-constants
 */

export const ENVIRONMENT = {
  DEVELOPMENT: 'development',
  STAGING: 'staging',
  PRODUCTION: 'production',
} as const;

export type Environment = (typeof ENVIRONMENT)[keyof typeof ENVIRONMENT];

export const COMPLIANCE_REGION = {
  US: 'us',
  EU: 'eu',
  INDIA: 'india',
} as const;

export type ComplianceRegion = (typeof COMPLIANCE_REGION)[keyof typeof COMPLIANCE_REGION];

export const SEVERITY_NUMBER = {
  TRACE: 1,
  DEBUG: 5,
  INFO: 9,
  WARN: 13,
  ERROR: 17,
  FATAL: 21,
} as const;

export type SeverityNumberValue = (typeof SEVERITY_NUMBER)[keyof typeof SEVERITY_NUMBER];

export const HASH_ALGORITHM = {
  SHA_256: 'sha256',
  SHA_512: 'sha512',
  SHA_384: 'sha384',
} as const;

export type HashAlgorithm = (typeof HASH_ALGORITHM)[keyof typeof HASH_ALGORITHM];
