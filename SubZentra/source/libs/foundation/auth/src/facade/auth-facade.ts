/**
 * Auth Facade
 *
 * Unified facade for authentication operations.
 *
 * @module facade/auth-facade
 */

import type { Identity } from '@ory/client-fetch';

import { IDENTITY_TRAIT } from '../core/constants';
import {
  getUserPermissions,
  isValidRole,
  type AuthConfig,
  type AuthFacadeInterface,
  type AuthUser,
  type FlowServiceInterface,
  type IdentityTraits,
  type SessionServiceInterface,
  type TypedIdentity,
  type UserRole,
  type UserServiceInterface,
} from '../core/types';

// =============================================================================
// Default Role
// =============================================================================

/**
 * Default role for users without explicit role
 */
const DEFAULT_USER_ROLE: UserRole = 'viewer';

// =============================================================================
// Auth Facade
// =============================================================================

/**
 * Auth facade implementation
 *
 * Provides a unified interface for authentication operations,
 * coordinating between session, flow, and user services.
 */
export class AuthFacade implements AuthFacadeInterface {
  readonly session: SessionServiceInterface;
  readonly flow: FlowServiceInterface;
  readonly user: UserServiceInterface;

  private readonly config: AuthConfig;
  private initialized = false;

  constructor(
    sessionService: SessionServiceInterface,
    flowService: FlowServiceInterface,
    userService: UserServiceInterface,
    config: AuthConfig,
  ) {
    this.session = sessionService;
    this.flow = flowService;
    this.user = userService;
    this.config = config;
  }

  /**
   * Initialize the facade
   */
  initialize = async (): Promise<void> => {
    if (this.initialized) return;

    // Initialize session service (checks current session)
    await this.session.initialize();

    this.initialized = true;

    if (this.config.debug) {
      console.debug('[AuthFacade] Initialized');
    }
  };

  /**
   * Dispose the facade
   */
  dispose = async (): Promise<void> => {
    if (!this.initialized) return;

    // Services are disposed by the container, not the facade
    this.initialized = false;

    if (this.config.debug) {
      console.debug('[AuthFacade] Disposed');
    }
  };

  /**
   * Map Ory identity to AuthUser
   *
   * Extracts user information from Ory identity traits
   * and derives permissions from the user's role.
   */
  mapIdentityToUser = (identity: Identity): AuthUser => {
    const traits = (identity.traits ?? {}) as IdentityTraits;

    // Extract basic user info from traits
    const email = this.extractEmail(identity, traits);
    const name = this.extractName(traits);
    const { firstName, lastName } = this.extractNames(traits);
    const avatarUrl = traits[IDENTITY_TRAIT.AVATAR_URL] ?? null;
    const role = this.extractRole(traits);
    const tenantId = traits[IDENTITY_TRAIT.TENANT_ID] ?? null;

    // Check email verification status
    const emailVerified = this.isEmailVerified(identity, email);

    // Get permissions for the role
    const permissions = getUserPermissions(role);

    return {
      id: identity.id,
      email,
      name,
      firstName,
      lastName,
      avatarUrl,
      role,
      tenantId,
      permissions,
      emailVerified,
      identity: this.convertToTypedIdentity(identity, traits),
    };
  };

  /**
   * Convert Ory identity to TypedIdentity with string dates
   */
  private convertToTypedIdentity = (identity: Identity, traits: IdentityTraits): TypedIdentity => ({
    id: identity.id,
    schema_id: identity.schema_id,
    schema_url: identity.schema_url,
    state: identity.state,
    state_changed_at:
      identity.state_changed_at instanceof Date
        ? identity.state_changed_at.toISOString()
        : identity.state_changed_at,
    traits,
    verifiable_addresses: identity.verifiable_addresses?.map((addr) => ({
      id: addr.id,
      value: addr.value,
      verified: addr.verified,
      via: addr.via,
      status: addr.status,
      verified_at:
        addr.verified_at instanceof Date ? addr.verified_at.toISOString() : addr.verified_at,
      created_at: addr.created_at instanceof Date ? addr.created_at.toISOString() : addr.created_at,
      updated_at: addr.updated_at instanceof Date ? addr.updated_at.toISOString() : addr.updated_at,
    })),
    recovery_addresses: identity.recovery_addresses?.map((addr) => ({
      id: addr.id,
      value: addr.value,
      via: addr.via,
      created_at: addr.created_at instanceof Date ? addr.created_at.toISOString() : addr.created_at,
      updated_at: addr.updated_at instanceof Date ? addr.updated_at.toISOString() : addr.updated_at,
    })),
    metadata_public: identity.metadata_public as Record<string, unknown> | undefined,
    metadata_admin: identity.metadata_admin as Record<string, unknown> | undefined,
    created_at:
      identity.created_at instanceof Date ? identity.created_at.toISOString() : identity.created_at,
    updated_at:
      identity.updated_at instanceof Date ? identity.updated_at.toISOString() : identity.updated_at,
  });

