import { atom } from 'recoil';
import { atomWithLocalStorage } from '~/store/utils';

/**
 * Kept for backwards compatibility with persisted UI state.
 * Chat submit always uses the analytics path in this deployment.
 */
export const analyticsMode = atomWithLocalStorage('analyticsMode', true);

/** Currently open analytics report in the main column (`null` = chat). */
export const selectedReportId = atom<string | null>({
  key: 'selectedReportId',
  default: null,
});
