/**
 * Compliance and Security Type Definitions
 * @module types/compliance
 */

import type { ComplianceRegion, HashAlgorithm } from '@open-zentra/foundation-data-model';
import type { URLSanitizationOptions } from '@open-zentra/foundation-utils';

import type { AuditLogAction, PiiFieldType } from './constants';

/**
 * PII detection result
 */
export interface PIIDetectionResult {
  detected: boolean;
  type?: PiiFieldType;
  fieldName?: string;
  originalValue?: string;
  redactedValue: string;
}

/**
 * PII pattern configuration
 */
export interface PIIPattern {
  name: string;
  type: PiiFieldType;
  pattern: RegExp;
  replacement: string | ((match: string) => string);
  priority: number;
}

/**
 * Field allowlist/denylist configuration
 */
export interface FieldListConfig {
  allowedFields: string[];
  deniedFields: string[];
  allowByDefault: boolean;
}

/**
 * Default URL sanitization options for metrics
 */
export const DEFAULT_URL_SANITIZATION: URLSanitizationOptions = {
  removeQueryParams: false,
  preserveQueryParams: ['page', 'tab', 'view', 'sort', 'filter'],
  removeHash: true,
  removeAuth: true,
  removePort: false,
  maskPathPatterns: [/\/users\/[^/]+/g, /\/orders\/[^/]+/g, /\/accounts\/[^/]+/g],
};

/**
 * Data retention configuration
 */
export interface DataRetentionConfig {
  tracesRetentionDays: number;
  metricsRetentionDays: number;
  logsRetentionDays: number;
  enableAutoExpiry: boolean;
}

/**
 * Default data retention config
 */
export const DEFAULT_DATA_RETENTION: DataRetentionConfig = {
  tracesRetentionDays: 30,
  metricsRetentionDays: 90,
  logsRetentionDays: 30,
  enableAutoExpiry: true,
};

/**
 * Regional compliance requirements
 */
export interface RegionalCompliance {
  region: ComplianceRegion;
  gdprRequired: boolean;
  dataResidencyRequired: boolean;
  consentRequired: boolean;
  rightToDeletionRequired: boolean;
  encryptionAtRestRequired: boolean;
  encryptionInTransitRequired: boolean;
  auditLoggingRequired: boolean;
}

/**
 * Regional compliance configurations
 */
export const REGIONAL_COMPLIANCE: Record<ComplianceRegion, RegionalCompliance> = {
  us: {
    region: 'us',
    gdprRequired: false,
    dataResidencyRequired: false,
    consentRequired: false,
    rightToDeletionRequired: false,
    encryptionAtRestRequired: true,
    encryptionInTransitRequired: true,
    auditLoggingRequired: true,
  },
  eu: {
    region: 'eu',
    gdprRequired: true,
    dataResidencyRequired: true,
    consentRequired: true,
    rightToDeletionRequired: true,
    encryptionAtRestRequired: true,
    encryptionInTransitRequired: true,
    auditLoggingRequired: true,
  },
  india: {
    region: 'india',
    gdprRequired: false,
    dataResidencyRequired: true,
    consentRequired: true,
    rightToDeletionRequired: true,
    encryptionAtRestRequired: true,
    encryptionInTransitRequired: true,
    auditLoggingRequired: true,
  },
};

/**
 * Consent state
 */
export interface ConsentState {
  analytics: boolean;
  performance: boolean;
  errorTracking: boolean;
  userBehavior: boolean;
  timestamp: number;
  version: string;
}

/**
 * Default consent state (all denied)
 */
export const DEFAULT_CONSENT_STATE: ConsentState = {
  analytics: false,
  performance: false,
  errorTracking: false,
  userBehavior: false,
  timestamp: 0,
  version: '1.0',
};

/**
 * Audit log entry
 */
export interface AuditLogEntry {
  action: AuditLogAction;
  actor: string;
  timestamp: number;
  details: Record<string, unknown>;
  ipHash?: string;
}

/**
 * Security context
 */
export interface SecurityContext {
  consent: ConsentState;
  compliance: RegionalCompliance;
  retention: DataRetentionConfig;
  piiPatterns: PIIPattern[];
  fieldList: FieldListConfig;
}

/**
 * Hashing configuration
 */
export interface HashingConfig {
  algorithm: HashAlgorithm;
  salt: string;
  iterations: number;
}

/**
 * Default hashing config
 */
export const DEFAULT_HASHING_CONFIG: HashingConfig = {
  algorithm: 'sha256',
  salt: '',
  iterations: 1000,
};
