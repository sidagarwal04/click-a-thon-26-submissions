/**
 * Tests for AuthFacade
 *
 * Tests the identity-to-user mapping and facade lifecycle.
 */

import type { Identity } from '@ory/client-fetch';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  AuthConfig,
  FlowServiceInterface,
  SessionServiceInterface,
  UserServiceInterface,
} from '../core/types';
import { AuthFacade } from './auth-facade';

// =============================================================================
// Helpers
// =============================================================================

const createMockConfig = (overrides: Partial<AuthConfig> = {}): AuthConfig => ({
  ory: { kratosUrl: 'https://kratos.example.com' },
  ...overrides,
});

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

const createIdentity = (overrides: Partial<Identity> = {}): Identity =>
  ({
    id: 'identity-123',
    schema_id: 'default',
    schema_url: 'https://kratos.example.com/schemas/default',
    state: 'active',
    traits: {
      email: 'test@example.com',
      name: 'Test User',
      role: 'member',
    },
    verifiable_addresses: [
      {
        id: 'addr-1',
        value: 'test@example.com',
        verified: true,
        via: 'email',
        status: 'completed',
      },
    ],
    recovery_addresses: [
      {
        id: 'recovery-1',
        value: 'test@example.com',
        via: 'email',
      },
    ],
    ...overrides,
  } as Identity);

// =============================================================================
// Tests
// =============================================================================

