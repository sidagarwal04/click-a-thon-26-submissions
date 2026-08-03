/**
 * Provider exports
 * @module provider
 */

// Provider component
export { DataLayerProvider, type DataLayerProviderProps } from './data-layer-provider';

// Public context and hook
export { DataLayerContext, useDataLayer } from './data-layer-context';

// Internals context and hook (advanced integrations such as query-engine)
export {
  DataLayerInternalsContext,
  useDataLayerInternals,
  type DataLayerInternals,
} from './data-layer-internals-context';

export type { DataLayerConfig, DataLayerContextValue } from '../core/types';
