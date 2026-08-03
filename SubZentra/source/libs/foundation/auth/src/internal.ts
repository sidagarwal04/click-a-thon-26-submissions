/**
 * Internal Exports
 *
 * Internal APIs for advanced use cases and testing.
 * These exports are not part of the public API and may change without notice.
 *
 * @internal
 * @packageDocumentation
 */

// =============================================================================
// Ory Client
// =============================================================================

export {
  getOryClient,
  resetOryClient,
  hasOryClient,
  createOryClientConfig,
  type OryClientConfig,
  type OryClientInstance,
} from './core/ory-client';

// =============================================================================
// Container
// =============================================================================

export {
  AuthContainer,
  createAuthContainer,
  type AuthContainerDependencies,
  type AuthDependencyFactories,
  type AuthContainerConfig,
} from './core/container';

// =============================================================================
// Services
// =============================================================================

export { SessionService } from './services/session-service';
export { FlowService } from './services/flow-service';
export { UserService } from './services/user-service';

// =============================================================================
// Facade
// =============================================================================

export { AuthFacade } from './facade/auth-facade';
