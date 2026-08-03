/**
 * Foundation Metrics SDK Tests
 * @module core/foundation-metrics.spec
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FoundationMetricsConfig } from '../types';
import {
  FoundationMetrics,
  getLifecycleState,
  isInitialized,
  resetMetricsStateForTesting,
} from './foundation-metrics';

// Mock OpenTelemetry modules
vi.mock('@opentelemetry/api', () => ({
  trace: {
    getTracer: vi.fn(() => ({
      startSpan: vi.fn(() => ({
        spanContext: () => ({ traceId: 'test-trace-id', spanId: 'test-span-id', traceFlags: 1 }),
        setAttribute: vi.fn(),
        setAttributes: vi.fn(),
        addEvent: vi.fn(),
        setStatus: vi.fn(),
        end: vi.fn(),
        recordException: vi.fn(),
        isRecording: () => true,
        updateName: vi.fn(),
      })),
    })),
    getActiveSpan: vi.fn(),
    getSpan: vi.fn(),
  },
  metrics: {
    getMeter: vi.fn(() => ({
      createHistogram: vi.fn(() => ({ record: vi.fn() })),
      createCounter: vi.fn(() => ({ add: vi.fn() })),
    })),
    setGlobalMeterProvider: vi.fn(),
  },
  context: {
    active: vi.fn(() => ({})),
  },
  propagation: {
    inject: vi.fn(),
    extract: vi.fn(),
    setGlobalPropagator: vi.fn(),
  },
  diag: {
    setLogger: vi.fn(),
  },
  DiagConsoleLogger: vi.fn(),
  DiagLogLevel: { DEBUG: 1 },
  SpanKind: { INTERNAL: 0, CLIENT: 2 },
  SpanStatusCode: { ERROR: 2 },
}));

vi.mock('@opentelemetry/sdk-trace-web', () => ({
  WebTracerProvider: vi.fn(
    class {
      register = vi.fn();
      shutdown = vi.fn().mockResolvedValue(undefined);
      forceFlush = vi.fn().mockResolvedValue(undefined);
    },
  ),
  BatchSpanProcessor: vi.fn(),
}));

vi.mock('@opentelemetry/sdk-metrics', () => ({
  MeterProvider: vi.fn(
    class {
      shutdown = vi.fn().mockResolvedValue(undefined);
      forceFlush = vi.fn().mockResolvedValue(undefined);
    },
  ),
  PeriodicExportingMetricReader: vi.fn(),
}));

vi.mock('@opentelemetry/exporter-trace-otlp-http', () => ({
  OTLPTraceExporter: vi.fn(),
}));

vi.mock('@opentelemetry/exporter-metrics-otlp-http', () => ({
  OTLPMetricExporter: vi.fn(),
}));

vi.mock('@opentelemetry/context-zone', () => ({
  ZoneContextManager: vi.fn(),
}));

vi.mock('@opentelemetry/core', () => ({
  W3CTraceContextPropagator: vi.fn(),
}));

vi.mock('@opentelemetry/resources', () => ({
  resourceFromAttributes: vi.fn(() => ({})),
}));

vi.mock('@opentelemetry/semantic-conventions', () => ({
  ATTR_SERVICE_NAME: 'service.name',
  ATTR_SERVICE_VERSION: 'service.version',
  ATTR_DEPLOYMENT_ENVIRONMENT: 'deployment.environment',
  ATTR_TELEMETRY_SDK_NAME: 'telemetry.sdk.name',
  ATTR_TELEMETRY_SDK_VERSION: 'telemetry.sdk.version',
  ATTR_TELEMETRY_SDK_LANGUAGE: 'telemetry.sdk.language',
}));

const createValidConfig = (): FoundationMetricsConfig => ({
  serviceName: 'test-service',
  collectorEndpoint: 'http://localhost:4318',
  environment: 'development',
  version: '1.0.0',
  signals: {
    errors: true,
    performance: true,
    network: true,
    userBehavior: true,
  },
  sampling: {
    defaultRate: 1.0,
    errorRate: 1.0,
    traceRate: 0.1,
    userBehaviorRate: 0.1,
  },
  compliance: {
    piiFields: ['email'],
    allowedFields: [],
    region: 'us',
    autoPiiDetection: true,
  },
});

describe('FoundationMetrics', () => {
  beforeEach(() => {
    // Reset singleton between tests
    vi.clearAllMocks();
  });

  afterEach(async () => {
    // Cleanup: shutdown if running, then reset module state for next test
    if (isInitialized()) {
      await FoundationMetrics.getInstance().shutdown();
    }
    resetMetricsStateForTesting();
  });

  describe('init', () => {
    it('should initialize with valid config', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      expect(sdk).toBeInstanceOf(FoundationMetrics);
      expect(isInitialized()).toBe(true);
    });

    it('should throw error if serviceName is missing', () => {
      const config = createValidConfig();
      delete (config as any).serviceName;

      expect(() => FoundationMetrics.init(config as any)).toThrow();
    });

    it('should throw error if collectorEndpoint is missing', () => {
      const config = createValidConfig();
      delete (config as any).collectorEndpoint;

      expect(() => FoundationMetrics.init(config as any)).toThrow();
    });

    it('should return existing instance if already initialized', () => {
      const config = createValidConfig();
      const sdk1 = FoundationMetrics.init(config);
      const sdk2 = FoundationMetrics.init(config);

      expect(sdk1).toBe(sdk2);
    });
  });

  describe('getInstance', () => {
    it('should throw if not initialized', async () => {
      // Ensure clean state
      if (isInitialized()) {
        await FoundationMetrics.getInstance().shutdown();
      }
      resetMetricsStateForTesting();

      expect(() => FoundationMetrics.getInstance()).toThrow('not initialized');
    });

    it('should return instance after initialization', () => {
      const config = createValidConfig();
      FoundationMetrics.init(config);

      const instance = FoundationMetrics.getInstance();
      expect(instance).toBeInstanceOf(FoundationMetrics);
    });
  });

  describe('captureError', () => {
    it('should capture an error', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      const error = new Error('Test error');

      // Should not throw
      expect(() => sdk.captureError(error)).not.toThrow();
    });

    it('should capture error with context', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      const error = new Error('Test error');

      expect(() =>
        sdk.captureError(error, {
          type: 'custom',
          componentName: 'TestComponent',
          metadata: { key: 'value' },
        }),
      ).not.toThrow();
    });
  });

  describe('startSpan', () => {
    it('should create a span', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      const span = sdk.startSpan('test-span');

      expect(span).toBeDefined();
      expect(typeof span.end).toBe('function');
    });

    it('should create a span with options', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      const span = sdk.startSpan('test-span', {
        kind: 'client',
        attributes: { foo: 'bar' },
      });

      expect(span).toBeDefined();
    });
  });

  describe('setUser', () => {
    it('should set user context', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      expect(() => sdk.setUser('user-123', { role: 'admin' })).not.toThrow();
    });
  });

  describe('setTenant', () => {
    it('should set tenant context', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      expect(() => sdk.setTenant('tenant-123', 'enterprise')).not.toThrow();
    });
  });

  describe('addBreadcrumb', () => {
    it('should add a breadcrumb', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      sdk.addBreadcrumb({
        category: 'navigation',
        message: 'User clicked button',
        timestamp: Date.now(),
      });

      const breadcrumbs = sdk.getBreadcrumbs();
      expect(breadcrumbs.length).toBe(1);
      expect(breadcrumbs[0].message).toBe('User clicked button');
    });

    it('should limit breadcrumbs to 100', () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      for (let i = 0; i < 150; i++) {
        sdk.addBreadcrumb({
          category: 'ui',
          message: `Breadcrumb ${i}`,
          timestamp: Date.now(),
        });
      }

      const breadcrumbs = sdk.getBreadcrumbs();
      expect(breadcrumbs.length).toBe(100);
    });
  });

  describe('flush', () => {
    it('should flush without error', async () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      await expect(sdk.flush()).resolves.not.toThrow();
    });
  });

  describe('shutdown', () => {
    it('should shutdown without error', async () => {
      const config = createValidConfig();
      const sdk = FoundationMetrics.init(config);

      await expect(sdk.shutdown()).resolves.not.toThrow();
      expect(isInitialized()).toBe(false);
      expect(getLifecycleState()).toBe('shutdown');
    });
  });

  describe('lifecycle state', () => {
    it('should start in uninitialized state', () => {
      expect(getLifecycleState()).toBe('uninitialized');
    });

    it('should transition to ready after init', () => {
      FoundationMetrics.init(createValidConfig());
      expect(getLifecycleState()).toBe('ready');
    });

    it('should throw on init() after shutdown', async () => {
      const sdk = FoundationMetrics.init(createValidConfig());
      await sdk.shutdown();

      expect(() => FoundationMetrics.init(createValidConfig())).toThrow('shut down');
    });

    it('should allow reinitialize() after shutdown', async () => {
      const sdk = FoundationMetrics.init(createValidConfig());
      await sdk.shutdown();
      expect(getLifecycleState()).toBe('shutdown');

      const newSdk = FoundationMetrics.reinitialize(createValidConfig());
      expect(newSdk).toBeInstanceOf(FoundationMetrics);
      expect(getLifecycleState()).toBe('ready');
    });
  });
});