describe('AuthFacade', () => {
  let facade: AuthFacade;
  let sessionService: SessionServiceInterface;
  let flowService: FlowServiceInterface;
  let userService: UserServiceInterface;
  let config: AuthConfig;

  beforeEach(() => {
    sessionService = createMockSessionService();
    flowService = createMockFlowService();
    userService = createMockUserService();
    config = createMockConfig();
    facade = new AuthFacade(sessionService, flowService, userService, config);
  });

  // ===========================================================================
  // Lifecycle
  // ===========================================================================

  describe('initialize', () => {
    it('should initialize session service', async () => {
      await facade.initialize();
      expect(sessionService.initialize).toHaveBeenCalledOnce();
    });

    it('should be idempotent', async () => {
      await facade.initialize();
      await facade.initialize();
      expect(sessionService.initialize).toHaveBeenCalledOnce();
    });
  });

  describe('dispose', () => {
    it('should mark as not initialized', async () => {
      await facade.initialize();
      await facade.dispose();

      // Re-initializing after dispose should work
      await facade.initialize();
      expect(sessionService.initialize).toHaveBeenCalledTimes(2);
    });

    it('should be idempotent', async () => {
      await facade.dispose();
      await facade.dispose();
      // Should not throw
    });
  });

  describe('service accessors', () => {
    it('should expose session service', () => {
      expect(facade.session).toBe(sessionService);
    });

    it('should expose flow service', () => {
      expect(facade.flow).toBe(flowService);
    });

    it('should expose user service', () => {
      expect(facade.user).toBe(userService);
    });
  });

  // ===========================================================================
  // mapIdentityToUser
  // ===========================================================================

  describe('mapIdentityToUser', () => {
    it('should map basic identity to AuthUser', () => {
      const identity = createIdentity();
      const user = facade.mapIdentityToUser(identity);

      expect(user.id).toBe('identity-123');
      expect(user.email).toBe('test@example.com');
      expect(user.name).toBe('Test User');
      expect(user.role).toBe('member');
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Email extraction
    // ─────────────────────────────────────────────────────────────────────────

    it('should extract email from traits', () => {
      const identity = createIdentity({
        traits: { email: 'from-traits@example.com' },
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.email).toBe('from-traits@example.com');
    });

    it('should fall back to verifiable_addresses for email', () => {
      const identity = createIdentity({
        traits: {},
        verifiable_addresses: [
          {
            id: 'a1',
            value: 'verified@example.com',
            verified: true,
            via: 'email',
            status: 'completed',
          },
        ],
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.email).toBe('verified@example.com');
    });

    it('should prefer email via over other verifiable addresses', () => {
      const identity = createIdentity({
        traits: {},
        verifiable_addresses: [
          { id: 'a1', value: '+1234567890', verified: true, via: 'sms', status: 'completed' },
          {
            id: 'a2',
            value: 'email@example.com',
            verified: true,
            via: 'email',
            status: 'completed',
          },
        ],
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.email).toBe('email@example.com');
    });

    it('should fall back to first verifiable address if no email via', () => {
      const identity = createIdentity({
        traits: {},
        verifiable_addresses: [
          { id: 'a1', value: 'first@example.com', verified: true, via: 'sms', status: 'completed' },
        ],
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.email).toBe('first@example.com');
    });

    it('should return empty string when no email source', () => {
      const identity = createIdentity({
        traits: {},
        verifiable_addresses: undefined,
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.email).toBe('');
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Name extraction
    // ─────────────────────────────────────────────────────────────────────────

    it('should extract name from traits.name', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com', name: 'Full Name' } });
      const user = facade.mapIdentityToUser(identity);
      expect(user.name).toBe('Full Name');
    });

    it('should build name from first + last name', () => {
      const identity = createIdentity({
        traits: { email: 'e@e.com', first_name: 'Alice', last_name: 'Smith' },
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.name).toBe('Alice Smith');
    });

    it('should return null when no name available', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com' } });
      const user = facade.mapIdentityToUser(identity);
      expect(user.name).toBeNull();
    });

    it('should extract firstName and lastName', () => {
      const identity = createIdentity({
        traits: { email: 'e@e.com', first_name: 'Bob', last_name: 'Jones' },
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.firstName).toBe('Bob');
      expect(user.lastName).toBe('Jones');
    });

    it('should derive firstName and lastName from full name', () => {
      const identity = createIdentity({
        traits: { email: 'e@e.com', name: 'Alice Marie Smith' },
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.firstName).toBe('Alice');
      expect(user.lastName).toBe('Marie Smith');
    });

    it('should handle single-word name', () => {
      const identity = createIdentity({
        traits: { email: 'e@e.com', name: 'Madonna' },
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.firstName).toBe('Madonna');
      expect(user.lastName).toBeNull();
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Role extraction
    // ─────────────────────────────────────────────────────────────────────────

    it('should extract valid role from traits', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com', role: 'admin' } });
      const user = facade.mapIdentityToUser(identity);
      expect(user.role).toBe('admin');
    });

    it('should default to viewer for invalid role', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com', role: 'superuser' as any } });
      const user = facade.mapIdentityToUser(identity);
      expect(user.role).toBe('viewer');
    });

    it('should default to viewer when role not set', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com' } });
      const user = facade.mapIdentityToUser(identity);
      expect(user.role).toBe('viewer');
    });

    it('should accept all valid roles', () => {
      const validRoles = ['owner', 'admin', 'member', 'viewer', 'guest'] as const;
      for (const role of validRoles) {
        const identity = createIdentity({ traits: { email: 'e@e.com', role } });
        const user = facade.mapIdentityToUser(identity);
        expect(user.role).toBe(role);
      }
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Permissions
    // ─────────────────────────────────────────────────────────────────────────

    it('should derive permissions from role', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com', role: 'owner' } });
      const user = facade.mapIdentityToUser(identity);
      expect(user.permissions.canManageUsers).toBe(true);
      expect(user.permissions.canManageTenant).toBe(true);
    });

    it('should have restricted permissions for viewer', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com' } }); // defaults to viewer
      const user = facade.mapIdentityToUser(identity);
      expect(user.permissions.canManageUsers).toBe(false);
      expect(user.permissions.canExportData).toBe(false);
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Email verification
    // ─────────────────────────────────────────────────────────────────────────

    it('should detect verified email', () => {
      const identity = createIdentity({
        traits: { email: 'test@example.com' },
        verifiable_addresses: [
          {
            id: 'a1',
            value: 'test@example.com',
            verified: true,
            via: 'email',
            status: 'completed',
          },
        ],
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.emailVerified).toBe(true);
    });

    it('should detect unverified email', () => {
      const identity = createIdentity({
        traits: { email: 'test@example.com' },
        verifiable_addresses: [
          { id: 'a1', value: 'test@example.com', verified: false, via: 'email', status: 'pending' },
        ],
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.emailVerified).toBe(false);
    });

    it('should be case-insensitive for email verification check', () => {
      const identity = createIdentity({
        traits: { email: 'TEST@Example.COM' },
        verifiable_addresses: [
          {
            id: 'a1',
            value: 'test@example.com',
            verified: true,
            via: 'email',
            status: 'completed',
          },
        ],
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.emailVerified).toBe(true);
    });

    it('should return false when no verifiable addresses', () => {
      const identity = createIdentity({
        traits: { email: 'test@example.com' },
        verifiable_addresses: undefined,
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.emailVerified).toBe(false);
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Other fields
    // ─────────────────────────────────────────────────────────────────────────

    it('should extract avatar URL', () => {
      const identity = createIdentity({
        traits: { email: 'e@e.com', avatar_url: 'https://img.example.com/pic.jpg' },
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.avatarUrl).toBe('https://img.example.com/pic.jpg');
    });

    it('should return null for missing avatar URL', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com' } });
      const user = facade.mapIdentityToUser(identity);
      expect(user.avatarUrl).toBeNull();
    });

    it('should extract tenant ID', () => {
      const identity = createIdentity({
        traits: { email: 'e@e.com', tenant_id: 'tenant-42' },
      });
      const user = facade.mapIdentityToUser(identity);
      expect(user.tenantId).toBe('tenant-42');
    });

    it('should return null for missing tenant ID', () => {
      const identity = createIdentity({ traits: { email: 'e@e.com' } });
      const user = facade.mapIdentityToUser(identity);
      expect(user.tenantId).toBeNull();
    });

    // ─────────────────────────────────────────────────────────────────────────
    // TypedIdentity conversion
    // ─────────────────────────────────────────────────────────────────────────

    it('should include typed identity in result', () => {
      const identity = createIdentity();
      const user = facade.mapIdentityToUser(identity);

      expect(user.identity.id).toBe('identity-123');
      expect(user.identity.schema_id).toBe('default');
      expect(user.identity.traits).toBeDefined();
    });

    it('should convert Date objects to ISO strings', () => {
      const now = new Date('2025-01-15T12:00:00Z');
      const identity = createIdentity({
        state_changed_at: now,
        created_at: now,
        updated_at: now,
      });
      const user = facade.mapIdentityToUser(identity);

      expect(user.identity.state_changed_at).toBe('2025-01-15T12:00:00.000Z');
      expect(user.identity.created_at).toBe('2025-01-15T12:00:00.000Z');
      expect(user.identity.updated_at).toBe('2025-01-15T12:00:00.000Z');
    });

    it('should handle traits with no properties gracefully', () => {
      const identity = createIdentity({ traits: {}, verifiable_addresses: undefined });
      const user = facade.mapIdentityToUser(identity);

      expect(user.email).toBe('');
      expect(user.name).toBeNull();
      expect(user.role).toBe('viewer');
    });

    it('should handle null traits gracefully', () => {
      const identity = createIdentity({ traits: null as any, verifiable_addresses: undefined });
      const user = facade.mapIdentityToUser(identity);

      expect(user.email).toBe('');
      expect(user.role).toBe('viewer');
    });
  });
});
