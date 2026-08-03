/**
 * OpenTelemetry Provider - Singleton Class
 * @module core/otel-provider
 */

import {
  context,
  diag,
  DiagConsoleLogger,
  DiagLogLevel,
  metrics,
  propagation,
  trace,
  type Counter,
  type Meter,
  type Tracer,
} from '@opentelemetry/api';
import type { Histogram } from '@opentelemetry/api';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { W3CTraceContextPropagator } from '@opentelemetry/core';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { resourceFromAttributes, type Resource } from '@opentelemetry/resources';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { BatchSpanProcessor, WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
  ATTR_TELEMETRY_SDK_LANGUAGE,
  ATTR_TELEMETRY_SDK_NAME,
  ATTR_TELEMETRY_SDK_VERSION,
} from '@opentelemetry/semantic-conventions';

import { detectBrowser } from '@open-zentra/foundation-utils';

import type { ResolvedConfig, ResourceAttributes } from '../types';

const SDK_NAME = '@open-zentra/foundation-metrics';
const SDK_VERSION = '0.0.1';

/**
 * OpenTelemetry Provider Singleton
 *
 * Manages OpenTelemetry tracer/meter providers and provides instrument caching
 * for histograms and counters to avoid re-creating instruments.
 */
export class OTelProvider {
  private static instance: OTelProvider | null = null;

  private tracer: Tracer;
  private meter: Meter;
  private tracerProvider: WebTracerProvider;
  private meterProvider: MeterProvider;
  private histogramCache = new Map<string, Histogram>();
  private counterCache = new Map<string, Counter>();

  private constructor(config: ResolvedConfig) {
    // Enable debug logging in development
    if (config.debug) {
      diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);
    }

    // Create resource with service info and browser attributes
    const resource = this.createResource(config);

    // Initialize trace provider
    this.tracerProvider = this.createTracerProvider(config, resource);

    // Initialize meter provider
    this.meterProvider = this.createMeterProvider(config, resource);

    // Set up context propagation
    this.setupContextPropagation();

