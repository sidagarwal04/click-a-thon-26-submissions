/**
 * Configuration Resolver
 * @module core/config-resolver
 */

import { COMPLIANCE_REGION, ENVIRONMENT } from '@open-zentra/foundation-data-model';

import type {
  ErrorSignalConfig,
  FoundationMetricsConfig,
  NetworkSignalConfig,
  PerformanceSignalConfig,
  ResolvedConfig,
  UserBehaviorSignalConfig,
} from '../types';
import { resolveTransportConfig } from './transport';

/**
 * Default signal configurations
 */
const DEFAULT_ERROR_CONFIG: ErrorSignalConfig = {
  enabled: true,
  captureUnhandledRejections: true,
  captureGlobalErrors: true,
  enableSourceMaps: false,
};

const DEFAULT_PERFORMANCE_CONFIG: PerformanceSignalConfig = {
  enabled: true,
  webVitals: true,
  pageLoad: true,
  spaNavigation: true,
  longTasks: true,
  longTaskThreshold: 50,
};

const DEFAULT_NETWORK_CONFIG: NetworkSignalConfig = {
  enabled: true,
  trackFetch: true,
  trackXHR: true,
  trackRetries: true,
  ignoreUrls: [],
  propagateTraceContextTo: [],
  axiosInstance: undefined,
};

const DEFAULT_USER_BEHAVIOR_CONFIG: UserBehaviorSignalConfig = {
  enabled: true,
  trackClicks: true,
  trackNavigation: true,
  detectRageClicks: true,
  rageClickThreshold: 3,
  rageClickWindow: 1000,
  trackSession: true,
  sessionTimeout: 30 * 60 * 1000, // 30 minutes
};

/**
 * Resolve signal configuration from boolean or object
 */
const resolveSignalConfig = <T extends { enabled: boolean }>(
  config: boolean | T,
  defaults: T,
): T => {
  if (typeof config === 'boolean') {
    return { ...defaults, enabled: config };
  }
  return { ...defaults, ...config };
};

/**
 * Resolve the full configuration with defaults
 */
export function resolveConfig(config: FoundationMetricsConfig): ResolvedConfig {
  // Validate required fields
  if (!config.serviceName) {
    throw new Error('FoundationMetrics: serviceName is required');
  }
  if (!config.collectorEndpoint) {
    throw new Error('FoundationMetrics: collectorEndpoint is required');
  }
  if (!config.environment) {
    throw new Error('FoundationMetrics: environment is required');
  }
  if (!config.version) {
    throw new Error('FoundationMetrics: version is required');
  }

  // Resolve signals configuration
  const signals = {
    errors: resolveSignalConfig(config.signals.errors, DEFAULT_ERROR_CONFIG),
    performance: resolveSignalConfig(config.signals.performance, DEFAULT_PERFORMANCE_CONFIG),
    network: resolveSignalConfig(config.signals.network, DEFAULT_NETWORK_CONFIG),
    userBehavior: resolveSignalConfig(config.signals.userBehavior, DEFAULT_USER_BEHAVIOR_CONFIG),
  };

  // Resolve sampling configuration
  const sampling = {
    defaultRate: config.sampling?.defaultRate ?? 1.0,
    errorRate: config.sampling?.errorRate ?? 1.0,
    traceRate: config.sampling?.traceRate ?? 0.1,
    userBehaviorRate: config.sampling?.userBehaviorRate ?? 0.1,
  };

  // Resolve compliance configuration
  const compliance = {
    piiFields: config.compliance?.piiFields ?? ['email', 'password', 'ssn', 'creditCard', 'phone'],
    allowedFields: config.compliance?.allowedFields ?? [],
    tenantHashSalt: config.compliance?.tenantHashSalt,
    region: config.compliance?.region ?? 'us',
    autoPiiDetection: config.compliance?.autoPiiDetection ?? true,
    customPiiPatterns: config.compliance?.customPiiPatterns,
  };

  // Resolve transport configuration
  const transport = resolveTransportConfig(config.transport);

  return {
    serviceName: config.serviceName,
    collectorEndpoint: normalizeEndpoint(config.collectorEndpoint),
    environment: config.environment,
    version: config.version,
    signals,
    sampling,
    compliance,
    tenant: config.tenant,
    transport,
    plugins: config.plugins ?? [],
    debug: config.debug ?? false,
    resourceAttributes: config.resourceAttributes ?? {},
  };
}

/**
 * Normalize the collector endpoint URL
 */
