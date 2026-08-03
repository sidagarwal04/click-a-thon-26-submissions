import { useMutation } from '@tanstack/react-query';
import { MutationKeys, dataService } from 'librechat-data-provider';
import type { UseMutationOptions } from '@tanstack/react-query';
import type { AnalyticsQueryRequest, AnalyticsResponse } from 'librechat-data-provider';

export const useAnalyticsQueryMutation = (
  options?: UseMutationOptions<AnalyticsResponse, Error, AnalyticsQueryRequest>,
) => {
  return useMutation(
    [MutationKeys.analyticsQuery],
    (payload: AnalyticsQueryRequest) => dataService.queryAnalytics(payload),
    options,
  );
};
