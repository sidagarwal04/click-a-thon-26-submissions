/**
 * useAuthFlow Hook
 *
 * Hook for managing authentication flows.
 *
 * @module hooks/use-auth-flow
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import type {
  LoginFlow,
  RecoveryFlow,
  RegistrationFlow,
  SettingsFlow,
  VerificationFlow,
} from '@ory/client-fetch';

import { AUTH_FLOW_TYPE, FLOW_STATE, type AuthFlowType } from '../core/constants';
import type {
  FlowState,
  LoginSubmission,
  OryFlow,
  RecoverySubmission,
  RegistrationSubmission,
  SettingsSubmission,
  UseAuthFlowOptions,
  UseAuthFlowResult,
  VerificationSubmission,
} from '../core/types';
import { FlowExpiredError } from '../errors/auth-errors';
import { useAuthInternals } from '../providers/auth-internals-context';

// =============================================================================
// Type Helpers
// =============================================================================

type FlowTypeMap = {
  [AUTH_FLOW_TYPE.LOGIN]: LoginFlow;
  [AUTH_FLOW_TYPE.REGISTRATION]: RegistrationFlow;
  [AUTH_FLOW_TYPE.RECOVERY]: RecoveryFlow;
  [AUTH_FLOW_TYPE.VERIFICATION]: VerificationFlow;
  [AUTH_FLOW_TYPE.SETTINGS]: SettingsFlow;
};

type SubmissionTypeMap = {
  [AUTH_FLOW_TYPE.LOGIN]: LoginSubmission;
  [AUTH_FLOW_TYPE.REGISTRATION]: RegistrationSubmission;
  [AUTH_FLOW_TYPE.RECOVERY]: RecoverySubmission;
  [AUTH_FLOW_TYPE.VERIFICATION]: VerificationSubmission;
  [AUTH_FLOW_TYPE.SETTINGS]: SettingsSubmission;
};

// =============================================================================
// Hook
// =============================================================================

/**
 * Manage an authentication flow
 *
 * Provides state management for auth flows (login, registration, etc.).
 *
 * @param options - Flow options
 * @returns Flow state and operations
 *
 * @example
 * ```tsx
 * // Login flow
 * const {
 *   flowState,
 *   createFlow,
 *   submitFlow,
 *   isLoading,
 *   isSubmitting,
 * } = useAuthFlow({ type: 'login', autoCreate: true });
 *
 * const handleSubmit = async (data: LoginSubmission) => {
 *   await submitFlow(data);
 * };
 *
 * if (isLoading) return <LoadingSpinner />;
 *
 * return (
 *   <LoginForm
 *     flow={flowState.flow}
 *     onSubmit={handleSubmit}
 *     isSubmitting={isSubmitting}
 *   />
 * );
 * ```
 */
