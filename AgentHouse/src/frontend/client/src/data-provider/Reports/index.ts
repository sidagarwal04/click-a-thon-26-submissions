import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { QueryKeys } from 'librechat-data-provider';
import type { AnalyticsBlock, AnalyticsReport } from 'librechat-data-provider';
import {
  createReport,
  deleteReport,
  getReport,
  listReports,
  updateReport,
} from './store';

export * from './utils';

const REPORTS_KEY = [QueryKeys.analyticsReports] as const;

export function useReportsQuery() {
  return useQuery({
    queryKey: REPORTS_KEY,
    queryFn: (): AnalyticsReport[] => listReports(),
  });
}

export function useReportQuery(id: string | null) {
  return useQuery({
    queryKey: [...REPORTS_KEY, id],
    queryFn: (): AnalyticsReport | undefined => (id ? getReport(id) : undefined),
    enabled: Boolean(id),
  });
}

type CreateReportInput = {
  title: string;
  conversationId: string;
  blocks: AnalyticsBlock[];
};

export function useCreateReportMutation() {
  const queryClient = useQueryClient();
  return useMutation<AnalyticsReport, Error, CreateReportInput>({
    mutationFn: (input) => createReport(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: REPORTS_KEY });
    },
  });
}

type UpdateReportInput = {
  id: string;
  title?: string;
  blocks?: AnalyticsBlock[];
};

export function useUpdateReportMutation() {
  const queryClient = useQueryClient();
  return useMutation<AnalyticsReport, Error, UpdateReportInput>({
    mutationFn: ({ id, ...patch }) => {
      const updated = updateReport(id, patch);
      if (!updated) {
        throw new Error('Report not found');
      }
      return updated;
    },
    onSuccess: (report) => {
      void queryClient.invalidateQueries({ queryKey: REPORTS_KEY });
      queryClient.setQueryData([...REPORTS_KEY, report.id], report);
    },
  });
}

export function useDeleteReportMutation() {
  const queryClient = useQueryClient();
  return useMutation<string, Error, string>({
    mutationFn: (id) => {
      if (!deleteReport(id)) {
        throw new Error('Report not found');
      }
      return id;
    },
    onSuccess: (id) => {
      void queryClient.invalidateQueries({ queryKey: REPORTS_KEY });
      queryClient.removeQueries({ queryKey: [...REPORTS_KEY, id] });
    },
  });
}
