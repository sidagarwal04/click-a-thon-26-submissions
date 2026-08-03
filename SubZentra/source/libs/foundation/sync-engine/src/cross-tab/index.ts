/**
 * Cross-tab synchronization exports
 * @module cross-tab
 *
 * NOTE: CrossTabMessageType, CrossTabMessage, and CrossTabMessageHandler types
 * should be imported directly from @open-zentra/foundation-data-model
 */

export {
  CrossTabManager,
  getCrossTabManager,
  resetCrossTabManager,
  createCrossTabManager,
  CrossTabMessageSchema,
  type CrossTabManagerConfig,
} from './manager';
