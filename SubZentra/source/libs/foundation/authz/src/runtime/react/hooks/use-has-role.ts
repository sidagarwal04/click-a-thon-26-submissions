import { AUTHZ_ROLE_ACTION } from '../../../core';
import { useCan, type UseCanResult } from './use-can';

export const useHasRole = (role: string): UseCanResult =>
  useCan({
    action: AUTHZ_ROLE_ACTION,
    resource: role,
  });