  // ==========================================================================
  // Private Methods
  // ==========================================================================

  /**
   * Extract email from identity
   */
  private extractEmail = (identity: Identity, traits: IdentityTraits): string => {
    // First try traits
    const traitEmail = traits[IDENTITY_TRAIT.EMAIL];
    if (typeof traitEmail === 'string' && traitEmail) {
      return traitEmail;
    }

    // Then try verifiable addresses
    if (identity.verifiable_addresses && identity.verifiable_addresses.length > 0) {
      const emailAddress = identity.verifiable_addresses.find((addr) => addr.via === 'email');
      if (emailAddress) {
        return emailAddress.value;
      }
      // Fallback to first address
      return identity.verifiable_addresses[0].value;
    }

    // Fallback to empty string (shouldn't happen in practice)
    return '';
  };

  /**
   * Extract display name from traits
   */
  private extractName = (traits: IdentityTraits): string | null => {
    // First check for explicit name trait
    const name = traits[IDENTITY_TRAIT.NAME];
    if (typeof name === 'string' && name) {
      return name;
    }

    // Build from first + last name
    const firstName = traits[IDENTITY_TRAIT.FIRST_NAME];
    const lastName = traits[IDENTITY_TRAIT.LAST_NAME];

    if (typeof firstName === 'string' || typeof lastName === 'string') {
      const parts: string[] = [];
      if (typeof firstName === 'string' && firstName) parts.push(firstName);
      if (typeof lastName === 'string' && lastName) parts.push(lastName);
      return parts.length > 0 ? parts.join(' ') : null;
    }

    return null;
  };

  /**
   * Extract first and last names from traits
   */
  private extractNames = (
    traits: IdentityTraits,
  ): { firstName: string | null; lastName: string | null } => {
    let firstName: string | null = null;
    let lastName: string | null = null;

    // Direct traits
    const traitFirstName = traits[IDENTITY_TRAIT.FIRST_NAME];
    const traitLastName = traits[IDENTITY_TRAIT.LAST_NAME];

    if (typeof traitFirstName === 'string' && traitFirstName) {
      firstName = traitFirstName;
    }
    if (typeof traitLastName === 'string' && traitLastName) {
      lastName = traitLastName;
    }

    // Try to derive from name if not set
    if (!firstName && !lastName) {
      const name = traits[IDENTITY_TRAIT.NAME];
      if (typeof name === 'string' && name) {
        const parts = name.trim().split(/\s+/);
        if (parts.length === 1) {
          firstName = parts[0];
        } else if (parts.length >= 2) {
          firstName = parts[0];
          lastName = parts.slice(1).join(' ');
        }
      }
    }

    return { firstName, lastName };
  };

  /**
   * Extract role from traits
   */
  private extractRole = (traits: IdentityTraits): UserRole => {
    const role = traits[IDENTITY_TRAIT.ROLE];

    if (typeof role === 'string' && isValidRole(role)) {
      return role;
    }

    return DEFAULT_USER_ROLE;
  };

  /**
   * Check if email is verified
   */
  private isEmailVerified = (identity: Identity, email: string): boolean => {
    if (!identity.verifiable_addresses) {
      return false;
    }

    const emailAddress = identity.verifiable_addresses.find(
      (addr) => addr.value.toLowerCase() === email.toLowerCase() && addr.via === 'email',
    );

    return emailAddress?.verified === true;
  };
}