    // Get tracer and meter instances
    this.tracer = trace.getTracer(SDK_NAME, SDK_VERSION);
    this.meter = metrics.getMeter(SDK_NAME, SDK_VERSION);
  }

  /**
   * Initialize the OTelProvider singleton
   */
  static initialize = (config: ResolvedConfig): OTelProvider => {
    if (OTelProvider.instance) {
      return OTelProvider.instance;
    }

    OTelProvider.instance = new OTelProvider(config);
    return OTelProvider.instance;
  };

  /**
   * Get the singleton instance
   */
  static getInstance = (): OTelProvider => {
    if (!OTelProvider.instance) {
      throw new Error('OTelProvider not initialized. Call OTelProvider.initialize() first.');
    }
    return OTelProvider.instance;
  };

  /**
   * Check if the provider is initialized
   */
  static isInitialized = (): boolean => {
    return OTelProvider.instance !== null;
  };

  /**
   * Get current tracer instance
   */
  getTracer = (): Tracer => {
    return this.tracer;
  };

  /**
   * Get current meter instance
   */
  getMeter = (): Meter => {
    return this.meter;
  };

  /**
   * Get current active context
   */
  getContext = () => {
    return context.active();
  };

  /**
   * Get underlying tracer provider
   */
  getTracerProvider = (): WebTracerProvider => {
    return this.tracerProvider;
  };

  /**
   * Get underlying meter provider
   */
  getMeterProvider = (): MeterProvider => {
    return this.meterProvider;
  };

  /**
   * Get or create a cached histogram instrument
   */
  getOrCreateHistogram = (
    name: string,
    options?: { description?: string; unit?: string },
  ): Histogram => {
    const cached = this.histogramCache.get(name);
    if (cached) {
      return cached;
    }

    const histogram = this.meter.createHistogram(name, options);
    this.histogramCache.set(name, histogram);
    return histogram;
  };

  /**
   * Get or create a cached counter instrument
   */
  getOrCreateCounter = (
    name: string,
    options?: { description?: string; unit?: string },
  ): Counter => {
    const cached = this.counterCache.get(name);
    if (cached) {
      return cached;
    }

    const counter = this.meter.createCounter(name, options);
    this.counterCache.set(name, counter);
    return counter;
  };

  /**
   * Shutdown all providers
   */
  shutdown = async (): Promise<void> => {
    await Promise.all([this.tracerProvider.shutdown(), this.meterProvider.shutdown()]);

    this.histogramCache.clear();
    this.counterCache.clear();
    OTelProvider.instance = null;
  };

  /**
   * Force flush all providers
   */
  flush = async (): Promise<void> => {
    await Promise.all([this.tracerProvider.forceFlush(), this.meterProvider.forceFlush()]);
  };

  // ==========================================
  // Private Methods
  // ==========================================

  /**
   * Create OpenTelemetry resource
   */
  private createResource = (config: ResolvedConfig): Resource => {
    const browserInfo = detectBrowser();

    const attributes: ResourceAttributes = {
      [ATTR_SERVICE_NAME]: config.serviceName,
      [ATTR_SERVICE_VERSION]: config.version,
      'deployment.environment': config.environment,
      [ATTR_TELEMETRY_SDK_NAME]: SDK_NAME,
      [ATTR_TELEMETRY_SDK_VERSION]: SDK_VERSION,
      [ATTR_TELEMETRY_SDK_LANGUAGE]: 'webjs',
      'browser.name': browserInfo.name,
      'browser.version': browserInfo.version,
      'browser.platform': browserInfo.platform,
      'browser.language': browserInfo.language,
      'user_agent.original': browserInfo.userAgent,
      'device.type': browserInfo.deviceType,
      'os.name': browserInfo.os,
      'os.version': browserInfo.osVersion,
      ...config.resourceAttributes,
    };

    return resourceFromAttributes(attributes);
  };

  /**
   * Create and configure tracer provider
   */
  private createTracerProvider = (
    config: ResolvedConfig,
    resource: Resource,
  ): WebTracerProvider => {
    // Configure OTLP trace exporter
    const traceExporter = new OTLPTraceExporter({
      url: `${config.collectorEndpoint}/v1/traces`,
      headers: {},
      timeoutMillis: config.transport.timeout,
    });

    const tracerProvider = new WebTracerProvider({
      resource,
      spanProcessors: [
        new BatchSpanProcessor(traceExporter, {
          maxQueueSize: config.transport.maxQueueSize,
          maxExportBatchSize: config.transport.batchSize,
          scheduledDelayMillis: config.transport.flushInterval,
        }),
      ],
    });

    // Register as global tracer provider
    tracerProvider.register({
      contextManager: new ZoneContextManager(),
      propagator: new W3CTraceContextPropagator(),
    });

    return tracerProvider;
  };

  /**
   * Create and configure meter provider
   */
  private createMeterProvider = (config: ResolvedConfig, resource: Resource): MeterProvider => {
    // Configure OTLP metric exporter
    const metricExporter = new OTLPMetricExporter({
      url: `${config.collectorEndpoint}/v1/metrics`,
      headers: {},
      timeoutMillis: config.transport.timeout,
    });

    const meterProvider = new MeterProvider({
      resource,
      readers: [
        new PeriodicExportingMetricReader({
          exporter: metricExporter,
          exportIntervalMillis: config.transport.flushInterval,
        }),
      ],
    });

    // Register as global meter provider
    metrics.setGlobalMeterProvider(meterProvider);

    return meterProvider;
  };

  /**
   * Set up context propagation
   */
  private setupContextPropagation = (): void => {
    propagation.setGlobalPropagator(new W3CTraceContextPropagator());
  };
}

/**
 * OpenTelemetry provider state
 */
export interface OTelProviderState {
  tracer: Tracer;
  meter: Meter;
  tracerProvider: WebTracerProvider;
  meterProvider: MeterProvider;
  isInitialized: boolean;
}

const getProviderOrThrow = (): OTelProvider => OTelProvider.getInstance();

/**
 * Initialize OpenTelemetry providers
 */
export const initializeOTelProviders = (config: ResolvedConfig): OTelProviderState => {
  const provider = OTelProvider.initialize(config);
  return {
    tracer: provider.getTracer(),
    meter: provider.getMeter(),
    tracerProvider: provider.getTracerProvider(),
    meterProvider: provider.getMeterProvider(),
    isInitialized: true,
  };
};

/**
 * Get current tracer instance
 */
export const getTracer = (): Tracer => getProviderOrThrow().getTracer();

/**
 * Get current meter instance
 */
export const getMeter = (): Meter => getProviderOrThrow().getMeter();

/**
 * Get current context
 */
export const getContext = () => getProviderOrThrow().getContext();

/**
 * Shutdown all providers
 */
export const shutdownProviders = async (): Promise<void> => {
  if (!OTelProvider.isInitialized()) {
    return;
  }
  await getProviderOrThrow().shutdown();
};

/**
 * Force flush all providers
 */
export const flushProviders = async (): Promise<void> => {
  if (!OTelProvider.isInitialized()) {
    return;
  }
  await getProviderOrThrow().flush();
};

/**
 * Check if providers are initialized
 */
export const isInitialized = (): boolean => OTelProvider.isInitialized();
