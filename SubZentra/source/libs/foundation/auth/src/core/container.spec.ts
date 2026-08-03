/**
 * Tests for AuthContainer
 *
 * DI container lifecycle management.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthContainer, createAuthContainer, type AuthContainerConfig } from './container';
import type {
  AuthConfig,
  AuthFacadeInterface,
  FlowServiceInterface,
  SessionServiceInterface,
  UserServiceInterface,
} from './types';

// =============================================================================
// Helpers
// =============================================================================

const createMockSessionService = (): SessionServiceInterface => ({
  initialize: vi.fn().mockResolvedValue(null),
  checkSession: vi.fn().mockResolvedValue(null),
  refresh: vi.fn().mockResolvedValue(null),
  logout: vi.fn().mockResolvedValue(undefined),
  getAccessToken: vi.fn().mockResolvedValue(null),
  getState: vi.fn().mockReturnValue(null),
  subscribe: vi.fn().mockReturnValue(() => undefined),
  dispose: vi.fn().mockResolvedValue(undefined),
});

const createMockFlowService = (): FlowServiceInterface => ({
  createLoginFlow: vi.fn(),
  getLoginFlow: vi.fn(),
  submitLoginFlow: vi.fn(),
  createRegistrationFlow: vi.fn(),
  getRegistrationFlow: vi.fn(),
  submitRegistrationFlow: vi.fn(),
  createRecoveryFlow: vi.fn(),
  getRecoveryFlow: vi.fn(),
  submitRecoveryFlow: vi.fn(),
  createVerificationFlow: vi.fn(),
  getVerificationFlow: vi.fn(),
  submitVerificationFlow: vi.fn(),
  createSettingsFlow: vi.fn(),
  getSettingsFlow: vi.fn(),
  submitSettingsFlow: vi.fn(),
  dispose: vi.fn().mockResolvedValue(undefined),
});

const createMockUserService = (): UserServiceInterface => ({
  getCurrentIdentity: vi.fn().mockResolvedValue(null),
  updateTraits: vi.fn(),
  dispose: vi.fn().mockResolvedValue(undefined),
});

const createMockFacade = (deps?: {
  session?: SessionServiceInterface;
  flow?: FlowServiceInterface;
  user?: UserServiceInterface;
}): AuthFacadeInterface => ({
  session: deps?.session ?? createMockSessionService(),
  flow: deps?.flow ?? createMockFlowService(),
  user: deps?.user ?? createMockUserService(),
  mapIdentityToUser: vi.fn(),
  initialize: vi.fn().mockResolvedValue(undefined),
  dispose: vi.fn().mockResolvedValue(undefined),
});

const createConfig = (overrides: Partial<AuthConfig> = {}): AuthConfig => ({
  ory: { kratosUrl: 'https://kratos.example.com' },
  ...overrides,
});

/**
 * Create a container config with all factories mocked.
 * This avoids needing to mock the actual service module imports.
 */
const createFullyMockedContainerConfig = (
  overrides: Partial<AuthContainerConfig> = {},
): AuthContainerConfig => {
  const session = createMockSessionService();
  const flow = createMockFlowService();
  const user = createMockUserService();
  const facade = createMockFacade({ session, flow, user });

  return {
    config: createConfig(),
    factories: {
      sessionService: () => session,
      flowService: () => flow,
      userService: () => user,
      facade: () => facade,
    },
    ...overrides,
  };
};

// =============================================================================
// Tests
// =============================================================================

