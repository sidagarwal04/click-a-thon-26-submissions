/**
 * Hooks Module
 *
 * Authentication hooks for React components.
 *
 * @module hooks
 */

// Main hook
export { useAuth } from './use-auth';

// User hooks
export { useAuthUser, useRequiredAuthUser } from './use-auth-user';

// Session hook
export { useAuthSession } from './use-auth-session';

// Flow hooks
export {
  useAuthFlow,
  useLoginFlow,
  useRegistrationFlow,
  useRecoveryFlow,
  useVerificationFlow,
  useSettingsFlow,
} from './use-auth-flow';

// Internals (internal use only)
export { useAuthInternals, useRequiredAuthInternals } from './use-auth-internals';
