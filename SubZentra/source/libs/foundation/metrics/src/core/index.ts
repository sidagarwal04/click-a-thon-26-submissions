/**
 * Core Module Exports
 * @module core
 */

export {
  FoundationMetrics,
  init,
  reinitialize,
  getInstance,
  isInitialized,
  getLifecycleState,
} from './foundation-metrics';

export {
  initializeOTelProviders,
  getTracer,
  getMeter,
  getContext,
  shutdownProviders,
  flushProviders,
  isInitialized as isOTelInitialized,
} from './otel-provider';

export {
  initializeContextManager,
  getTelemetryContext,
  setUser,
  clearUser,
  setTenant,
  setCustomAttributes,
  updateContext,
  updateSessionActivity,
  startNewSession,
  getSpanAttributes,
  injectTraceContext,
  extractTraceContext,
  shutdownContextManager,
} from './context-manager';

export { resolveConfig, validateConfig, mergeConfigs } from './config-resolver';

export {
  createTransport,
  sendBeacon,
  shouldUseBeacon,
  compressData,
  isCompressionSupported,
  resolveTransportConfig,
  DEFAULT_TRANSPORT_CONFIG,
} from './transport';