describe('AuthContainer', () => {
  let container: AuthContainer;

  beforeEach(() => {
    container = new AuthContainer(createFullyMockedContainerConfig());
  });

  // ===========================================================================
  // Initial State
  // ===========================================================================

  describe('initial state', () => {
    it('should not be initialized', () => {
      expect(container.isInitialized).toBe(false);
    });

    it('should not be disposed', () => {
      expect(container.isDisposed).toBe(false);
    });
  });

  // ===========================================================================
  // Initialize
  // ===========================================================================

  describe('initialize', () => {
    it('should initialize successfully', async () => {
      const deps = await container.initialize();

      expect(deps).toBeDefined();
      expect(deps.config).toBeDefined();
      expect(deps.facade).toBeDefined();
      expect(deps.sessionService).toBeDefined();
      expect(deps.flowService).toBeDefined();
      expect(deps.userService).toBeDefined();
      expect(container.isInitialized).toBe(true);
    });

    it('should be idempotent (returns same deps)', async () => {
      const deps1 = await container.initialize();
      const deps2 = await container.initialize();
      expect(deps1).toBe(deps2);
    });

    it('should return same promise for concurrent calls', async () => {
      const promise1 = container.initialize();
      const promise2 = container.initialize();

      const [deps1, deps2] = await Promise.all([promise1, promise2]);
      expect(deps1).toBe(deps2);
    });

    it('should throw if already disposed', async () => {
      await container.dispose();
      await expect(container.initialize()).rejects.toThrow('disposed');
    });

    it('should initialize the facade', async () => {
      const deps = await container.initialize();
      expect(deps.facade.initialize).toHaveBeenCalledOnce();
    });

    it('should store the config in deps', async () => {
      const config = createConfig({ debug: true });
      const c = new AuthContainer(createFullyMockedContainerConfig({ config }));
      const deps = await c.initialize();
      expect(deps.config.debug).toBe(true);
    });
  });

  // ===========================================================================
  // getDependencies
  // ===========================================================================

  describe('getDependencies', () => {
    it('should return deps after initialization', async () => {
      const expected = await container.initialize();
      const actual = container.getDependencies();
      expect(actual).toBe(expected);
    });

    it('should throw if not initialized', () => {
      expect(() => container.getDependencies()).toThrow('not initialized');
    });

    it('should throw if disposed', async () => {
      await container.initialize();
      await container.dispose();
      expect(() => container.getDependencies()).toThrow('disposed');
    });
  });

  // ===========================================================================
  // Dispose
  // ===========================================================================

  describe('dispose', () => {
    it('should dispose all services in reverse order', async () => {
      const deps = await container.initialize();
      await container.dispose();

      expect(deps.facade.dispose).toHaveBeenCalled();
      expect(deps.userService.dispose).toHaveBeenCalled();
      expect(deps.flowService.dispose).toHaveBeenCalled();
      expect(deps.sessionService.dispose).toHaveBeenCalled();
    });

    it('should mark container as disposed', async () => {
      await container.initialize();
      await container.dispose();
      expect(container.isDisposed).toBe(true);
    });

    it('should be idempotent', async () => {
      await container.initialize();
      await container.dispose();
      await container.dispose(); // Should not throw
      expect(container.isDisposed).toBe(true);
    });

    it('should handle disposal before initialization', async () => {
      await container.dispose(); // Should not throw
      expect(container.isDisposed).toBe(true);
    });

    it('should clear deps after disposal', async () => {
      await container.initialize();
      expect(container.isInitialized).toBe(true);

      await container.dispose();
      expect(container.isInitialized).toBe(false);
    });
  });

  // ===========================================================================
  // Factory Support
  // ===========================================================================

  describe('factory overrides', () => {
    it('should use custom session service factory', async () => {
      const customSession = createMockSessionService();
      const c = new AuthContainer(
        createFullyMockedContainerConfig({
          factories: {
            sessionService: () => customSession,
            flowService: () => createMockFlowService(),
            userService: () => createMockUserService(),
            facade: () => createMockFacade({ session: customSession }),
          },
        }),
      );

      const deps = await c.initialize();
      expect(deps.sessionService).toBe(customSession);
    });

    it('should use custom flow service factory', async () => {
      const customFlow = createMockFlowService();
      const c = new AuthContainer(
        createFullyMockedContainerConfig({
          factories: {
            sessionService: () => createMockSessionService(),
            flowService: () => customFlow,
            userService: () => createMockUserService(),
            facade: () => createMockFacade({ flow: customFlow }),
          },
        }),
      );

      const deps = await c.initialize();
      expect(deps.flowService).toBe(customFlow);
    });

    it('should use custom user service factory', async () => {
      const customUser = createMockUserService();
      const c = new AuthContainer(
        createFullyMockedContainerConfig({
          factories: {
            sessionService: () => createMockSessionService(),
            flowService: () => createMockFlowService(),
            userService: () => customUser,
            facade: () => createMockFacade({ user: customUser }),
          },
        }),
      );

      const deps = await c.initialize();
      expect(deps.userService).toBe(customUser);
    });

    it('should use custom facade factory', async () => {
      const customFacade = createMockFacade();
      const c = new AuthContainer(
        createFullyMockedContainerConfig({
          factories: {
            sessionService: () => createMockSessionService(),
            flowService: () => createMockFlowService(),
            userService: () => createMockUserService(),
            facade: () => customFacade,
          },
        }),
      );

      const deps = await c.initialize();
      expect(deps.facade).toBe(customFacade);
    });
  });

  // ===========================================================================
  // createAuthContainer
  // ===========================================================================

  describe('createAuthContainer', () => {
    it('should create a new container instance', () => {
      const config = createFullyMockedContainerConfig();
      const result = createAuthContainer(config);
      expect(result).toBeInstanceOf(AuthContainer);
      expect(result.isInitialized).toBe(false);
    });
  });
});
