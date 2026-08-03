import { FileText, Trash2 } from 'lucide-react';
import { useSetRecoilState } from 'recoil';
import { Spinner, useToastContext } from '@librechat/client';
import type { AnalyticsReport } from 'librechat-data-provider';
import { useDeleteReportMutation, useReportsQuery } from '~/data-provider';
import { useLocalize } from '~/hooks';
import store from '~/store';

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function ReportRow({ report }: { report: AnalyticsReport }) {
  const localize = useLocalize();
  const { showToast } = useToastContext();
  const setSelectedReportId = useSetRecoilState(store.selectedReportId);
  const deleteMutation = useDeleteReportMutation();

  const handleDelete = () => {
    if (!window.confirm(localize('com_ui_reports_delete_confirm'))) {
      return;
    }
    deleteMutation.mutate(report.id, {
      onSuccess: () => {
        setSelectedReportId((current) => (current === report.id ? null : current));
        showToast({ message: localize('com_ui_reports_deleted'), status: 'success' });
      },
    });
  };

  return (
    <div className="group flex w-full items-start gap-1 rounded-lg px-1 py-1 hover:bg-surface-hover">
      <button
        type="button"
        className="flex min-w-0 flex-1 items-start gap-2 rounded-md px-1 py-1 text-left"
        onClick={() => setSelectedReportId(report.id)}
        aria-label={report.title}
      >
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm text-text-primary">{report.title}</span>
          <span className="block text-xs text-text-secondary">{formatDate(report.updatedAt)}</span>
        </span>
      </button>
      <button
        type="button"
        className="rounded p-1 text-text-secondary opacity-0 transition-opacity hover:bg-surface-tertiary hover:text-text-primary group-hover:opacity-100 focus:opacity-100"
        aria-label={localize('com_ui_delete')}
        onClick={handleDelete}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export default function ReportsPanel() {
  const localize = useLocalize();
  const { data: reports = [], isLoading } = useReportsQuery();

  return (
    <div className="flex h-full flex-col px-2 py-3" data-testid="reports-panel">
      <h2 className="mb-3 px-2 text-sm font-semibold text-text-primary">
        {localize('com_ui_reports')}
      </h2>
      {isLoading ? (
        <div className="flex flex-1 items-center justify-center">
          <Spinner />
        </div>
      ) : reports.length === 0 ? (
        <p className="px-2 text-sm text-text-secondary">{localize('com_ui_reports_empty')}</p>
      ) : (
        <div className="flex flex-col gap-0.5 overflow-y-auto" role="list">
          {reports.map((report) => (
            <div key={report.id} role="listitem">
              <ReportRow report={report} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
