/**
 * Foundation Metrics Configuration Types
 * @module types/config
 */

import type { AxiosInstance } from 'axios';

import type { ComplianceRegion, Environment } from '@open-zentra/foundation-data-model';

import type { FoundationMetricsPlugin } from './plugin';

/**
 * Error signal specific configuration
 */
export interface ErrorSignalConfig {
  enabled: boolean;
  captureUnhandledRejections: boolean;
  captureGlobalErrors: boolean;
  enableSourceMaps: boolean;
}

/**
 * Performance signal specific configuration
 */
export interface PerformanceSignalConfig {
  enabled: boolean;
  webVitals: boolean;
  pageLoad: boolean;
  spaNavigation: boolean;
  longTasks: boolean;
  longTaskThreshold: number;
}

/**
 * Network signal specific configuration
 */
export interface NetworkSignalConfig {
  enabled: boolean;
  trackFetch: boolean;
  trackXHR: boolean;
  trackRetries: boolean;
  ignoreUrls: string[];
  propagateTraceContextTo: string[];
  axiosInstance?: AxiosInstance;
}

/**
 * User behavior signal specific configuration
 */
export interface UserBehaviorSignalConfig {
  enabled: boolean;
  trackClicks: boolean;
  trackNavigation: boolean;
  detectRageClicks: boolean;
  rageClickThreshold: number;
  rageClickWindow: number;
  trackSession: boolean;
  sessionTimeout: number;
}

/**
 * Sampling configuration
 */
export interface SamplingConfig {
  defaultRate: number;
  errorRate: number;
  traceRate: number;
  userBehaviorRate: number;
}

/**
 * Compliance and security configuration
 */
export interface ComplianceConfig {
  piiFields: string[];
  allowedFields: string[];
  tenantHashSalt?: string;
  region: ComplianceRegion;
  autoPiiDetection: boolean;
  customPiiPatterns?: string[];
}

/**
 * Tenant context configuration
 */
export interface TenantConfig {
  id: string;
  tier?: string;
  metadata?: Record<string, string>;
}

/**
 * Transport configuration for OTLP
 */
export interface TransportConfig {
  batchSize: number;
  flushInterval: number;
  maxQueueSize: number;
  timeout: number;
  retryAttempts: number;
  compression: boolean;
}

/**
 * Signal configuration - can be boolean or detailed config
 */
export interface SignalsConfig {
  errors: boolean | ErrorSignalConfig;
  performance: boolean | PerformanceSignalConfig;
  network: boolean | NetworkSignalConfig;
  userBehavior: boolean | UserBehaviorSignalConfig;
}

/**
 * Main configuration interface for Foundation Metrics
 */
export interface FoundationMetricsConfig {
  serviceName: string;
  collectorEndpoint: string;
  environment: Environment;
  version: string;
  signals: SignalsConfig;
  sampling: SamplingConfig;
  compliance: ComplianceConfig;
  tenant?: TenantConfig;
  transport?: Partial<TransportConfig>;
  plugins?: FoundationMetricsPlugin[];
  debug?: boolean;
  resourceAttributes?: Record<string, string>;
}

export const RESOLVED_CONFIG_OPTIONAL_KEY = {
  TENANT: 'tenant',
  PLUGINS: 'plugins',
  RESOURCE_ATTRIBUTES: 'resourceAttributes',
} as const;

type ResolvedConfigOptionalKey =
  (typeof RESOLVED_CONFIG_OPTIONAL_KEY)[keyof typeof RESOLVED_CONFIG_OPTIONAL_KEY];

/**
 * Resolved configuration with all defaults applied
 */
export interface ResolvedConfig
  extends Required<Omit<FoundationMetricsConfig, ResolvedConfigOptionalKey>> {
  tenant?: TenantConfig;
  plugins: FoundationMetricsPlugin[];
  resourceAttributes: Record<string, string>;
  signals: {
    errors: ErrorSignalConfig;
    performance: PerformanceSignalConfig;
    network: NetworkSignalConfig;
    userBehavior: UserBehaviorSignalConfig;
  };
  transport: TransportConfig;
}
