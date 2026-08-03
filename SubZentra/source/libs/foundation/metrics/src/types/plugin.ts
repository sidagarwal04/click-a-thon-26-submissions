/**
 * Plugin System Type Definitions
 * @module types/plugin
 */

import type { FoundationMetricsConfig, ResolvedConfig } from './config';
import type { TelemetryContext } from './context';
import type {
  Breadcrumb,
  CapturedError,
  InteractionEvent,
  NetworkRequest,
  WebVitalMetric,
} from './signals';

/**
 * Plugin lifecycle hooks
 */
export interface PluginHooks {
  onInit?(config: ResolvedConfig): void | Promise<void>;
  onShutdown?(): void | Promise<void>;
  beforeCaptureError?(
    error: CapturedError,
    context: TelemetryContext,
  ): CapturedError | null | Promise<CapturedError | null>;
  afterCaptureError?(error: CapturedError): void;
  beforeRecordWebVital?(
    metric: WebVitalMetric,
    context: TelemetryContext,
  ): WebVitalMetric | null | Promise<WebVitalMetric | null>;
  afterRecordWebVital?(metric: WebVitalMetric): void;
  beforeRecordNetworkRequest?(
    request: NetworkRequest,
    context: TelemetryContext,
  ): NetworkRequest | null | Promise<NetworkRequest | null>;
  afterRecordNetworkRequest?(request: NetworkRequest): void;
  beforeTrackInteraction?(
    event: InteractionEvent,
    context: TelemetryContext,
  ): InteractionEvent | null | Promise<InteractionEvent | null>;
  afterTrackInteraction?(event: InteractionEvent): void;
  beforeAddBreadcrumb?(breadcrumb: Breadcrumb): Breadcrumb | null | Promise<Breadcrumb | null>;
  onContextUpdate?(context: TelemetryContext): void;
  beforeExport?(data: unknown): unknown | Promise<unknown>;
}

/**
 * Plugin metadata
 */
export interface PluginMetadata {
  name: string;
  version: string;
  description?: string;
  author?: string;
  homepage?: string;
}

/**
 * Plugin interface
 */
export interface FoundationMetricsPlugin extends PluginMetadata, PluginHooks {
  setup?(config: FoundationMetricsConfig): FoundationMetricsConfig | void;
}

/**
 * Plugin registration options
 */
export interface PluginRegistrationOptions {
  enabled?: boolean;
  options?: Record<string, unknown>;
}

/**
 * Plugin state
 */
export interface PluginState {
  metadata: PluginMetadata;
  enabled: boolean;
  initialized: boolean;
  hooks: PluginHooks;
  initError?: Error;
}

/**
 * Plugin manager interface
 */
export interface PluginManager {
  register(plugin: FoundationMetricsPlugin, options?: PluginRegistrationOptions): void;
  unregister(name: string): void;
  get(name: string): PluginState | undefined;
  getAll(): PluginState[];
  has(name: string): boolean;
}

/**
 * Plugin factory function type
 */
export type PluginFactory<TOptions = Record<string, unknown>> = (
  options?: TOptions,
) => FoundationMetricsPlugin;

/**
 * Async plugin factory function type
 */
export type AsyncPluginFactory<TOptions = Record<string, unknown>> = (
  options?: TOptions,
) => Promise<FoundationMetricsPlugin>;
