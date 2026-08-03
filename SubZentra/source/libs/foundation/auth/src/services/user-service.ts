/**
 * User Service
 *
 * Manages user identity operations.
 *
 * @module services/user-service
 */

import type { Identity } from '@ory/client-fetch';

import { AUTH_FLOW_TYPE } from '../core/constants';
import type { OryClientInstance } from '../core/ory-client';
import type {
  AuthConfig,
  IdentityTraits,
  TypedIdentity,
  UserServiceInterface,
} from '../core/types';
import {
  AuthNetworkError,
  FlowCreationError,
  FlowSubmissionError,
  UserNotFoundError,
} from '../errors/auth-errors';

// =============================================================================
// User Service
// =============================================================================

/**
 * User service implementation
 *
 * Handles user identity operations:
 * - Get current identity
 * - Update user traits
 */
export class UserService implements UserServiceInterface {
  private readonly oryClient: OryClientInstance;
  private disposed = false;

  constructor(oryClient: OryClientInstance, _config: AuthConfig) {
    this.oryClient = oryClient;
  }

  /**
   * Get current user's identity
   */
  getCurrentIdentity = async (): Promise<TypedIdentity | null> => {
    this.ensureNotDisposed();

    try {
      const session = await this.oryClient.frontend.toSession();

      if (!session.active || !session.identity) {
        return null;
      }

      return this.mapToTypedIdentity(session.identity);
    } catch (error) {
      // 401/403 means no valid session
      if (this.isUnauthorizedError(error)) {
        return null;
      }

      if (this.isNetworkError(error)) {
        throw new AuthNetworkError('getCurrentIdentity', error as Error);
      }

      throw new UserNotFoundError(undefined, error instanceof Error ? error : undefined);
    }
  };

  /**
   * Update user traits
   *
   * This requires a settings flow to update traits.
   */
  updateTraits = async (traits: Partial<IdentityTraits>): Promise<TypedIdentity> => {
    this.ensureNotDisposed();

    try {
      // Create a settings flow
      const flow = await this.oryClient.frontend.createBrowserSettingsFlow();

      // Submit the traits update
      const result = await this.oryClient.frontend.updateSettingsFlow({
        flow: flow.id,
        updateSettingsFlowBody: {
          method: 'profile',
          traits,
        },
      });

      // Get the updated identity from the result
      if (result.identity) {
        return this.mapToTypedIdentity(result.identity);
      }

      // If no identity in result, fetch current identity
      const identity = await this.getCurrentIdentity();
      if (!identity) {
        throw new UserNotFoundError('Current user not found after update');
      }
      return identity;
    } catch (error) {
      if (error instanceof UserNotFoundError) {
        throw error;
      }

      if (this.isNetworkError(error)) {
        throw new AuthNetworkError('updateTraits', error as Error);
      }

      // Check if it's a flow-related error
      if (this.isFlowError(error)) {
        throw new FlowSubmissionError(
          AUTH_FLOW_TYPE.SETTINGS,
          error instanceof Error ? error.message : 'Unknown error',
          error instanceof Error ? error : undefined,
        );
      }

      throw new FlowCreationError(
        AUTH_FLOW_TYPE.SETTINGS,
        error instanceof Error ? error.message : 'Unknown error',
        error instanceof Error ? error : undefined,
      );
    }
  };

  /**
   * Dispose resources
   */
  dispose = async (): Promise<void> => {
    this.disposed = true;
  };

  // ==========================================================================
  // Private Methods
  // ==========================================================================

  /**
   * Ensure service is not disposed
   */
  private ensureNotDisposed = (): void => {
    if (this.disposed) {
      throw new Error('[UserService] Service has been disposed');
    }
  };

  /**
   * Map Ory identity to TypedIdentity
   */
  private mapToTypedIdentity = (identity: Identity): TypedIdentity => {
    const traits = (identity.traits ?? {}) as IdentityTraits;

    // The Ory SDK types use Date objects, but we convert to ISO strings for consistency
    return {
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
        created_at:
          addr.created_at instanceof Date ? addr.created_at.toISOString() : addr.created_at,
        updated_at:
          addr.updated_at instanceof Date ? addr.updated_at.toISOString() : addr.updated_at,
      })),
      recovery_addresses: identity.recovery_addresses?.map((addr) => ({
        id: addr.id,
        value: addr.value,
        via: addr.via,
        created_at:
          addr.created_at instanceof Date ? addr.created_at.toISOString() : addr.created_at,
        updated_at:
          addr.updated_at instanceof Date ? addr.updated_at.toISOString() : addr.updated_at,
      })),
      metadata_public: identity.metadata_public as Record<string, unknown> | undefined,
      metadata_admin: identity.metadata_admin as Record<string, unknown> | undefined,
      created_at:
        identity.created_at instanceof Date
          ? identity.created_at.toISOString()
          : identity.created_at,
      updated_at:
        identity.updated_at instanceof Date
          ? identity.updated_at.toISOString()
          : identity.updated_at,
    };
  };

  /**
   * Check if error is an unauthorized error
   */
  private isUnauthorizedError = (error: unknown): boolean => {
    if (error && typeof error === 'object' && 'status' in error) {
      const status = (error as { status: number }).status;
      return status === 401 || status === 403;
    }
    return false;
  };

  /**
   * Check if error is a network error
   */
  private isNetworkError = (error: unknown): boolean => {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      return true;
    }
    if (error && typeof error === 'object' && 'name' in error) {
      return (error as { name: string }).name === 'NetworkError';
    }
    return false;
  };

  /**
   * Check if error is a flow-related error
   */
  private isFlowError = (error: unknown): boolean => {
    if (error && typeof error === 'object' && 'status' in error) {
      const status = (error as { status: number }).status;
      // 400 - validation error, 410 - flow expired
      return status === 400 || status === 410;
    }
    return false;
  };
}
