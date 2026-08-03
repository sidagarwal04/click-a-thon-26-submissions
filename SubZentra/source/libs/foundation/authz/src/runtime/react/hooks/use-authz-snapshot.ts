import type { AuthzSnapshot } from '../../../core';
import { useAuthzRuntimeContext } from '../authz-context';

export const useAuthzSnapshot = (): AuthzSnapshot => useAuthzRuntimeContext().snapshot;
