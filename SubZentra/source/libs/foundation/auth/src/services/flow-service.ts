/**
 * Flow Service
 *
 * Manages authentication flows (login, registration, recovery, verification, settings).
 *
 * @module services/flow-service
 */

import type {
  LoginFlow,
  RecoveryFlow,
  RegistrationFlow,
  SettingsFlow,
  UpdateLoginFlowBody,
  UpdateRecoveryFlowBody,
  UpdateRegistrationFlowBody,
  UpdateSettingsFlowBody,
  UpdateVerificationFlowBody,
  VerificationFlow,
} from '@ory/client-fetch';

import { AUTH_FLOW_TYPE } from '../core/constants';
import type { OryClientInstance } from '../core/ory-client';
import type {
  AuthConfig,
  FlowServiceInterface,
  LoginSubmission,
  RecoverySubmission,
  RegistrationSubmission,
  SettingsSubmission,
  VerificationSubmission,
} from '../core/types';
import {
  AuthNetworkError,
  FlowCreationError,
  FlowExpiredError,
  FlowNotFoundError,
  FlowSubmissionError,
  InvalidCredentialsError,
} from '../errors/auth-errors';

// =============================================================================
// Flow Service
// =============================================================================

/**
 * Flow service implementation
 *
 * Handles authentication flow lifecycle:
 * - Flow creation (browser flows)
 * - Flow retrieval
 * - Flow submission
 * - Error handling and flow expiry
 */
export class FlowService implements FlowServiceInterface {
  private readonly oryClient: OryClientInstance;
  private disposed = false;

  constructor(oryClient: OryClientInstance, _config: AuthConfig) {
    this.oryClient = oryClient;
  }

  // ==========================================================================
  // Login Flow
  // ==========================================================================