export const useAuthFlow = <T extends AuthFlowType>(
  options: UseAuthFlowOptions<T>,
): UseAuthFlowResult<FlowTypeMap[T]> => {
  const { type, autoCreate = false, returnTo } = options;
  const { facade } = useAuthInternals();

  // State
  const [flowState, setFlowState] = useState<FlowState<FlowTypeMap[T]>>({
    type,
    flow: null,
    state: FLOW_STATE.PENDING,
    error: null,
    flowId: null,
    expiresAt: null,
  });

  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ==========================================================================
  // Create Flow
  // ==========================================================================

  const createFlow = useCallback(async (): Promise<void> => {
    if (!facade) return;

    setIsLoading(true);
    setFlowState((prev) => ({
      ...prev,
      state: FLOW_STATE.PENDING,
      error: null,
    }));

    try {
      let flow: OryFlow;

      switch (type) {
        case AUTH_FLOW_TYPE.LOGIN:
          flow = await facade.flow.createLoginFlow(returnTo);
          break;
        case AUTH_FLOW_TYPE.REGISTRATION:
          flow = await facade.flow.createRegistrationFlow(returnTo);
          break;
        case AUTH_FLOW_TYPE.RECOVERY:
          flow = await facade.flow.createRecoveryFlow(returnTo);
          break;
        case AUTH_FLOW_TYPE.VERIFICATION:
          flow = await facade.flow.createVerificationFlow(returnTo);
          break;
        case AUTH_FLOW_TYPE.SETTINGS:
          flow = await facade.flow.createSettingsFlow(returnTo);
          break;
        default:
          throw new Error(`Unknown flow type: ${type}`);
      }

      setFlowState({
        type,
        flow: flow as FlowTypeMap[T],
        state: FLOW_STATE.PENDING,
        error: null,
        flowId: flow.id,
        expiresAt: flow.expires_at ? new Date(flow.expires_at).getTime() : null,
      });
    } catch (error) {
      setFlowState((prev) => ({
        ...prev,
        state: FLOW_STATE.FAILED,
        error: error instanceof Error ? error : new Error('Failed to create flow'),
      }));
    } finally {
      setIsLoading(false);
    }
  }, [facade, type, returnTo]);

  // ==========================================================================
  // Submit Flow
  // ==========================================================================

  const submitFlow = useCallback(
    async (data: SubmissionTypeMap[T]): Promise<void> => {
      if (!facade || !flowState.flowId) return;

      // Check for expiry
      if (flowState.expiresAt && flowState.expiresAt < Date.now()) {
        setFlowState((prev) => ({
          ...prev,
          state: FLOW_STATE.EXPIRED,
          error: new FlowExpiredError(prev.flowId ?? 'unknown', type, prev.expiresAt ?? undefined),
        }));
        return;
      }

      setIsSubmitting(true);
      setFlowState((prev) => ({
        ...prev,
        state: FLOW_STATE.SUBMITTING,
        error: null,
      }));

      try {
        switch (type) {
          case AUTH_FLOW_TYPE.LOGIN:
            await facade.flow.submitLoginFlow(flowState.flowId, data as LoginSubmission);
            break;
          case AUTH_FLOW_TYPE.REGISTRATION:
            await facade.flow.submitRegistrationFlow(
              flowState.flowId,
              data as RegistrationSubmission,
            );
            break;
          case AUTH_FLOW_TYPE.RECOVERY:
            await facade.flow.submitRecoveryFlow(flowState.flowId, data as RecoverySubmission);
            break;
          case AUTH_FLOW_TYPE.VERIFICATION:
            await facade.flow.submitVerificationFlow(
              flowState.flowId,
              data as VerificationSubmission,
            );
            break;
          case AUTH_FLOW_TYPE.SETTINGS:
            await facade.flow.submitSettingsFlow(flowState.flowId, data as SettingsSubmission);
            break;
        }

        setFlowState((prev) => ({
          ...prev,
          state: FLOW_STATE.COMPLETED,
        }));
      } catch (error) {
        // Check if flow expired during submission
        if (error instanceof FlowExpiredError) {
          setFlowState((prev) => ({
            ...prev,
            state: FLOW_STATE.EXPIRED,
            error,
          }));
        } else {
          setFlowState((prev) => ({
            ...prev,
            state: FLOW_STATE.FAILED,
            error: error instanceof Error ? error : new Error('Failed to submit flow'),
          }));
        }
      } finally {
        setIsSubmitting(false);
      }
    },
    [facade, flowState.flowId, flowState.expiresAt, type],
  );

  // ==========================================================================
  // Reset Flow
  // ==========================================================================

  const resetFlow = useCallback((): void => {
    setFlowState({
      type,
      flow: null,
      state: FLOW_STATE.PENDING,
      error: null,
      flowId: null,
      expiresAt: null,
    });
    setIsLoading(false);
    setIsSubmitting(false);
  }, [type]);

  // ==========================================================================
  // Auto-create
  // ==========================================================================

  useEffect(() => {
    if (autoCreate && facade && !flowState.flowId) {
      createFlow();
    }
  }, [autoCreate, facade, flowState.flowId, createFlow]);

  // ==========================================================================
  // Return
  // ==========================================================================

  return useMemo(
    () => ({
      flowState,
      createFlow,
      submitFlow: submitFlow as (data: unknown) => Promise<void>,
      resetFlow,
      isLoading,
      isSubmitting,
    }),
    [flowState, createFlow, submitFlow, resetFlow, isLoading, isSubmitting],
  );
};

// =============================================================================
// Convenience Hooks
// =============================================================================

/**
 * Manage login flow
 */
export const useLoginFlow = (options?: Omit<UseAuthFlowOptions<'login'>, 'type'>) =>
  useAuthFlow({ ...options, type: AUTH_FLOW_TYPE.LOGIN });

/**
 * Manage registration flow
 */
export const useRegistrationFlow = (options?: Omit<UseAuthFlowOptions<'registration'>, 'type'>) =>
  useAuthFlow({ ...options, type: AUTH_FLOW_TYPE.REGISTRATION });

/**
 * Manage recovery flow
 */
export const useRecoveryFlow = (options?: Omit<UseAuthFlowOptions<'recovery'>, 'type'>) =>
  useAuthFlow({ ...options, type: AUTH_FLOW_TYPE.RECOVERY });

/**
 * Manage verification flow
 */
export const useVerificationFlow = (options?: Omit<UseAuthFlowOptions<'verification'>, 'type'>) =>
  useAuthFlow({ ...options, type: AUTH_FLOW_TYPE.VERIFICATION });

/**
 * Manage settings flow
 */
export const useSettingsFlow = (options?: Omit<UseAuthFlowOptions<'settings'>, 'type'>) =>
  useAuthFlow({ ...options, type: AUTH_FLOW_TYPE.SETTINGS });