const normalizeEndpoint = (endpoint: string): string => {
  // Remove trailing slash
  const normalized = endpoint.replace(/\/+$/, '');

  // Ensure it's a valid URL
  try {
    new URL(normalized);
  } catch {
    throw new Error(`FoundationMetrics: Invalid collector endpoint: ${endpoint}`);
  }

  return normalized;
};

/**
 * Validate configuration
 */
export function validateConfig(config: FoundationMetricsConfig): string[] {
  const errors: string[] = [];

  if (!config.serviceName) {
    errors.push('serviceName is required');
  }

  if (!config.collectorEndpoint) {
    errors.push('collectorEndpoint is required');
  } else {
    try {
      new URL(config.collectorEndpoint);
    } catch {
      errors.push('collectorEndpoint must be a valid URL');
    }
  }

  if (!config.environment) {
    errors.push('environment is required');
  } else if (!Object.values(ENVIRONMENT).includes(config.environment)) {
    errors.push('environment must be one of: development, staging, production');
  }

  if (!config.version) {
    errors.push('version is required');
  }

  // Validate sampling rates
  if (config.sampling) {
    const { defaultRate, errorRate, traceRate, userBehaviorRate } = config.sampling;

    if (defaultRate !== undefined && (defaultRate < 0 || defaultRate > 1)) {
      errors.push('sampling.defaultRate must be between 0 and 1');
    }
    if (errorRate !== undefined && (errorRate < 0 || errorRate > 1)) {
      errors.push('sampling.errorRate must be between 0 and 1');
    }
    if (traceRate !== undefined && (traceRate < 0 || traceRate > 1)) {
      errors.push('sampling.traceRate must be between 0 and 1');
    }
    if (userBehaviorRate !== undefined && (userBehaviorRate < 0 || userBehaviorRate > 1)) {
      errors.push('sampling.userBehaviorRate must be between 0 and 1');
    }
  }

  // Validate compliance region
  if (
    config.compliance?.region &&
    !Object.values(COMPLIANCE_REGION).includes(config.compliance.region)
  ) {
    errors.push('compliance.region must be one of: us, eu, india');
  }

  return errors;
}

/**
 * Deep merge two configuration objects
 */
export function mergeConfigs(
  base: Partial<FoundationMetricsConfig>,
  override: Partial<FoundationMetricsConfig>,
): Partial<FoundationMetricsConfig> {
  const result: Partial<FoundationMetricsConfig> = {
    ...base,
    ...override,
  };

  // Merge nested objects when both exist
  if (base.signals !== undefined || override.signals !== undefined) {
    result.signals = {
      errors: override.signals?.errors ?? base.signals?.errors ?? DEFAULT_ERROR_CONFIG,
      performance:
        override.signals?.performance ?? base.signals?.performance ?? DEFAULT_PERFORMANCE_CONFIG,
      network: override.signals?.network ?? base.signals?.network ?? DEFAULT_NETWORK_CONFIG,
      userBehavior:
        override.signals?.userBehavior ??
        base.signals?.userBehavior ??
        DEFAULT_USER_BEHAVIOR_CONFIG,
    };
  }

  if (base.sampling !== undefined || override.sampling !== undefined) {
    result.sampling = {
      defaultRate: override.sampling?.defaultRate ?? base.sampling?.defaultRate ?? 1.0,
      errorRate: override.sampling?.errorRate ?? base.sampling?.errorRate ?? 1.0,
      traceRate: override.sampling?.traceRate ?? base.sampling?.traceRate ?? 0.1,
      userBehaviorRate:
        override.sampling?.userBehaviorRate ?? base.sampling?.userBehaviorRate ?? 0.1,
    };
  }

  if (base.compliance !== undefined || override.compliance !== undefined) {
    result.compliance = {
      piiFields: override.compliance?.piiFields ??
        base.compliance?.piiFields ?? ['email', 'password', 'ssn', 'creditCard', 'phone'],
      allowedFields: override.compliance?.allowedFields ?? base.compliance?.allowedFields ?? [],
      tenantHashSalt: override.compliance?.tenantHashSalt ?? base.compliance?.tenantHashSalt,
      region: override.compliance?.region ?? base.compliance?.region ?? COMPLIANCE_REGION.US,
      autoPiiDetection:
        override.compliance?.autoPiiDetection ?? base.compliance?.autoPiiDetection ?? true,
      customPiiPatterns:
        override.compliance?.customPiiPatterns ?? base.compliance?.customPiiPatterns,
    };
  }

  if (base.transport !== undefined || override.transport !== undefined) {
    result.transport = { ...base.transport, ...override.transport };
  }

  result.resourceAttributes = {
    ...base.resourceAttributes,
    ...override.resourceAttributes,
  };

  return result;
}