  /**
   * Create a new login flow
   */
  createLoginFlow = async (returnTo?: string): Promise<LoginFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.createBrowserLoginFlow({
        returnTo,
      });
      return flow;
    } catch (error) {
      throw this.handleFlowCreationError(AUTH_FLOW_TYPE.LOGIN, error);
    }
  };

  /**
   * Get an existing login flow
   */
  getLoginFlow = async (flowId: string): Promise<LoginFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.getLoginFlow({ id: flowId });
      this.checkFlowExpiry(flow, AUTH_FLOW_TYPE.LOGIN);
      return flow;
    } catch (error) {
      throw this.handleFlowRetrievalError(flowId, AUTH_FLOW_TYPE.LOGIN, error);
    }
  };

  /**
   * Submit a login flow
   */
  submitLoginFlow = async (flowId: string, data: LoginSubmission): Promise<void> => {
    this.ensureNotDisposed();

    try {
      const body: UpdateLoginFlowBody = {
        method: 'password',
        identifier: data.identifier,
        password: data.password,
        csrf_token: data.csrf_token,
      };

      await this.oryClient.frontend.updateLoginFlow({
        flow: flowId,
        updateLoginFlowBody: body,
      });
    } catch (error) {
      throw this.handleFlowSubmissionError(AUTH_FLOW_TYPE.LOGIN, error);
    }
  };

  // ==========================================================================
  // Registration Flow
  // ==========================================================================

  /**
   * Create a new registration flow
   */
  createRegistrationFlow = async (returnTo?: string): Promise<RegistrationFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.createBrowserRegistrationFlow({
        returnTo,
      });
      return flow;
    } catch (error) {
      throw this.handleFlowCreationError(AUTH_FLOW_TYPE.REGISTRATION, error);
    }
  };

  /**
   * Get an existing registration flow
   */
  getRegistrationFlow = async (flowId: string): Promise<RegistrationFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.getRegistrationFlow({ id: flowId });
      this.checkFlowExpiry(flow, AUTH_FLOW_TYPE.REGISTRATION);
      return flow;
    } catch (error) {
      throw this.handleFlowRetrievalError(flowId, AUTH_FLOW_TYPE.REGISTRATION, error);
    }
  };

  /**
   * Submit a registration flow
   */
  submitRegistrationFlow = async (flowId: string, data: RegistrationSubmission): Promise<void> => {
    this.ensureNotDisposed();

    try {
      // Build traits from submission data
      const traits: Record<string, unknown> = {
        email: data.email,
      };

      if (data.name) traits.name = data.name;
      if (data.first_name) traits.first_name = data.first_name;
      if (data.last_name) traits.last_name = data.last_name;

      // Add any additional traits
      Object.entries(data).forEach(([key, value]) => {
        if (!['email', 'password', 'name', 'first_name', 'last_name', 'csrf_token'].includes(key)) {
          traits[key] = value;
        }
      });

      const body: UpdateRegistrationFlowBody = {
        method: 'password',
        password: data.password,
        traits,
        csrf_token: data.csrf_token,
      };

      await this.oryClient.frontend.updateRegistrationFlow({
        flow: flowId,
        updateRegistrationFlowBody: body,
      });
    } catch (error) {
      throw this.handleFlowSubmissionError(AUTH_FLOW_TYPE.REGISTRATION, error);
    }
  };

  // ==========================================================================
  // Recovery Flow
  // ==========================================================================

  /**
   * Create a new recovery flow
   */
  createRecoveryFlow = async (returnTo?: string): Promise<RecoveryFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.createBrowserRecoveryFlow({
        returnTo,
      });
      return flow;
    } catch (error) {
      throw this.handleFlowCreationError(AUTH_FLOW_TYPE.RECOVERY, error);
    }
  };

  /**
   * Get an existing recovery flow
   */
  getRecoveryFlow = async (flowId: string): Promise<RecoveryFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.getRecoveryFlow({ id: flowId });
      this.checkFlowExpiry(flow, AUTH_FLOW_TYPE.RECOVERY);
      return flow;
    } catch (error) {
      throw this.handleFlowRetrievalError(flowId, AUTH_FLOW_TYPE.RECOVERY, error);
    }
  };

  /**
   * Submit a recovery flow
   */
  submitRecoveryFlow = async (flowId: string, data: RecoverySubmission): Promise<void> => {
    this.ensureNotDisposed();

    try {
      const body: UpdateRecoveryFlowBody = {
        method: 'code',
        email: data.email,
        csrf_token: data.csrf_token,
      };

      await this.oryClient.frontend.updateRecoveryFlow({
        flow: flowId,
        updateRecoveryFlowBody: body,
      });
    } catch (error) {
      throw this.handleFlowSubmissionError(AUTH_FLOW_TYPE.RECOVERY, error);
    }
  };

  // ==========================================================================
  // Verification Flow
  // ==========================================================================

  /**
   * Create a new verification flow
   */
  createVerificationFlow = async (returnTo?: string): Promise<VerificationFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.createBrowserVerificationFlow({
        returnTo,
      });
      return flow;
    } catch (error) {
      throw this.handleFlowCreationError(AUTH_FLOW_TYPE.VERIFICATION, error);
    }
  };

  /**
   * Get an existing verification flow
   */
  getVerificationFlow = async (flowId: string): Promise<VerificationFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.getVerificationFlow({ id: flowId });
      this.checkFlowExpiry(flow, AUTH_FLOW_TYPE.VERIFICATION);
      return flow;
    } catch (error) {
      throw this.handleFlowRetrievalError(flowId, AUTH_FLOW_TYPE.VERIFICATION, error);
    }
  };

  /**
   * Submit a verification flow
   */
  submitVerificationFlow = async (flowId: string, data: VerificationSubmission): Promise<void> => {
    this.ensureNotDisposed();

    try {
      const body: UpdateVerificationFlowBody = {
        method: 'code',
        email: data.email,
        code: data.code,
        csrf_token: data.csrf_token,
      };

      await this.oryClient.frontend.updateVerificationFlow({
        flow: flowId,
        updateVerificationFlowBody: body,
      });
    } catch (error) {
      throw this.handleFlowSubmissionError(AUTH_FLOW_TYPE.VERIFICATION, error);
    }
  };

  // ==========================================================================
  // Settings Flow
  // ==========================================================================

  /**
   * Create a new settings flow
   */
  createSettingsFlow = async (returnTo?: string): Promise<SettingsFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.createBrowserSettingsFlow({
        returnTo,
      });
      return flow;
    } catch (error) {
      throw this.handleFlowCreationError(AUTH_FLOW_TYPE.SETTINGS, error);
    }
  };

  /**
   * Get an existing settings flow
   */
  getSettingsFlow = async (flowId: string): Promise<SettingsFlow> => {
    this.ensureNotDisposed();

    try {
      const flow = await this.oryClient.frontend.getSettingsFlow({ id: flowId });
      this.checkFlowExpiry(flow, AUTH_FLOW_TYPE.SETTINGS);
      return flow;
    } catch (error) {
      throw this.handleFlowRetrievalError(flowId, AUTH_FLOW_TYPE.SETTINGS, error);
    }
  };

  /**
   * Submit a settings flow
   */
  submitSettingsFlow = async (flowId: string, data: SettingsSubmission): Promise<void> => {
    this.ensureNotDisposed();

    try {
      let body: UpdateSettingsFlowBody;

      if (data.password) {
        // Password update
        body = {
          method: 'password',
          password: data.password,
          csrf_token: data.csrf_token,
        };
      } else if (data.traits) {
        // Profile update
        body = {
          method: 'profile',
          traits: data.traits,
          csrf_token: data.csrf_token,
        };
      } else {
        throw new FlowSubmissionError(AUTH_FLOW_TYPE.SETTINGS, 'No valid settings data provided');
      }

      await this.oryClient.frontend.updateSettingsFlow({
        flow: flowId,
        updateSettingsFlowBody: body,
      });
    } catch (error) {
      if (error instanceof FlowSubmissionError) throw error;
      throw this.handleFlowSubmissionError(AUTH_FLOW_TYPE.SETTINGS, error);
    }
  };

  // ==========================================================================
  // Dispose
  // ==========================================================================

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
      throw new Error('[FlowService] Service has been disposed');
    }
  };

  /**
   * Check if flow is expired
   */
  private checkFlowExpiry = (
    flow: { expires_at?: Date | string; id: string },
    flowType: string,
  ): void => {
    if (flow.expires_at) {
      const expiresAt =
        flow.expires_at instanceof Date
          ? flow.expires_at.getTime()
          : new Date(flow.expires_at).getTime();
      if (expiresAt < Date.now()) {
        throw new FlowExpiredError(flow.id, flowType, expiresAt);
      }
    }
  };

  /**
   * Handle flow creation errors
   */
  private handleFlowCreationError = (flowType: string, error: unknown): Error => {
    if (this.isNetworkError(error)) {
      return new AuthNetworkError(`create${flowType}Flow`, error as Error);
    }
    return new FlowCreationError(
      flowType,
      error instanceof Error ? error.message : 'Unknown error',
      error instanceof Error ? error : undefined,
    );
  };

  /**
   * Handle flow retrieval errors
   */
  private handleFlowRetrievalError = (flowId: string, flowType: string, error: unknown): Error => {
    // 404 means flow not found
    if (this.isNotFoundError(error)) {
      return new FlowNotFoundError(flowId, flowType, error as Error);
    }

    // 410 means flow expired (Gone)
    if (this.isGoneError(error)) {
      return new FlowExpiredError(flowId, flowType, undefined, error as Error);
    }

    if (this.isNetworkError(error)) {
      return new AuthNetworkError(`get${flowType}Flow`, error as Error);
    }

    return new FlowNotFoundError(flowId, flowType, error instanceof Error ? error : undefined);
  };

  /**
   * Handle flow submission errors
   */
  private handleFlowSubmissionError = (flowType: string, error: unknown): Error => {
    // Check for invalid credentials (specific to login)
    if (flowType === AUTH_FLOW_TYPE.LOGIN && this.isInvalidCredentialsError(error)) {
      return new InvalidCredentialsError(error as Error);
    }

    // Check for flow expiry during submission
    if (this.isGoneError(error)) {
      return new FlowExpiredError('unknown', flowType, undefined, error as Error);
    }

    if (this.isNetworkError(error)) {
      return new AuthNetworkError(`submit${flowType}Flow`, error as Error);
    }

    return new FlowSubmissionError(
      flowType,
      error instanceof Error ? error.message : 'Unknown error',
      error instanceof Error ? error : undefined,
    );
  };

  /**
   * Check if error is a not found error
   */
  private isNotFoundError = (error: unknown): boolean => {
    if (error && typeof error === 'object' && 'status' in error) {
      return (error as { status: number }).status === 404;
    }
    return false;
  };

  /**
   * Check if error is a gone error (expired)
   */
  private isGoneError = (error: unknown): boolean => {
    if (error && typeof error === 'object' && 'status' in error) {
      return (error as { status: number }).status === 410;
    }
    return false;
  };

  /**
   * Check if error indicates invalid credentials
   */
  private isInvalidCredentialsError = (error: unknown): boolean => {
    if (error && typeof error === 'object') {
      // Ory returns 400 with specific error messages for invalid credentials
      const err = error as { status?: number; body?: { error?: { id?: string } } };
      if (err.status === 400) {
        const errorId = err.body?.error?.id;
        return errorId === 'session_already_available' || errorId === 'self_service_flow_error';
      }
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
}
