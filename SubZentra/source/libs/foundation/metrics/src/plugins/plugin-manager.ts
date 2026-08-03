/**
 * Plugin Manager
 * @module plugins/plugin-manager
 */

import type {
  Breadcrumb,
  CapturedError,
  FoundationMetricsPlugin,
  InteractionEvent,
  PluginManager as IPluginManager,
  PluginHooks,
  PluginRegistrationOptions,
  PluginState,
  ResolvedConfig,
  TelemetryContext,
  WebVitalMetric,
} from '../types';

/**
 * Extended plugin manager with additional convenience methods
 */
export interface ExtendedPluginManager extends IPluginManager {
  initializeAll(config: ResolvedConfig): Promise<void>;
  shutdownAll(): Promise<void>;
  beforeCaptureError(
    error: CapturedError,
    context: TelemetryContext,
  ): Promise<CapturedError | null>;
  afterCaptureError(error: CapturedError): Promise<void>;
  beforeRecordWebVital(
    metric: WebVitalMetric,
    context: TelemetryContext,
  ): Promise<WebVitalMetric | null>;
  beforeTrackInteraction(
    event: InteractionEvent,
    context: TelemetryContext,
  ): Promise<InteractionEvent | null>;
  beforeAddBreadcrumb(breadcrumb: Breadcrumb): Promise<Breadcrumb | null>;
}

/**
 * Extract hooks from a plugin
 */
const extractHooks = (plugin: FoundationMetricsPlugin): PluginHooks => ({
  onInit: plugin.onInit,
  onShutdown: plugin.onShutdown,
  beforeCaptureError: plugin.beforeCaptureError,
  afterCaptureError: plugin.afterCaptureError,
  beforeRecordWebVital: plugin.beforeRecordWebVital,
  afterRecordWebVital: plugin.afterRecordWebVital,
  beforeRecordNetworkRequest: plugin.beforeRecordNetworkRequest,
  afterRecordNetworkRequest: plugin.afterRecordNetworkRequest,
  beforeTrackInteraction: plugin.beforeTrackInteraction,
  afterTrackInteraction: plugin.afterTrackInteraction,
  beforeAddBreadcrumb: plugin.beforeAddBreadcrumb,
  onContextUpdate: plugin.onContextUpdate,
  beforeExport: plugin.beforeExport,
});

/**
 * Create a plugin manager
 */
export const createPluginManager = (): ExtendedPluginManager => {
  const plugins = new Map<string, PluginState>();

  const register = (
    plugin: FoundationMetricsPlugin,
    options: PluginRegistrationOptions = {},
  ): void => {
    const { enabled = true } = options;

    if (plugins.has(plugin.name)) {
      console.warn(`[FoundationMetrics] Plugin "${plugin.name}" already registered`);
      return;
    }

    const state: PluginState = {
      metadata: {
        name: plugin.name,
        version: plugin.version,
        description: plugin.description,
        author: plugin.author,
        homepage: plugin.homepage,
      },
      enabled,
      initialized: false,
      hooks: extractHooks(plugin),
    };

    plugins.set(plugin.name, state);
  };

  const unregister = (name: string): void => {
    const state = plugins.get(name);
    if (state?.hooks.onShutdown) {
      try {
        state.hooks.onShutdown();
      } catch (e) {
        console.error(`[FoundationMetrics] Error shutting down plugin "${name}":`, e);
      }
    }
    plugins.delete(name);
  };

  const get = (name: string): PluginState | undefined => plugins.get(name);

  const getAll = (): PluginState[] => Array.from(plugins.values());

  const has = (name: string): boolean => plugins.has(name);

  const initializeAll = async (config: ResolvedConfig): Promise<void> => {
    for (const [name, state] of plugins.entries()) {
      if (!state.enabled || state.initialized) {
        continue;
      }

      try {
        if (state.hooks.onInit) {
          await state.hooks.onInit(config);
        }
        state.initialized = true;
      } catch (e) {
        console.error(`[FoundationMetrics] Error initializing plugin "${name}":`, e);
        state.initError = e instanceof Error ? e : new Error(String(e));
      }
    }
  };

  const shutdownAll = async (): Promise<void> => {
    for (const [name, state] of plugins.entries()) {
      if (!state.initialized) {
        continue;
      }

      try {
        if (state.hooks.onShutdown) {
          await state.hooks.onShutdown();
        }
        state.initialized = false;
      } catch (e) {
        console.error(`[FoundationMetrics] Error shutting down plugin "${name}":`, e);
      }
    }
  };

  const beforeCaptureError = async (
    error: CapturedError,
    context: TelemetryContext,
  ): Promise<CapturedError | null> => {
    let current = error;

    for (const state of plugins.values()) {
      if (!state.enabled || !state.initialized || !state.hooks.beforeCaptureError) {
        continue;
      }

      try {
        const result = await state.hooks.beforeCaptureError(current, context);
        if (result === null) {
          return null;
        }
        current = result;
      } catch (e) {
        console.error('[FoundationMetrics] Error in beforeCaptureError hook:', e);
      }
    }

    return current;
  };

  const afterCaptureError = async (error: CapturedError): Promise<void> => {
    for (const state of plugins.values()) {
      if (!state.enabled || !state.initialized || !state.hooks.afterCaptureError) {
        continue;
      }

      try {
        state.hooks.afterCaptureError(error);
      } catch (e) {
        console.error('[FoundationMetrics] Error in afterCaptureError hook:', e);
      }
    }
  };

  const beforeRecordWebVital = async (
    metric: WebVitalMetric,
    context: TelemetryContext,
  ): Promise<WebVitalMetric | null> => {
    let current = metric;

    for (const state of plugins.values()) {
      if (!state.enabled || !state.initialized || !state.hooks.beforeRecordWebVital) {
        continue;
      }

      try {
        const result = await state.hooks.beforeRecordWebVital(current, context);
        if (result === null) {
          return null;
        }
        current = result;
      } catch (e) {
        console.error('[FoundationMetrics] Error in beforeRecordWebVital hook:', e);
      }
    }

    return current;
  };

  const beforeTrackInteraction = async (
    event: InteractionEvent,
    context: TelemetryContext,
  ): Promise<InteractionEvent | null> => {
    let current = event;

    for (const state of plugins.values()) {
      if (!state.enabled || !state.initialized || !state.hooks.beforeTrackInteraction) {
        continue;
      }

      try {
        const result = await state.hooks.beforeTrackInteraction(current, context);
        if (result === null) {
          return null;
        }
        current = result;
      } catch (e) {
        console.error('[FoundationMetrics] Error in beforeTrackInteraction hook:', e);
      }
    }

    return current;
  };

  const beforeAddBreadcrumb = async (breadcrumb: Breadcrumb): Promise<Breadcrumb | null> => {
    let current = breadcrumb;

    for (const state of plugins.values()) {
      if (!state.enabled || !state.initialized || !state.hooks.beforeAddBreadcrumb) {
        continue;
      }

      try {
        const result = await state.hooks.beforeAddBreadcrumb(current);
        if (result === null) {
          return null;
        }
        current = result;
      } catch (e) {
        console.error('[FoundationMetrics] Error in beforeAddBreadcrumb hook:', e);
      }
    }

    return current;
  };

  return {
    register,
    unregister,
    get,
    getAll,
    has,
    initializeAll,
    shutdownAll,
    beforeCaptureError,
    afterCaptureError,
    beforeRecordWebVital,
    beforeTrackInteraction,
    beforeAddBreadcrumb,
  };
};

// Default plugin manager instance
let defaultManager: ExtendedPluginManager | null = null;

/**
 * Get the default plugin manager
 */
export const getPluginManager = (): ExtendedPluginManager => {
  if (!defaultManager) {
    defaultManager = createPluginManager();
  }
  return defaultManager;
};

/**
 * Reset the default plugin manager
 */
export const resetPluginManager = (): void => {
  if (defaultManager) {
    defaultManager.shutdownAll();
  }
  defaultManager = null;
};
